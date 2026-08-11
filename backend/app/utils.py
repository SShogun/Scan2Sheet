import re
from .schemas import WarningItem, ExtractResponse, InvoiceLineItem

GSTIN_PATTERN = re.compile(r"[0-9A-Z]{2}[A-Z]{5}[0-9A-Z]{4}[A-Z][0-9A-Z]Z[0-9A-Z]")
DATE_PATTERN = re.compile(r"\b(?:0?[1-9]|[12]\d|3[01])[\/.\- ](?:0?[1-9]|1[0-2]|[A-Za-z]{3})[\/.\- ](?:\d{2}|\d{4})\b", re.IGNORECASE)
AMOUNT_PATTERN = re.compile(r"(?<!\d)(?:Rs\.?\s*|INR\s*)?([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)(?!\d)")

def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def _classify_document(text: str) -> str:
    normalized = text.upper()
    invoice_score = sum(
        keyword in normalized
        for keyword in ["GSTIN", "INVOICE", "BILL", "CGST", "SGST", "IGST", "TAXABLE", "GRAND TOTAL", "TOTAL"]
    )
    ledger_score = sum(
        keyword in normalized
        for keyword in ["DEBIT", "CREDIT", "BALANCE", "WITHDRAWAL", "DEPOSIT", "UPI", "NEFT", "IMPS"]
    )

    if invoice_score > ledger_score:
        return "invoice"
    if ledger_score > invoice_score:
        return "ledger"
    return "unknown"

def _extract_first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(0).strip() if match else ""

def _extract_amount_value(raw_value: str) -> str:
    cleaned = raw_value.replace(",", "").replace("Rs", "").replace("INR", "").replace(" ", "").strip()
    return cleaned

def _extract_label_value(text: str, labels: list[str]) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        upper_line = line.upper()
        for label in labels:
            # We want to match the label as a whole word, or at least properly.
            # But just simple substring is risky (e.g. "Date" inside "Dated" leaves "d").
            # Let's ensure label is somewhat bounded.
            if re.search(rf"\b{re.escape(label)}\b", line, re.IGNORECASE):
                parts = re.split(rf"\b{re.escape(label)}\b", line, maxsplit=1, flags=re.IGNORECASE)
                if len(parts) > 1:
                    remainder = parts[1]
                    remainder = re.sub(r"^\s*[:\-#]\s*", "", remainder).strip().rstrip(",.")
                    if remainder:
                        return remainder
                # Fallback regex
                tail_match = re.search(rf"\b{re.escape(label)}\b\s*[:\-#]?\s*(.+)$", line, flags=re.IGNORECASE)
                if tail_match:
                    return tail_match.group(1).strip().rstrip(",.")
    return ""

def _extract_invoice_amount(lines: list[str], labels: list[str], is_total: bool = False) -> str | None:
    match_idx = -1
    for i, line in enumerate(lines):
        if any(re.search(rf"\b{re.escape(lbl)}\b", line, re.IGNORECASE) for lbl in labels):
            match_idx = i
            if not is_total:
                break
                
    if match_idx == -1:
        return None
        
    amounts = []
    # Look at the matching line and the next 3 lines for amounts
    for i in range(match_idx, min(len(lines), match_idx + 4)):
        amounts.extend(AMOUNT_PATTERN.findall(lines[i]))
        
    if not amounts:
        return None
        
    parsed = []
    for a in amounts:
        val = _parse_float(_extract_amount_value(a))
        if val is not None:
            parsed.append((a, val))
            
    if not parsed:
        return None
        
    # If any value is > 50, filter out the ones <= 50 (which are likely percentages like 9%, 10%, 18%)
    has_large = any(v > 50 for _, v in parsed)
    if has_large:
        parsed = [(a, v) for a, v in parsed if v > 50]
        
    # Return the last one in the remaining list (as amounts are typically right-aligned at the end)
    return _extract_amount_value(parsed[-1][0])

def _parse_float(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(",", "").strip())
    except ValueError:
        return None

