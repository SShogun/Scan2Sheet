from __future__ import annotations

import io
import os

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from ..imaging.pipeline import PreprocessResult, preprocess_image
from .base import OCREngine
from .experimental import ExperimentalEngine, RestrictedExperimentalEngine
from .router import OCRRouter
from .tesseract import TesseractEngine, configure_tesseract
from .types import OCRError, OCRResult, OCRTimeoutError


EXPERIMENTAL_OCR_FLAG = "SCAN2SHEET_EXPERIMENTAL_OCR"
EXPERIMENTAL_TRIGGER_CONFIDENCE = 60.0


def _experimental_enabled() -> bool:
    return os.getenv(EXPERIMENTAL_OCR_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


_DEFAULT_TESSERACT = TesseractEngine()
_DEFAULT_EXPERIMENTAL = RestrictedExperimentalEngine() if _experimental_enabled() else None
_DEFAULT_ROUTER = OCRRouter(
    primary=_DEFAULT_TESSERACT,
    secondary=_DEFAULT_EXPERIMENTAL,
    secondary_trigger_confidence=EXPERIMENTAL_TRIGGER_CONFIDENCE if _DEFAULT_EXPERIMENTAL is not None else None,
)


def _configure_tesseract() -> None:
    configure_tesseract()


def _decode_image(image_bytes: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Unsupported or corrupt image file.") from exc
    return image


def _preprocess_result(image: Image.Image) -> PreprocessResult:
    configure_tesseract()
    return preprocess_image(image)


def _preprocess_image(image: Image.Image) -> Image.Image:
    return _preprocess_result(image).processed_image


def _primary_ocr_result(image: Image.Image) -> OCRResult:
    try:
        return _DEFAULT_TESSERACT.recognize(image)
    except OCRTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except OCRError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _ocr_result(image: Image.Image) -> OCRResult:
    try:
        return _DEFAULT_ROUTER.recognize(image)
    except OCRTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except OCRError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _ocr_image(image: Image.Image) -> tuple[str, float]:
    result = _ocr_result(image)
    return result.text, result.confidence


def _experimental_engine_available() -> bool:
    return _DEFAULT_EXPERIMENTAL is not None


def _experimental_result(image: Image.Image) -> OCRResult | None:
    if _DEFAULT_EXPERIMENTAL is None:
        return None
    try:
        return _DEFAULT_EXPERIMENTAL.recognize(image)
    except Exception as exc:
        return OCRResult.abstain(
            engine=_DEFAULT_EXPERIMENTAL.name,
            reason=f"error:{type(exc).__name__}",
        )


def _ocr_data(image: Image.Image) -> dict[str, list[object]]:
    return _DEFAULT_TESSERACT.recognize_data(image)


__all__ = [
    "OCREngine", "OCRResult", "TesseractEngine", "ExperimentalEngine",
    "RestrictedExperimentalEngine", "OCRRouter", "_configure_tesseract",
    "_decode_image", "_preprocess_result", "_preprocess_image",
    "_primary_ocr_result", "_ocr_result", "_ocr_image", "_ocr_data",
    "_experimental_engine_available", "_experimental_result",
]
