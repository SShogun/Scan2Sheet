from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def test_2a_01_engine_contract_exists() -> None:
    from backend.app.ocr.base import OCREngine
    from backend.app.ocr.types import OCRResult

    assert "recognize" in OCREngine.__dict__
    assert {"text", "confidence", "engine", "metadata"} == set(
        OCRResult.__dataclass_fields__
    )


def test_2a_02_tesseract_engine_preserves_legacy_success_semantics(monkeypatch) -> None:
    from backend.app.ocr.tesseract import TesseractEngine
    import backend.app.ocr.tesseract as module

    monkeypatch.setattr(
        module.pytesseract,
        "image_to_string",
        lambda *args, **kwargs: "  INV-102  ",
    )
    result = TesseractEngine().recognize(Image.new("L", (20, 20), 255))

    assert (result.text, result.confidence, result.engine) == (
        "INV-102",
        17.5,
        "tesseract",
    )


def test_2a_03_tesseract_error_retains_500_api_behavior(monkeypatch) -> None:
    from backend.app.ocr.tesseract import TesseractEngine
    import backend.app.ocr.tesseract as module

    def fail(*args, **kwargs):
        raise module.pytesseract.TesseractError(1, "boom")

    monkeypatch.setattr(module.pytesseract, "image_to_string", fail)

    with pytest.raises(HTTPException) as exc:
        TesseractEngine().recognize(Image.new("L", (20, 20), 255))

    assert exc.value.status_code == 500
    assert exc.value.detail.startswith("OCR failed:")


def test_2a_04_tesseract_timeout_retains_504_api_behavior(monkeypatch) -> None:
    from backend.app.ocr.tesseract import TesseractEngine
    import backend.app.ocr.tesseract as module

    def timeout(*args, **kwargs):
        raise RuntimeError("timeout")

    monkeypatch.setattr(module.pytesseract, "image_to_string", timeout)

    with pytest.raises(HTTPException) as exc:
        TesseractEngine().recognize(Image.new("L", (20, 20), 255))

    assert exc.value.status_code == 504
    assert exc.value.detail == "OCR timed out. Use a smaller or cleaner image."


def test_2a_05_legacy_wrapper_matches_engine(monkeypatch) -> None:
    from backend.app.ocr import _ocr_image
    from backend.app.ocr.tesseract import TesseractEngine
    import backend.app.ocr.tesseract as module

    monkeypatch.setattr(
        module.pytesseract,
        "image_to_string",
        lambda *args, **kwargs: "ABC123",
    )
    image = Image.new("L", (20, 20), 255)
    engine_result = TesseractEngine().recognize(image)

    assert _ocr_image(image) == (engine_result.text, engine_result.confidence)


def test_2a_06_parser_does_not_import_tesseract_directly() -> None:
    source = (ROOT / "backend" / "app" / "extractors.py").read_text()
    assert "import pytesseract" not in source
    assert "from pytesseract" not in source


def test_2a_07_ocr_package_has_no_accounting_rule_imports() -> None:
    forbidden = ("extractors", "validators", "schemas")

    for path in (ROOT / "backend" / "app" / "ocr").glob("*.py"):
        source = path.read_text()
        assert not any(
            f".{name}" in source or f"app.{name}" in source
            for name in forbidden
        ), path


def test_2a_08_router_accepts_abstaining_secondary_without_replacing_primary() -> None:
    from backend.app.ocr.router import OCRRouter
    from backend.app.ocr.types import OCRResult

    class Primary:
        def recognize(self, image):
            return OCRResult("PRIMARY", 80.0, "primary", {})

    class Secondary:
        def recognize(self, image):
            return OCRResult.abstain(engine="experimental", reason="not-ready")

    result = OCRRouter(Primary(), Secondary()).recognize(
        Image.new("L", (20, 20), 255)
    )

    assert result.text == "PRIMARY"
    assert result.engine == "primary"
    assert result.metadata["secondary_abstained"] is True


def test_2a_09_router_never_replaces_primary_in_part_2a() -> None:
    from backend.app.ocr.router import OCRRouter
    from backend.app.ocr.types import OCRResult

    class Primary:
        def recognize(self, image):
            return OCRResult("PRIMARY", 40.0, "primary", {})

    class Secondary:
        def recognize(self, image):
            return OCRResult("SECONDARY", 99.0, "experimental", {})

    result = OCRRouter(Primary(), Secondary()).recognize(
        Image.new("L", (20, 20), 255)
    )

    assert result.text == "PRIMARY"
    assert result.engine == "primary"
    assert result.metadata["secondary_candidate"]["text"] == "SECONDARY"


def test_2a_10_extract_endpoint_contract_stays_compatible() -> None:
    source = (ROOT / "backend" / "app" / "routes.py").read_text()

    assert '@router.post("/api/extract", response_model=ExtractResponse)' in source
    assert "file: UploadFile = File(...)" in source
    assert "template_id: str | None = Form(None)" in source


def test_2a_11_m1b_ocr_results_remain_stable(current_benchmark) -> None:
    expected = json.loads(
        (ROOT / "artifacts" / "benchmarks" / "m1b_after.json").read_text()
    )
    before = {item["category"]: item for item in expected["fixtures"]}
    after = {item["category"]: item for item in current_benchmark["fixtures"]}

    assert set(before) == set(after)
    for category in before:
        assert after[category]["normalized_ocr_text"] == before[category][
            "normalized_ocr_text"
        ]
        assert after[category]["cer"] == before[category]["cer"]
        assert after[category]["wer"] == before[category]["wer"]
        assert after[category]["important_field_accuracy"] == before[category][
            "important_field_accuracy"
        ]
