import re
import io
from PIL import Image
import pytesseract
from fastapi import HTTPException
from .schemas import Template
from .utils import GSTIN_PATTERN, DATE_PATTERN, AMOUNT_PATTERN, _normalize_text, _classify_document, _extract_first_match, _parse_float, _extract_amount_value, _extract_label_value, _extract_invoice_amount

def _extract_invoice_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # --- Supplier GSTIN (first GSTIN-like match near the top) ---
    all_gstins: list[str] = []
    for match in re.finditer(r"(?:GSTIN|GST\s*No|GST\s*Tin\s*No|STN|@STIN)[^A-Z0-9]*([A-Z0-9]{15})", text.upper()):
        all_gstins.append(match.group(1))
    if not all_gstins:
        all_gstins = GSTIN_PATTERN.findall(text.upper())

    if len(all_gstins) >= 1:
        fields["gstin"] = all_gstins[0]
    if len(all_gstins) >= 2:
        fields["buyer_gstin"] = all_gstins[1]

    # --- Invoice Number ---
    invoice_number = _extract_label_value(text, ["Invoice No", "Invoice Number", "Inv No", "Bill No", "Invoice Ne", "INVOICE No"])
    if invoice_number:
        invoice_number = re.split(r"\s{2,}|\n", invoice_number)[0].strip()
        fields["invoice_number"] = invoice_number

    # --- Date ---
    invoice_date = _extract_label_value(text, ["Invoice Date", "Dated", "Date"])
    if not invoice_date:
        invoice_date = _extract_first_match(DATE_PATTERN, text)
    if invoice_date:
        if not DATE_PATTERN.search(invoice_date):
            fallback = _extract_first_match(DATE_PATTERN, text)
            if fallback:
                invoice_date = fallback
        fields["date"] = invoice_date

    # --- Taxable Amount ---
    taxable_amount = _extract_invoice_amount(lines, ["Taxable Amount", "Taxable Value", "Taxable", "Torable Amount"])
    if taxable_amount:
        fields["taxable_amount"] = taxable_amount

    # --- Discount ---
    # Discount needs special handling: the discount line often sits right above the
    # "Taxable Value" line. _extract_invoice_amount would scan forward 4 lines and
    # grab the taxable value (which is larger). Instead, we only look at the matching
    # line itself and one line after, then pick the value that is NOT the taxable amount.
    discount_idx = -1
    for i, line in enumerate(lines):
        if any(re.search(rf"\b{re.escape(lbl)}\b", line, re.IGNORECASE) for lbl in ["Less Discount", "Discount", "Disc"]):
            discount_idx = i
            break
    if discount_idx >= 0:
        disc_amounts: list[tuple[str, float]] = []
        for i in range(discount_idx, min(len(lines), discount_idx + 2)):
            for a in AMOUNT_PATTERN.findall(lines[i]):
                val = _parse_float(_extract_amount_value(a))
                if val is not None and val > 0:
                    disc_amounts.append((_extract_amount_value(a), val))
        # Filter out any value that matches what we already captured as taxable_amount
        taxable_float = _parse_float(fields.get("taxable_amount", "")) or 0.0
        disc_amounts = [(a, v) for a, v in disc_amounts if abs(v - taxable_float) > 1.0]
        # Also filter out tiny percentage-like numbers (<=20) if we have a proper amount
        has_proper = any(v > 20 for _, v in disc_amounts)
        if has_proper:
            disc_amounts = [(a, v) for a, v in disc_amounts if v > 20]
        if disc_amounts:
            # Pick the smallest remaining value (the actual discount, not some sub-total)
            disc_amounts.sort(key=lambda x: x[1])
            fields["discount"] = disc_amounts[0][0]

    # --- Tax Components ---
    cgst = _extract_invoice_amount(lines, ["CGST", "casr", "cssr", "C6ST"])
    if cgst: fields["cgst"] = cgst
        
    sgst = _extract_invoice_amount(lines, ["SGST", "sast", "S6ST", "sgsf"])
    if sgst: fields["sgst"] = sgst
        
    igst = _extract_invoice_amount(lines, ["IGST", "1GST", "I6ST"])
    if igst: fields["igst"] = igst

    total = _extract_invoice_amount(lines, ["Grand Total", "Total", "Toa", "Talat", "Amount Chargeable"], is_total=True)
    if total: fields["total"] = total

    # --- Vendor Name (Supplier) ---
    # Strategy: find the line immediately before the first GSTIN mention in the text.
    # That line is almost always the company header. If it is "Bill to" or similar,
    # fall back to scanning the first 5 non-keyword lines.
    vendor_name = ""
    first_gstin_match = re.search(r"(?:GSTIN|GST\s*No)[^A-Z0-9]*[A-Z0-9]{15}", text.upper())
    if first_gstin_match:
        gstin_pos = first_gstin_match.start()
        # Walk backwards through lines to find the line just before this GSTIN
        char_count = 0
        for line in lines:
            line_end = char_count + len(line) + 1  # +1 for newline
            if line_end >= gstin_pos:
                break
            char_count = line_end
        # Now search upward from that position for a line that looks like a company name
        before_gstin_lines = [l.strip() for l in text[:gstin_pos].splitlines() if l.strip()]
        for candidate in reversed(before_gstin_lines[-5:]):
            upper_cand = candidate.upper()
            # Skip labels and addresses
            if any(token in upper_cand for token in ["BILL TO", "BILL", "PLACE OF SUPPLY", "ADDRESS", "CONTACT", "1D-", "BENGALURU", "KARNATAKA", "INDIA", "FLOOR"]):
                continue
            if any(token in upper_cand for token in ["GSTIN", "GST NO", "TAX INVOICE", "INVOICE"]):
                continue
            if len(candidate) >= 3:
                vendor_name = candidate
                break
    if not vendor_name:
        # Fallback: first non-keyword line in the document
        for line in lines[:5]:
            upper_line = line.upper()
            if any(token in upper_line for token in ["GSTIN", "INVOICE", "BILL", "DATE", "TOTAL", "CGST", "SGST", "IGST", "TAX"]):
                continue
            if len(line) >= 3:
                vendor_name = line
                break
    if vendor_name:
        fields["vendor_name"] = vendor_name

    # --- Buyer Name ---
    # Look for the "Bill to" section and grab the next non-empty, non-address line
    bill_to_idx = -1
    for i, line in enumerate(lines):
        if re.search(r"\bBill\s*to\b", line, re.IGNORECASE):
            bill_to_idx = i
            break
    if bill_to_idx >= 0:
        for j in range(bill_to_idx, min(len(lines), bill_to_idx + 4)):
            candidate = lines[j]
            # Skip the "Bill to" label line itself if it has nothing else
            cleaned = re.sub(r"(?i)\bbill\s*to\b", "", candidate).strip().rstrip(":")
            if not cleaned:
                continue
            upper_cand = cleaned.upper()
            if any(token in upper_cand for token in ["GSTIN", "GST", "ADDRESS", "FLOOR", "BENGALURU", "KARNATAKA", "INDIA", "PLACE"]):
                continue
            if len(cleaned) >= 2:
                fields["buyer_name"] = cleaned
                break

    # --- Infer Total if missing ---
    if "total" not in fields:
        taxable = _parse_float(fields.get("taxable_amount", "")) or 0.0
        cgst_val = _parse_float(fields.get("cgst", "")) or 0.0
        sgst_val = _parse_float(fields.get("sgst", "")) or 0.0
        igst_val = _parse_float(fields.get("igst", "")) or 0.0
        if taxable > 0:
            fields["total"] = f"{taxable + cgst_val + sgst_val + igst_val:.2f}"

    return fields

