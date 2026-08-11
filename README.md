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

*(Add your setup instructions here)*
