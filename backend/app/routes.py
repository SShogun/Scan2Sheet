import csv
import io
import uuid
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse
from .schemas import ExtractResponse, Template, InvoiceLineItem
from .store import templates_db
from .ocr import _decode_image, _preprocess_image, _ocr_image
from .extractors import _classify_document, _extract_invoice_fields, _extract_invoice_line_items, _extract_ledger_rows, _process_with_template
from .validators import _build_warnings, _compute_confidence

router = APIRouter()

@router.post("/api/templates", response_model=Template)
def create_template(template: Template) -> Template:
    if not template.template_id:
        template.template_id = f"tpl_{uuid.uuid4().hex[:8]}"
    templates_db[template.template_id] = template
    return template

@router.get("/api/templates", response_model=list[Template])
def get_templates() -> list[Template]:
    return list(templates_db.values())

@router.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "scan2sheet-local-api"}

@router.post("/api/extract", response_model=ExtractResponse)
async def extract_document(
    file: UploadFile = File(...), 
    template_id: str | None = Form(None)
) -> ExtractResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="A file is required.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()
    ocr_confidence = 100.0

    is_pdf = filename.endswith(".pdf") or "pdf" in content_type
    is_spreadsheet = filename.endswith((".csv", ".xls", ".xlsx")) or content_type in (
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    
    if is_pdf:
        import pymupdf
        import traceback
        try:
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            raw_text = ""
            for page in doc:
                raw_text += page.get_text("text") + "\n"
            doc.close()
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {repr(e)}")

        # If the PDF is a scanned image (no selectable text), fall back to OCR
        stripped = raw_text.strip()
        if len(stripped) < 20:
            try:
                doc = pymupdf.open(stream=file_bytes, filetype="pdf")
                page = doc[0]
                pix = page.get_pixmap(dpi=300)
                img_bytes = pix.tobytes("png")
                doc.close()
                image = _decode_image(img_bytes)
                preprocessed_image = _preprocess_image(image)
                raw_text, ocr_confidence = _ocr_image(preprocessed_image)
            except Exception as e:
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"PDF OCR fallback failed: {repr(e)}")
        
        document_type = _classify_document(raw_text)
        fields: dict[str, str] = {}
        rows: list[dict[str, str]] = []
        line_items: list[dict[str, str]] = []
        if document_type == "invoice":
            fields = _extract_invoice_fields(raw_text)
            line_items = _extract_invoice_line_items(raw_text)
        elif document_type == "ledger":
            rows = _extract_ledger_rows(raw_text)

    elif is_spreadsheet:
        import pandas as pd
        try:
            if filename.endswith(".csv") or "csv" in content_type:
                df = pd.read_csv(io.BytesIO(file_bytes))
            else:
                df = pd.read_excel(io.BytesIO(file_bytes))
            raw_text = df.to_markdown(index=False)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse spreadsheet: {e}")
            
        document_type = _classify_document(raw_text)
        fields: dict[str, str] = {}
        rows: list[dict[str, str]] = []
        line_items: list[dict[str, str]] = []
        if document_type == "invoice":
            fields = _extract_invoice_fields(raw_text)
            line_items = _extract_invoice_line_items(raw_text)
        elif document_type == "ledger":
            rows = _extract_ledger_rows(raw_text)

    else:
        # Image handling
        image = _decode_image(file_bytes)
        
        if template_id and template_id in templates_db:
            template = templates_db[template_id]
            fields, rows, raw_text = _process_with_template(image, template)
            document_type = template.doc_type
            line_items = []
        else:
            preprocessed_image = _preprocess_image(image)
            raw_text, ocr_confidence = _ocr_image(preprocessed_image)
            document_type = _classify_document(raw_text)
            
            fields: dict[str, str] = {}
            rows: list[dict[str, str]] = []
            line_items: list[dict[str, str]] = []
            if document_type == "invoice":
                fields = _extract_invoice_fields(raw_text)
                line_items = _extract_invoice_line_items(raw_text)
            elif document_type == "ledger":
                rows = _extract_ledger_rows(raw_text)

    # Append a structured table to the raw text for readability
    import pandas as pd
    formatted_table = "### Extracted Structured Data (Table Format)\n\n"
    if fields:
        df = pd.DataFrame(list(fields.items()), columns=["Field", "Value"])
        formatted_table += df.to_markdown(index=False) + "\n\n"
    if line_items:
        formatted_table += "### Invoice Line Items\n\n"
        df = pd.DataFrame(line_items)
        formatted_table += df.to_markdown(index=False) + "\n\n"
    elif rows:
        df = pd.DataFrame(rows)
        formatted_table += df.to_markdown(index=False) + "\n\n"
    
    formatted_table += "### Original Output\n\n"
    raw_text = formatted_table + raw_text

    warnings = _build_warnings(document_type, fields, rows, line_items)


    warnings = _build_warnings(document_type, fields, rows, line_items)
    confidence_overall = _compute_confidence(ocr_confidence, fields, rows)

    # Convert line_items dicts into InvoiceLineItem models
    line_item_models = [InvoiceLineItem(**item) for item in line_items]

    return ExtractResponse(
        document_type=document_type,
        raw_text=raw_text,
        fields=fields,
        rows=rows,
        line_items=line_item_models,
        warnings=warnings,
        confidence={"overall": confidence_overall},
    )