def _extract_invoice_line_items(text: str) -> list[dict[str, str]]:
    """Extract invoice line items from OCR text.
    
    PyMuPDF's get_text("text") often splits table columns across separate lines.
    For example, a single visual row like:
        LED LIGHTS   85013410   50   pcs   500   25000
    might become multiple lines:
        LED LIGHTS
        85013410
        50
        pcs
        500
        25000
    
    Strategy: 
    1. Find the table zone (between the header row and the summary lines).
    2. Within that zone, look for HSN codes (8-digit numbers like 85013410).
    3. For each HSN code found, look at surrounding lines to collect the
       description (text before the HSN), and amounts (numbers after it).
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    items: list[dict[str, str]] = []

    hsn_pattern = re.compile(r"\b(\d{4,8})\b")
    
    # --- Phase 1: Find the table zone boundaries ---
    table_start = -1
    table_end = len(lines)
    
    header_keywords_a = ["HSN", "DESCRIPTION", "PARTICULARS", "SERVICE"]
    header_keywords_b = ["QTY", "RATE", "AMOUNT", "CODE"]
    summary_keywords = ["TAXABLE", "LESS DISC", "DISCOUNT", "SUB TOTAL", "SUBTOTAL", 
                         "CGST", "SGST", "IGST", "GRAND TOTAL", "AMOUNT CHARGEABLE",
                         "COMPANY"]
    
    for i, line in enumerate(lines):
        upper = line.upper()
        # Detect header: look for keywords within a window of 3 consecutive lines
        if table_start == -1:
            window = " ".join(lines[i:i+3]).upper()
            if any(kw in window for kw in header_keywords_a) and any(kw in window for kw in header_keywords_b):
                table_start = i + 1  # start capturing after the header
                continue
    
    if table_start == -1:
        # No explicit header found; try scanning for HSN-code-bearing lines anywhere
        for i, line in enumerate(lines):
            hsn_matches = hsn_pattern.findall(line)
            for h in hsn_matches:
                if 6 <= len(h) <= 8:  # strong HSN signal
                    table_start = max(0, i - 2)
                    break
            if table_start >= 0:
                break

    if table_start == -1:
        return items  # no table found at all
    
    # Find where the table ends (first summary keyword after the table starts)
    for i in range(table_start, len(lines)):
        upper = lines[i].upper()
        # "Total" alone on a line with a large number = row subtotal, skip unless it's a summary keyword
        if any(kw in upper for kw in summary_keywords):
            table_end = i
            break
        # Also stop at standalone "Total" if it looks like a summary row
        if re.match(r"^\s*Total\s*$", lines[i], re.IGNORECASE):
            table_end = i
            break
    
    table_lines = lines[table_start:table_end]
    
    # --- Phase 2: Try single-line extraction first (each line has HSN + amounts) ---
    for line in table_lines:
        all_numbers = AMOUNT_PATTERN.findall(line)
        hsn_matches = hsn_pattern.findall(line)
        
        if len(all_numbers) >= 2 and hsn_matches:
            item: dict[str, str] = {}
            
            hsn_code = ""
            for h in hsn_matches:
                if 4 <= len(h) <= 8:
                    hsn_code = h
                    break
            item["hsn_code"] = hsn_code

            desc_part = re.split(r"\d{4,}", line, maxsplit=1)[0].strip()
            if not desc_part:
                desc_part = re.split(r"\s+\d", line, maxsplit=1)[0].strip()
            item["description"] = desc_part

            item["amount"] = _extract_amount_value(all_numbers[-1])
            if len(all_numbers) >= 3:
                item["rate"] = _extract_amount_value(all_numbers[-2])
                item["quantity"] = _extract_amount_value(all_numbers[-3]) if len(all_numbers) >= 4 else ""
            else:
                item["rate"] = _extract_amount_value(all_numbers[-2])
                item["quantity"] = ""

            unit_match = re.search(r"\b(pcs|nos|kg|gm|ltr|dozen|dozens|pairs?|sets?|units?|mtrs?|sqft)\b", line, re.IGNORECASE)
            item["unit"] = unit_match.group(0) if unit_match else ""

            if item.get("description") or item.get("hsn_code"):
                items.append(item)

    if items:
        return items  # single-line extraction succeeded
    
    # --- Phase 3: Multi-line reconstruction ---
    # When PDF text splits columns, we look for HSN codes and reconstruct rows
    # by gathering the description line(s) before and the amount lines after.
    i = 0
    while i < len(table_lines):
        line = table_lines[i]
        hsn_matches = hsn_pattern.findall(line)
        
        # Look for a line that contains an HSN-like code (6-8 digits)
        strong_hsn = [h for h in hsn_matches if 6 <= len(h) <= 8]
        if not strong_hsn:
            i += 1
            continue
        
        hsn_code = strong_hsn[0]
        item: dict[str, str] = {"hsn_code": hsn_code}
        
        # Look backwards for description text (non-numeric lines before this HSN)
        desc_parts: list[str] = []
        for j in range(i - 1, max(-1, i - 4), -1):
            prev_line = table_lines[j]
            # If the previous line is mostly text (not numbers), it's probably a description
            text_content = re.sub(r"[\d,.\s]+", "", prev_line).strip()
            if len(text_content) >= 2 and not hsn_pattern.search(prev_line):
                desc_parts.insert(0, prev_line)
            else:
                break
        item["description"] = " ".join(desc_parts).strip()
        
        # Look forward for amounts (qty, unit, rate, amount)
        forward_amounts: list[str] = []
        forward_units: list[str] = []
        # Also collect from the HSN line itself
        for a in AMOUNT_PATTERN.findall(line):
            val = _extract_amount_value(a)
            if val != hsn_code:
                forward_amounts.append(val)
        
        for j in range(i + 1, min(len(table_lines), i + 6)):
            next_line = table_lines[j]
            # Stop if we hit another HSN code or another description block
            if hsn_pattern.search(next_line):
                next_hsn = [h for h in hsn_pattern.findall(next_line) if 6 <= len(h) <= 8]
                if next_hsn:
                    break
            
            # Check for unit keywords
            unit_match = re.search(r"\b(pcs|nos|kg|gm|ltr|dozen|dozens|pairs?|sets?|units?|mtrs?|sqft)\b", next_line, re.IGNORECASE)
            if unit_match:
                forward_units.append(unit_match.group(0))
            
            for a in AMOUNT_PATTERN.findall(next_line):
                forward_amounts.append(_extract_amount_value(a))
        
        if forward_amounts:
            item["amount"] = forward_amounts[-1]
            if len(forward_amounts) >= 2:
                item["rate"] = forward_amounts[-2]
            else:
                item["rate"] = ""
            if len(forward_amounts) >= 3:
                item["quantity"] = forward_amounts[-3]
            else:
                item["quantity"] = ""
        else:
            item["amount"] = ""
            item["rate"] = ""
            item["quantity"] = ""
        
        item["unit"] = forward_units[0] if forward_units else ""
        
        if item.get("description") or item.get("hsn_code"):
            items.append(item)
        
        i += 1

    return items

def _split_amount_tokens(text: str) -> list[str]:
    return [_extract_amount_value(match.group(1)) for match in AMOUNT_PATTERN.finditer(text)]

def _extract_ledger_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        date_match = DATE_PATTERN.search(line)
        if not date_match:
            continue

        date_value = date_match.group(0)
        remainder = line[date_match.end():].strip()
        amounts = _split_amount_tokens(remainder)
        description = remainder
        debit = ""
        credit = ""
        balance = ""

        if amounts:
            balance = amounts[-1]
            numeric_portion = amounts[:-1]
            description = re.sub(AMOUNT_PATTERN, "", remainder).strip(" -:|")

            upper_line = line.upper()
            if any(token in upper_line for token in ["CREDIT", "CR", "DEPOSIT", "UPI CREDIT", "SALARY", "REFUND"]):
                if numeric_portion:
                    credit = numeric_portion[0]
            elif any(token in upper_line for token in ["DEBIT", "DR", "WITHDRAWAL", "ATM", "PAYMENT", "CHARGE"]):
                if numeric_portion:
                    debit = numeric_portion[0]
            elif len(numeric_portion) == 2:
                debit, credit = numeric_portion[0], numeric_portion[1]
            elif len(numeric_portion) == 1:
                credit = numeric_portion[0]

        rows.append(
            {
                "date": date_value,
                "description": _normalize_text(description),
                "debit": debit,
                "credit": credit,
                "balance": balance,
            }
        )

    return rows

def _process_with_template(image: Image.Image, template: Template) -> tuple[dict[str, str], list[dict[str, str]], str]:
    scale_x = image.width / template.reference_image.width
    scale_y = image.height / template.reference_image.height
    
    fields: dict[str, str] = {}
    for field in template.fields:
        x = int(field.box.x * scale_x)
        y = int(field.box.y * scale_y)
        w = int(field.box.w * scale_x)
        h = int(field.box.h * scale_y)
        
        region = image.crop((x, y, x + w, y + h))
        processed_region = _preprocess_image(region)
        text, _ = _ocr_image(processed_region)
        
        if field.regex:
            match = re.search(field.regex, text)
            if match:
                text = match.group(0)
        fields[field.id] = text

    rows: list[dict[str, str]] = []
    for table in template.tables:
        x = int(table.bounding_box.x * scale_x)
        y = int(table.bounding_box.y * scale_y)
        w = int(table.bounding_box.w * scale_x)
        h = int(table.bounding_box.h * scale_y)
        
        region = image.crop((x, y, x + w, y + h))
        processed_region = _preprocess_image(region)
        
        _configure_tesseract()
        try:
            df = pytesseract.image_to_data(processed_region, output_type=pytesseract.Output.DICT)
        except Exception:
            continue
            
        n_boxes = len(df['text'])
        words = []
        for i in range(n_boxes):
            if int(df['conf'][i]) > -1 and df['text'][i].strip():
                w_x = df['left'][i]
                text = df['text'][i]
                
                scaled_w_x = w_x / scale_x
                col_id = None
                for col in table.columns:
                    if col.x_start <= scaled_w_x <= col.x_end:
                        col_id = col.id
                        break
                
                if col_id:
                    words.append({
                        "col": col_id,
                        "text": text,
                        "line_num": df['line_num'][i],
                        "par_num": df['par_num'][i],
                        "block_num": df['block_num'][i]
                    })
        
        grouped_lines = {}
        for w in words:
            key = (w['block_num'], w['par_num'], w['line_num'])
            if key not in grouped_lines:
                grouped_lines[key] = {}
            if w['col'] not in grouped_lines[key]:
                grouped_lines[key][w['col']] = []
            grouped_lines[key][w['col']].append(w['text'])
            
        for key, cols in grouped_lines.items():
            row_dict = {}
            for col_id, texts in cols.items():
                row_dict[col_id] = " ".join(texts)
            
            row_dict.setdefault("date", "")
            row_dict.setdefault("description", "")
            row_dict.setdefault("debit", "")
            row_dict.setdefault("credit", "")
            row_dict.setdefault("balance", "")
            if any(v for k, v in row_dict.items() if k in ["date", "description", "debit", "credit", "balance"]):
                rows.append(row_dict)
                
    raw_text = "Template-based extraction. Raw text not available for full page."
    return fields, rows, raw_text

