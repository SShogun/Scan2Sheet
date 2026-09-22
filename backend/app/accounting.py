from __future__ import annotations

from dataclasses import dataclass


def _parse_amount(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(",", "").strip())
    except ValueError:
        return None


@dataclass(frozen=True)
class InvoiceTotalCheck:
    expected_total: float | None
    observed_total: float | None
    difference: float | None
    matches: bool | None


def expected_invoice_total(fields: dict[str, str]) -> float | None:
    taxable = _parse_amount(fields.get("taxable_amount"))
    if taxable is None or taxable <= 0:
        return None
    taxes = 0.0
    has_explicit_tax_context = False
    for key in ("cgst", "sgst", "igst"):
        value = _parse_amount(fields.get(key))
        if value is not None:
            taxes += value
            has_explicit_tax_context = True
    if not has_explicit_tax_context:
        return None
    return taxable + taxes


def check_invoice_total(
    fields: dict[str, str],
    total_value: str | None = None,
    *,
    tolerance: float = 1.0,
) -> InvoiceTotalCheck:
    expected = expected_invoice_total(fields)
    observed = _parse_amount(total_value if total_value is not None else fields.get("total"))
    if expected is None or observed is None:
        return InvoiceTotalCheck(expected, observed, None, None)
    difference = abs(expected - observed)
    return InvoiceTotalCheck(expected, observed, difference, difference <= tolerance)
