import math
from .accounting import check_invoice_total
from .schemas import WarningItem
from .utils import GSTIN_PATTERN, _parse_float
def _build_warnings(document_type: str, fields: dict[str, str], rows: list[dict[str, str]], line_items: list[dict[str, str]] | None = None) -> list[WarningItem]:
    warnings: list[WarningItem] = []

    if document_type == "invoice":
        # --- GSTIN Validation ---
        gstin = fields.get("gstin", "")
        if not gstin:
            warnings.append(WarningItem(level="warning", field="gstin", message="Supplier GSTIN is missing."))
        elif not GSTIN_PATTERN.fullmatch(gstin.upper()):
            warnings.append(WarningItem(level="warning", field="gstin", message="Supplier GSTIN format looks invalid."))
        else:
            warnings.append(WarningItem(level="success", field="gstin", message=f"Supplier GSTIN verified: {gstin}"))

        buyer_gstin = fields.get("buyer_gstin", "")
        if not buyer_gstin:
            warnings.append(WarningItem(level="warning", field="buyer_gstin", message="Buyer GSTIN is missing. ITC claims require both GSTINs."))
        else:
            warnings.append(WarningItem(level="success", field="buyer_gstin", message=f"Buyer GSTIN found: {buyer_gstin}"))

        # --- Date ---
        if not fields.get("date"):
            warnings.append(WarningItem(level="warning", field="date", message="Invoice date is missing."))
        else:
            warnings.append(WarningItem(level="success", field="date", message=f"Invoice date: {fields['date']}"))

        # --- Invoice Number ---
        if fields.get("invoice_number"):
            warnings.append(WarningItem(level="success", field="invoice_number", message=f"Invoice #: {fields['invoice_number']}"))

        # --- Discount ---
        if fields.get("discount"):
            warnings.append(WarningItem(level="info", field="discount", message=f"Discount of {fields['discount']} applied before tax."))

        # --- Tax presence ---
        if not fields.get("total"):
            warnings.append(WarningItem(level="warning", field="total", message="Total is missing."))

        if not any(fields.get(key) for key in ["taxable_amount", "cgst", "sgst", "igst"]):
            warnings.append(WarningItem(level="warning", field="taxable_amount", message="Taxable amount or tax values are missing."))

        # --- MATH VALIDATION (shared with M3A arbitration) ---
        total_check = check_invoice_total(fields)
        if total_check.matches is not None:
            expected_total = float(total_check.expected_total)
            total = float(total_check.observed_total)
            if total_check.matches:
                taxable = _parse_float(fields.get("taxable_amount", "") or "") or 0.0
                cgst = _parse_float(fields.get("cgst", "") or "") or 0.0
                sgst = _parse_float(fields.get("sgst", "") or "") or 0.0
                igst = _parse_float(fields.get("igst", "") or "") or 0.0
                warnings.append(
                    WarningItem(
                        level="success",
                        field="total",
                        message=f"Math validated: {taxable} + {cgst} + {sgst} + {igst} = {expected_total} (total: {total})",
                    )
                )
            else:
                warnings.append(
                    WarningItem(
                        level="warning",
                        field="total",
                        message=f"Math mismatch: expected {expected_total}, but total reads {total}. Difference: {float(total_check.difference):.2f}",
                    )
                )

        # --- Line items check ---
        if line_items:
            warnings.append(WarningItem(level="success", field="line_items", message=f"{len(line_items)} line item(s) extracted with HSN codes."))
        else:
            warnings.append(WarningItem(level="info", field="line_items", message="No line items extracted. HSN codes may be missing from the scan."))

    elif document_type == "ledger":
        previous_balance = None
        for index, row in enumerate(rows):
            debit_value = _parse_float(row.get("debit", "") or "")
            credit_value = _parse_float(row.get("credit", "") or "")
            balance_value = _parse_float(row.get("balance", "") or "")

            if not row.get("date"):
                warnings.append(WarningItem(level="warning", field=f"rows[{index}].date", message="Missing transaction date."))

            if debit_value is not None and credit_value is not None:
                warnings.append(
                    WarningItem(
                        level="warning",
                        field=f"rows[{index}]",
                        message="Both debit and credit are filled for one row.",
                    )
                )
            if debit_value is None and credit_value is None:
                warnings.append(
                    WarningItem(
                        level="warning",
                        field=f"rows[{index}]",
                        message="Neither debit nor credit is filled for one row.",
                    )
                )

            if row.get("debit") and debit_value is None:
                warnings.append(WarningItem(level="warning", field=f"rows[{index}].debit", message="Invalid debit amount format."))
            if row.get("credit") and credit_value is None:
                warnings.append(WarningItem(level="warning", field=f"rows[{index}].credit", message="Invalid credit amount format."))
            if row.get("balance") and balance_value is None:
                warnings.append(WarningItem(level="warning", field=f"rows[{index}].balance", message="Invalid balance amount format."))

            if previous_balance is not None and balance_value is not None:
                expected_balance = previous_balance
                if credit_value is not None:
                    expected_balance += credit_value
                if debit_value is not None:
                    expected_balance -= debit_value
                if math.fabs(expected_balance - balance_value) > 1.0:
                    warnings.append(
                        WarningItem(
                            level="warning",
                            field=f"rows[{index}].balance",
                            message="Running balance mismatch.",
                        )
                    )

            if balance_value is not None:
                previous_balance = balance_value

        if rows and not warnings:
            warnings.append(WarningItem(level="success", field="ledger", message=f"All {len(rows)} transaction(s) validated. Balances are consistent."))

    return warnings

def _compute_confidence(ocr_confidence: float, fields: dict[str, str], rows: list[dict[str, str]]) -> float:
    extraction_hits = len(fields) + len(rows)
    coverage_score = min(1.0, extraction_hits / 8.0)
    ocr_score = max(0.0, min(1.0, ocr_confidence / 100.0))
    return round(max(0.0, min(1.0, (ocr_score * 0.7) + (coverage_score * 0.3))), 4)

