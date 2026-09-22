from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def _candidate(value, engine, confidence):
    from backend.app.arbitration import FieldCandidate

    return FieldCandidate(
        value=value,
        engine=engine,
        confidence=confidence,
        metadata={},
    )


def test_secondary_total_wins_only_when_accounting_math_supports_it():
    from backend.app.arbitration import arbitrate_invoice_total

    fields = {
        "taxable_amount": "10000",
        "cgst": "900",
        "sgst": "900",
        "igst": "0",
        "total": "17800",
    }
    decision = arbitrate_invoice_total(
        fields,
        _candidate("17800", "tesseract", 92),
        _candidate("11800", "experimental-restricted-v1", 75),
    )
    assert decision.value == "11800"
    assert decision.selected_engine == "experimental-restricted-v1"


def test_valid_primary_is_not_displaced_by_worse_secondary():
    from backend.app.arbitration import arbitrate_invoice_total

    fields = {
        "taxable_amount": "10000",
        "cgst": "900",
        "sgst": "900",
        "igst": "0",
        "total": "11800",
    }
    decision = arbitrate_invoice_total(
        fields,
        _candidate("11800", "tesseract", 70),
        _candidate("17800", "experimental-restricted-v1", 99),
    )
    assert decision.value == "11800"
    assert decision.selected_engine == "tesseract"


def test_no_accounting_context_means_no_override():
    from backend.app.arbitration import arbitrate_invoice_total

    fields = {"total": "17800"}
    decision = arbitrate_invoice_total(
        fields,
        _candidate("17800", "tesseract", 30),
        _candidate("11800", "experimental-restricted-v1", 99),
    )
    assert decision.selected_engine == "tesseract"


def test_decision_preserves_both_candidates():
    from backend.app.arbitration import arbitrate_invoice_total

    fields = {
        "taxable_amount": "10000",
        "cgst": "900",
        "sgst": "900",
        "total": "17800",
    }
    decision = arbitrate_invoice_total(
        fields,
        _candidate("17800", "tesseract", 82),
        _candidate("11800", "experimental-restricted-v1", 71),
    )
    assert {candidate.engine for candidate in decision.candidates} == {
        "tesseract",
        "experimental-restricted-v1",
    }


def test_amount_crop_uses_matching_tesseract_token_confidence():
    from backend.app.arbitration import find_amount_candidate_crop

    image = Image.new("L", (300, 100), 255)
    data = {
        "text": ["Grand", "Total", "11800.00"],
        "conf": ["90", "91", "76"],
        "left": [10, 80, 150],
        "top": [30, 30, 30],
        "width": [50, 50, 80],
        "height": [20, 20, 20],
        "line_num": [1, 1, 1],
        "par_num": [1, 1, 1],
        "block_num": [1, 1, 1],
    }
    crop = find_amount_candidate_crop(image, data, "11800.00")
    assert crop is not None
    assert crop.confidence == 76.0
    assert crop.image.width >= 80


def test_processing_schema_exposes_quality_preprocessing_and_arbitration():
    from backend.app.schemas import (
        ArbitrationInfo,
        ImageQualityInfo,
        ProcessingInfo,
    )

    info = ProcessingInfo(
        image_quality=ImageQualityInfo(
            status="degraded",
            blurred=True,
            warnings=["severe_blur"],
        ),
        preprocessing_applied=["resize_for_ocr"],
        experimental_ocr_status="selected",
        experimental_ocr_engine="experimental-restricted-v1",
        arbitration=ArbitrationInfo(
            field="total",
            selected_engine="experimental-restricted-v1",
            reason="secondary_matches_accounting_total",
            primary_value="17800",
            secondary_value="11800",
        ),
    )
    assert info.image_quality is not None
    assert info.image_quality.status == "degraded"
    assert info.preprocessing_applied == ["resize_for_ocr"]
    assert info.arbitration is not None
    assert info.arbitration.selected_engine == "experimental-restricted-v1"


def test_frontend_surfaces_m3a_processing_metadata():
    source = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "Image quality" in source
    assert "Preprocessing applied" in source
    assert "Experimental OCR" in source
    assert "Quality analysis not available." in source


def test_section_1_uses_primary_only_before_bounded_secondary_arbitration():
    source = (ROOT / "backend" / "app" / "routes.py").read_text(encoding="utf-8")
    assert "_primary_ocr_result(preprocessed_image)" in source
    assert "    _ocr_result," not in source
    assert " = _ocr_result(preprocessed_image)" not in source


def test_scanned_pdf_path_can_use_the_same_bounded_total_arbitration():
    source = (ROOT / "backend" / "app" / "routes.py").read_text(encoding="utf-8")
    assert "pdf_processed_image = preprocessed_image" in source
    assert "primary_engine=pdf_primary_engine" in source



def test_taxable_without_explicit_tax_context_cannot_promote_secondary():
    from backend.app.arbitration import arbitrate_invoice_total

    fields = {
        "taxable_amount": "10000",
        "total": "11800",
    }
    decision = arbitrate_invoice_total(
        fields,
        _candidate("11800", "tesseract", 35),
        _candidate("10000", "experimental-restricted-v1", 99),
    )
    assert decision.value == "11800"
    assert decision.selected_engine == "tesseract"
    assert decision.reason == "insufficient_accounting_context"


def test_high_confidence_primary_total_does_not_run_experimental(monkeypatch):
    from backend.app import routes
    from backend.app.schemas import ProcessingInfo

    image = Image.new("L", (300, 100), 255)
    data = {
        "text": ["Grand", "Total", "11800.00"],
        "conf": ["90", "91", "92"],
        "left": [10, 80, 150],
        "top": [30, 30, 30],
        "width": [50, 50, 80],
        "height": [20, 20, 20],
        "line_num": [1, 1, 1],
        "par_num": [1, 1, 1],
        "block_num": [1, 1, 1],
    }
    calls = []
    monkeypatch.setattr(routes, "_experimental_engine_available", lambda: True)
    monkeypatch.setattr(routes, "_ocr_data", lambda _image: data)
    monkeypatch.setattr(
        routes,
        "_experimental_result",
        lambda _image: calls.append(1),
    )

    processing = ProcessingInfo(experimental_ocr_status="not_run")
    fields = {
        "taxable_amount": "10000",
        "cgst": "900",
        "sgst": "900",
        "total": "11800.00",
    }
    routes._arbitrate_invoice_total_from_crop(
        image,
        fields,
        processing,
        primary_engine="tesseract",
    )

    assert calls == []
    assert processing.experimental_ocr_status == "not_run"
    assert fields["total"] == "11800.00"
