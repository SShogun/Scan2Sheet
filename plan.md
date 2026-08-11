# Scan2Sheet Local - Project Plan

## 1. Project Summary

Scan2Sheet Local is a free, local-first OCR project for Indian accounting documents.

The app lets a user upload or scan an invoice, bill, ledger page, or passbook-style document. It then runs local OCR, extracts useful accounting data, validates the extracted values, lets the user review and correct mistakes, and exports clean CSV/Excel-ready data.

This is not a generic OCR tool. The core idea is:

```text
Indian accounting documents -> OCR -> structured data -> validation -> human review -> CSV export
```

## 2. Hard Constraints

The MVP must follow these constraints:

- No paid APIs.
- No Chinese LLMs.
- No Chinese OCR engines.
- No Chinese cloud AI services.
- No Chinese open-source AI models in the core pipeline.
- Prefer local, free, auditable open-source tools.
- The project should work without relying on internet-based AI.
- The demo should still work even if OCR accuracy is imperfect.

## 3. Allowed Initial Stack

### Frontend

- React
- Vite
- PWA-friendly web app
- Plain CSS or lightweight UI styling

### Backend

- Python
- FastAPI
- Local file upload handling

### OCR and Processing

- Tesseract OCR
- pytesseract
- OpenCV
- Pillow

### Data and Export

- Python `csv`
- pandas, optional
- openpyxl, optional for XLSX

### Simple Intelligence

- Rule-based classifier first
- Regex extraction
- Validation rules
- Optional later: scikit-learn TF-IDF classifier

## 4. MVP Scope

The MVP should support only two document types.

### Document Type 1: GST Invoice / Bill

Extract:

- GSTIN
- Invoice number
- Invoice date
- Vendor or business name, if obvious
- Taxable amount
- CGST
- SGST
- IGST
- Grand total

Validate:

- GSTIN format
- Date format
- Required fields
- Tax math
- Total amount consistency

### Document Type 2: Ledger / Passbook Page

Extract transaction rows:

- Date
- Description
- Debit
- Credit
- Balance

Validate:

- Missing dates
- Invalid amounts
- Both debit and credit filled in the same row
- Neither debit nor credit filled
- Running balance mismatch, where possible

## 5. Main User Flow

```text
User opens app
  ↓
Uploads or scans document image
  ↓
App shows image preview
  ↓
User clicks "Extract"
  ↓
Backend preprocesses image
  ↓
Tesseract runs OCR locally
  ↓
Backend classifies document type
  ↓
Backend extracts structured fields or rows
  ↓
Backend validates extracted values
  ↓
Frontend shows editable review table
  ↓
User corrects mistakes
  ↓
User exports CSV
```

## 6. Backend API Contract

All extraction responses should follow this shape:

```json
{
  "document_type": "invoice",
  "raw_text": "Raw OCR text here",
  "fields": {
    "gstin": "27ABCDE1234F1Z5",
    "invoice_number": "INV-102",
    "date": "12/04/2025",
    "taxable_amount": "10000",
    "cgst": "900",
    "sgst": "900",
    "igst": "",
    "total": "11800"
  },
  "rows": [],
  "warnings": [
    {
      "level": "warning",
      "field": "total",
      "message": "Total does not match taxable amount plus tax."
    }
  ],
  "confidence": {
    "overall": 0.72
  }
}
```

For ledger/passbook documents:

```json
{
  "document_type": "ledger",
  "raw_text": "Raw OCR text here",
  "fields": {},
  "rows": [
    {
      "date": "12/04/2025",
      "description": "UPI CREDIT FROM RAHUL",
      "debit": "",
      "credit": "5000",
      "balance": "21500"
    }
  ],
  "warnings": [],
  "confidence": {
    "overall": 0.68
  }
}
```

## 7. Required Backend Endpoints

```text
GET /api/health
```

Checks whether the backend is running.

```text
POST /api/extract
```

Accepts an uploaded image and returns OCR text, structured data, warnings, and confidence.

