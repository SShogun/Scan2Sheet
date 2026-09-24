from tests.ocr_benchmark import edit_distance,error_rate,normalize_text
def test_edit_distance_known_case(): assert edit_distance('kitten','sitting')==3
def test_error_rate_exact_match_is_zero(): assert error_rate('ABC123','ABC123')==0.0
def test_word_normalization_collapses_whitespace_without_changing_case_or_punctuation(): assert normalize_text('  INV-102\n\n  Total: 11800.00  ',words=True)=='INV-102 Total: 11800.00'

def test_default_benchmark_output_cannot_overwrite_historical_baseline():
    from tests.ocr_benchmark import DEFAULT_OUTPUT
    assert DEFAULT_OUTPUT.name != 'baseline.json'

def test_clear_gst_invoice_extracts_all_seven_core_fields():
    from backend.app.extractors import _extract_invoice_fields

    text = """SCAN2SHEET TEST INVOICE
GSTIN: 27ABCDE1234F1Z5
Invoice No: INV-102
Date: 12/04/2025
Taxable Amount: 10000.00
CGST: 900.00
SGST: 900.00
Grand Total: 11800.00"""

    fields = _extract_invoice_fields(text)
    assert {
        "gstin": fields.get("gstin"),
        "invoice_number": fields.get("invoice_number"),
        "date": fields.get("date"),
        "taxable_amount": fields.get("taxable_amount"),
        "cgst": fields.get("cgst"),
        "sgst": fields.get("sgst"),
        "total": fields.get("total"),
    } == {
        "gstin": "27ABCDE1234F1Z5",
        "invoice_number": "INV-102",
        "date": "12/04/2025",
        "taxable_amount": "10000.00",
        "cgst": "900.00",
        "sgst": "900.00",
        "total": "11800.00",
    }