@router.post("/api/export/csv")
def export_csv(payload: ExtractResponse) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    if payload.document_type == "ledger":
        writer.writerow(["date", "description", "debit", "credit", "balance"])
        for row in payload.rows:
            writer.writerow([row.date, row.description, row.debit, row.credit, row.balance])
    else:
        writer.writerow(["field", "value"])
        preferred_fields = [
            "gstin",
            "buyer_gstin",
            "invoice_number",
            "date",
            "vendor_name",
            "buyer_name",
            "discount",
            "taxable_amount",
            "cgst",
            "sgst",
            "igst",
            "total",
        ]

        written_fields: set[str] = set()
        for field_name in preferred_fields:
            writer.writerow([field_name, payload.fields.get(field_name, "")])
            written_fields.add(field_name)

        for field_name, field_value in payload.fields.items():
            if field_name not in written_fields:
                writer.writerow([field_name, field_value])

        # Append line items if present
        if payload.line_items:
            writer.writerow([])
            writer.writerow(["--- LINE ITEMS ---"])
            writer.writerow(["description", "hsn_code", "quantity", "unit", "rate", "amount"])
            for item in payload.line_items:
                writer.writerow([item.description, item.hsn_code, item.quantity, item.unit, item.rate, item.amount])

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="scan2sheet-export.csv"'},
    )

@router.post("/api/export/tally")
def export_tally_xml(payload: ExtractResponse) -> StreamingResponse:
    date_val = payload.fields.get("date", "20240101").replace("-", "").replace("/", "")
    party = payload.fields.get("vendor_name", "Unknown Vendor")
    total = payload.fields.get("total", "0")
    invoice_no = payload.fields.get("invoice_number", "INV001")

    xml_content = f"""<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>Vouchers</REPORTNAME>
      </REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE>
          <VOUCHER VCHTYPE="Purchase" ACTION="Create">
            <DATE>{date_val}</DATE>
            <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
            <VOUCHERNUMBER>{invoice_no}</VOUCHERNUMBER>
            <PARTYLEDGERNAME>{party}</PARTYLEDGERNAME>
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>{party}</LEDGERNAME>
              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
              <AMOUNT>{total}</AMOUNT>
            </ALLLEDGERENTRIES.LIST>
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>Purchases</LEDGERNAME>
              <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
              <AMOUNT>-{payload.fields.get("taxable_amount", total)}</AMOUNT>
            </ALLLEDGERENTRIES.LIST>"""

    for tax_key in ["cgst", "sgst", "igst"]:
        tax_amt = payload.fields.get(tax_key, "0")
        if tax_amt and tax_amt != "0":
            xml_content += f"""
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>{tax_key.upper()}</LEDGERNAME>
              <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
              <AMOUNT>-{tax_amt}</AMOUNT>
            </ALLLEDGERENTRIES.LIST>"""

    xml_content += """
          </VOUCHER>
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>"""

    return StreamingResponse(
        iter([xml_content]),
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="scan2sheet-tally.xml"'},
    )