```text
POST /api/export/csv
```

Accepts corrected structured data and returns a CSV file.

## 8. OCR Pipeline

The local OCR pipeline should be:

```text
uploaded image
  ↓
load with OpenCV
  ↓
grayscale
  ↓
denoise
  ↓
threshold
  ↓
optional deskew
  ↓
Tesseract OCR
  ↓
raw text + confidence
```

The first version can be simple. Reliability can improve later.

## 9. Extraction Logic

### Document Classifier

Start with keyword scoring.

Invoice signals:

- GSTIN
- Invoice
- Bill
- Tax
- CGST
- SGST
- IGST
- Total

Ledger/passbook signals:

- Debit
- Credit
- Balance
- Withdrawal
- Deposit
- UPI
- NEFT
- IMPS

If invoice score is higher, classify as invoice.

If ledger score is higher, classify as ledger.

Otherwise classify as unknown.

### Invoice Parser

Use regex and nearby keywords.

GSTIN regex:

```regex
[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]
```

Date patterns:

```text
12/04/2025
12-04-2025
12.04.2025
12 Apr 2025
```

Amount patterns:

```text
1,180.00
1180
Rs. 1180
INR 1180
```

Look for labels:

- Invoice No
- Inv No
- Bill No
- Date
- Taxable Amount
- CGST
- SGST
- IGST
- Grand Total
- Total

### Ledger Parser

Split OCR text into lines.

For each line:

- Detect date.
- Detect amount-like tokens.
- Treat middle text as description.
- Assign last one to balance if the line has multiple amounts.
- Infer debit/credit based on nearby words or column labels.

This will not be perfect, but it is enough for a believable MVP.

## 10. Validation Rules

### Invoice Validation

Required checks:

- GSTIN exists.
- GSTIN format is valid.
- Invoice date exists.
- Total exists.
- At least one tax value or taxable amount exists.

Math check:

```text
taxable_amount + cgst + sgst + igst ~= total
```

Use a small tolerance, for example `1.00`, because OCR and rounding may create minor differences.

### Ledger Validation

Checks:

- Date exists for each transaction row.
- Debit and credit are not both filled.
- At least one of debit or credit is filled.
- Amounts are numeric.
- Balance is numeric.
- Running balance roughly matches previous row if enough data is available.

## 11. Frontend Layout

The app should open directly into the usable product, not a marketing page.

Recommended layout:

```text
Top bar:
  Scan2Sheet Local

Left panel:
  Upload button
  Image preview
  Extract button
  Raw OCR text toggle

Right panel:
  Document type badge
  Warnings
  Editable extracted fields or rows
  Revalidate button
  Export CSV button
```

States:

- Idle
- File selected
- Processing
- Extracted
- Error

## 12. CSV Export Format

### Invoice CSV

```csv
field,value
gstin,27ABCDE1234F1Z5
invoice_number,INV-102
date,12/04/2025
taxable_amount,10000
cgst,900
sgst,900
igst,
total,11800
```

### Ledger CSV

```csv
date,description,debit,credit,balance
12/04/2025,UPI CREDIT FROM RAHUL,,5000,21500
13/04/2025,ATM WITHDRAWAL,2000,,19500
```

## 13. 24-Hour Development Timeline

### Hour 0-1: Scope Lock

Tasks:

- Confirm MVP scope.
- Create folder structure.
- Collect sample invoice and ledger/passbook images.
- Decide exact JSON schema.

Output:

- Project skeleton.
- Sample files.
- This `plan.md`.

### Hour 1-3: Backend Skeleton

Tasks:

- Create FastAPI app.
- Add `/api/health`.
- Add `/api/extract`.
- Accept image upload.
- Return placeholder JSON.

Output:

- Backend runs locally.
- Upload endpoint works.

### Hour 3-5: OCR Pipeline

Tasks:

- Add OpenCV preprocessing.
- Add Tesseract OCR call.
- Return raw OCR text.
- Return approximate OCR confidence if available.

Output:

