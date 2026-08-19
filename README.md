# Scan2Sheet Local

Scan2Sheet Local is a free, local-first OCR project for Indian accounting documents.

It allows users to upload or scan an invoice, bill, ledger page, or passbook-style document. It then runs local OCR, extracts useful accounting data, validates the extracted values, lets the user review and correct mistakes, and exports clean CSV/Excel-ready data.

This is a specific OCR tool tailored to the flow:
`Indian accounting documents -> OCR -> structured data -> validation -> human review -> CSV export`

## Features

- **Local First & Privacy-focused**: Runs completely on your machine. No cloud APIs, no data sent to external servers.
- **Document Types**: Supports GST Invoices and Ledger/Passbook pages.
- **Validation**: Automatically validates GSTIN format, dates, tax math, and ledger balances.
- **Human-in-the-loop**: Provides an editable interface to correct OCR mistakes before exporting.
- **Export**: Generates clean CSVs ready to be imported into accounting software.

## Tech Stack

### Frontend
- **React & Vite**: Fast, modern frontend.
- **CSS**: Plain, functional styling.

### Backend
- **Python & FastAPI**: For fast, typed, and robust API endpoints.
- **OpenCV**: Image preprocessing (grayscale, denoise, thresholding).
- **Tesseract OCR**: The core open-source engine used to extract text from images.

## Architecture & Pipeline

1. **Upload**: User uploads an image via the React frontend.
2. **Preprocess**: FastAPI backend receives the image and uses OpenCV to clean it (convert to grayscale, threshold).
3. **OCR**: PyTesseract runs Tesseract OCR locally to extract raw text and confidence scores.
4. **Classification & Parsing**: Backend classifies the document (Invoice vs Ledger) and uses Regex and rule-based logic to parse structured data (like GSTIN, tax amounts, debit/credits).
5. **Validation**: Extracted data is validated against accounting rules.
6. **Review**: The frontend displays an editable table alongside the original image for the user to verify.
7. **Export**: After review, user can export the clean data to CSV.

## API Endpoints

- `GET /api/health` - Health check.
- `POST /api/extract` - Upload an image and get structured JSON with OCR results and warnings.
- `POST /api/export/csv` - Send corrected JSON data and receive a CSV file.

## Setup & Running Locally

### Prerequisites

- Windows 10 or later
- Python 3.11 or later
- Node.js 18 or later and npm
- Tesseract OCR

The backend uses Tesseract for image OCR. Install it on Windows with either of
these options:

```powershell
winget install --id UB-Mannheim.TesseractOCR
```

Or install Tesseract from the [UB Mannheim Windows builds](https://github.com/UB-Mannheim/tesseract/wiki).
The backend also checks the standard `Program Files` installation paths
automatically.

### Install the backend

From the repository root, create and activate a virtual environment, then
install the Python dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

If PowerShell blocks activation, run this once in the same terminal and retry:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Start the API from the repository root:

```powershell
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

The API is available at `http://127.0.0.1:8000`. Interactive API documentation
is available at `http://127.0.0.1:8000/docs`.

### Install and start the frontend

Open a second terminal, navigate to the frontend directory, and install the
Node dependencies:

```powershell
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, normally
`http://localhost:5173`.

### Check that the backend is running

With the backend terminal still running, use PowerShell to verify its health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

The response should contain `status: ok`.

### Use the app

1. Open the frontend at `http://localhost:5173`.
2. Choose an image, PDF, CSV, or Excel file with the file picker. For OCR, use a clear invoice, bill, ledger, or passbook scan.
3. Optionally enter a saved template ID. Leave it blank for automatic classification and extraction.
4. Select **Extract Data** and wait for the structured fields, ledger rows, raw OCR text, confidence, and validation warnings.
5. Review and edit the extracted fields or rows as needed.
6. Select **Export CSV** for spreadsheet data or **Export Tally XML** for a Tally-compatible XML file.

The three sample buttons can be used to explore the review and export interface
without uploading a document or running OCR. Actual extraction requires the
backend and Tesseract to be running.

### Stop the app

Press `Ctrl+C` in each terminal running the backend or frontend.

## API Reference

All endpoints are served by the backend at `http://127.0.0.1:8000`.

- `GET /api/health` - Check that the API is running.
- `POST /api/extract` - Upload a document as multipart form data using the `file` field. An optional `template_id` field can select a saved template.
- `POST /api/export/csv` - Send an extraction response as JSON and receive a CSV download.
- `POST /api/export/tally` - Send an extraction response as JSON and receive a Tally XML download.
- `GET /api/templates` - List saved templates held by the running backend process.
- `POST /api/templates` - Create a template.

## Troubleshooting

- **Frontend reports a network error:** Confirm the API terminal is running on port 8000. The current frontend expects `http://127.0.0.1:8000`.
- **OCR fails or returns no text:** Confirm `tesseract --version` works in PowerShell and use a well-lit, high-resolution document image.
- **Port already in use:** Stop the process using port 8000 or 5173, then restart the corresponding service on its expected port. The frontend currently uses fixed API and CORS URLs.
- **PDF upload fails:** PDF support imports PyMuPDF when a PDF is processed. Install it in the activated environment with `python -m pip install pymupdf` if your environment does not already provide it.

## Development Commands

From `frontend`:

```powershell
npm run build
npm run preview
```

The backend has no separate test command configured yet. The health endpoint
and the interactive API documentation are useful smoke checks during local
development.