- Uploaded image produces raw text.

### Hour 5-7: Invoice Parser

Tasks:

- Add invoice keyword classifier.
- Extract GSTIN.
- Extract date.
- Extract invoice number.
- Extract tax and total values.

Output:

- One sample invoice produces structured fields.

### Hour 7-9: Ledger Parser

Tasks:

- Add ledger keyword classifier.
- Split OCR text into lines.
- Detect date and amount tokens.
- Build transaction rows.

Output:

- One ledger/passbook sample produces rows.

### Hour 9-11: Validation Engine

Tasks:

- Add GSTIN validation.
- Add invoice total validation.
- Add date and amount validation.
- Add ledger row validation.

Output:

- Warnings appear for suspicious or missing values.

### Hour 11-14: Frontend

Tasks:

- Create React app.
- Add upload UI.
- Add image preview.
- Call backend extraction endpoint.
- Show raw OCR text.

Output:

- User can upload and inspect OCR result from UI.

### Hour 14-16: Editable Review UI

Tasks:

- Render invoice fields as editable table.
- Render ledger rows as editable table.
- Allow adding/deleting rows.
- Re-run validation after edits.

Output:

- Human correction workflow works.

### Hour 16-18: CSV Export

Tasks:

- Add CSV export for invoice.
- Add CSV export for ledger.
- Download CSV from browser.

Output:

- User can download clean extracted data.

### Hour 18-20: Demo Reliability

Tasks:

- Add sample invoice button.
- Add sample ledger button.
- Add fallback extracted JSON.
- Improve error messages.

Output:

- Demo still works even if OCR fails on a live image.

### Hour 20-22: Polish

Tasks:

- Improve UI spacing.
- Add loading states.
- Add warning badges.
- Add confidence display.
- Add concise project explanation in README.

Output:

- App feels intentional and demo-ready.

### Hour 22-24: Final Test and Pitch

Tasks:

- Test clean invoice.
- Test blurry invoice.
- Test ledger/passbook page.
- Test invalid GSTIN.
- Test CSV export.
- Prepare demo script.

Output:

- Final demo build.
- Pitch-ready workflow.

## 14. Agent Supervisor Breakdown

If multiple agents or AIs work on this project, split work like this.

### Agent 1: Backend/OCR

Responsible for:

- FastAPI app setup.
- Upload endpoint.
- Image preprocessing.
- Tesseract OCR integration.
- Returning raw OCR text and confidence.

Must not:

- Add paid APIs.
- Add cloud AI.
- Add Chinese OCR dependencies.

### Agent 2: Extraction/Validation

Responsible for:

- Document classifier.
- Invoice parser.
- Ledger parser.
- GSTIN regex.
- Date parsing.
- Amount parsing.
- Validation warnings.

Must follow:

- Shared JSON response shape.
- Minimal deterministic logic first.

### Agent 3: Frontend

Responsible for:

- Upload UI.
- Image preview.
- Extraction call.
- Editable fields.
- Editable ledger table.
- Warnings UI.
- CSV export button.

Must prioritize:

- Clear workflow.
- Fast demo.
- No unnecessary screens.

### Agent 4: Demo/Docs

Responsible for:

- Sample documents.
- README.
- Pitch script.
- Fallback JSON.
- Known limitations.
- Dependency notes.

Must explain:

- Local-first.
- Free stack.
- No Chinese AI dependencies.
- Accounting validation value.

## 15. Definition of Done

The MVP is done when:

- The app starts locally.
- The user can upload an image.
- The uploaded image is previewed.
- OCR runs locally.
- Raw OCR text is visible.
- At least one invoice can be parsed into fields.
- At least one ledger/passbook page can be parsed into rows.
- Validation warnings appear.
- User can edit extracted data.
- User can export CSV.
- The core pipeline uses no paid APIs or Chinese AI/model dependencies.

## 16. Demo Script

Use this flow:

1. Explain the problem: Indian small businesses and CAs manually type invoices, bills, ledgers, and passbooks into spreadsheets.
2. Open Scan2Sheet Local.
3. Upload a GST invoice.
4. Show image preview.
5. Run extraction.
6. Show raw OCR text to prove local OCR is working.
7. Show structured extracted fields.
8. Show validation warnings.
9. Edit one incorrect field.
10. Export CSV.
11. Upload a ledger/passbook page.
12. Show extracted transaction rows.
13. Export ledger CSV.

Pitch line:

```text
Scan2Sheet Local converts Indian accounting documents into verified spreadsheet-ready data using a free, local-first OCR pipeline with no paid or Chinese AI dependencies.
```

## 17. Known MVP Limitations

Be honest about these:

- OCR accuracy depends on image quality.
- Handwriting may fail.
- Complex invoice tables may not parse perfectly.
- Ledger/passbook column detection is basic.
- No database in the MVP.
- No real Tally integration yet.
- No batch processing yet.
- No mobile-native app yet.

These are acceptable for a hackathon MVP because the core pipeline still works end to end.

## 18. Future Roadmap

### Phase 1: MVP Hardening

Add:

- PDF support.
- Multi-page support.
- Auto-rotation.
- Deskewing.
- Blur detection.
- Better thresholding.
- XLSX export.

### Phase 2: Better Document Classification

Add:

- Invoice vs receipt vs ledger vs passbook vs unknown.
- Keyword classifier first.
- Later local scikit-learn classifier using TF-IDF.

### Phase 3: Better Table Extraction

Add:

- Tesseract word bounding boxes.
- Line grouping by y-coordinate.
- Column grouping by x-coordinate.
- Row confidence.
- Manual table correction.

### Phase 4: Stronger Accounting Validation

Add:

- Duplicate invoice detection.
- HSN/SAC extraction.
- CGST/SGST/IGST logic.
- Opening and closing balance checks.
- Date ordering checks.
- Suspicious amount jumps.

### Phase 5: Review Workflow

Add:

- Click extracted field to highlight source text.
- Confidence colors.
- Keyboard table editing.
- Undo/redo.
- Approve document button.

### Phase 6: Template Learning

Add local templates for repeated vendors or banks.

Example:

```json
{
  "template_name": "ABC Traders Invoice",
  "document_type": "invoice",
  "field_patterns": {
    "invoice_number": "Invoice No[: ]+(.*)",
    "total": "Grand Total[: ]+([0-9,.]+)"
  }
}
```

### Phase 7: Export Integrations

Add:

- XLSX.
- JSON.
- Tally-compatible CSV.
- Tally XML later.
- GST filing preparation formats.

### Phase 8: Privacy and Local-First Productization

Add:

- Offline mode.
- Local processing logs.
- Auto-delete uploaded files.
- Optional encrypted local history.
- Clear privacy messaging.

### Phase 9: Mobile App

Path:

1. PWA first.
2. React Native / Expo later.
3. Fully on-device OCR only if needed.

Mobile features:

- Camera scan.
- Auto-crop.
- Retake if blurry.
- Batch scan.
- Review/edit data.
- Share CSV.

### Phase 10: Accuracy Metrics

Track locally:

- OCR confidence.
- Extracted field count.
- User-edited field count.
- Validation failure count.
- Time saved.

Useful metric:

```text
automation_rate = fields accepted without edit / total fields
```

## 19. Long-Term Product Vision

The mature product can become a local-first accounting document processor for Indian small businesses and CAs.

It should eventually:

- Scan invoices.
- Scan receipts.
- Scan ledgers.
- Scan passbooks.
- Extract structured data.
- Validate accounting logic.
- Learn repeated templates.
- Export to Excel, Tally, and GST workflows.
- Keep documents private by processing locally.

## 20. Product Positioning

Do not position this as "just OCR."

Position it as:

```text
Verified OCR for Indian accounting workflows.
```

The value is:

- Local-first privacy.
- Free stack.
- India-specific fields.
- Accounting validation.
- Human correction.
- Export-ready data.
