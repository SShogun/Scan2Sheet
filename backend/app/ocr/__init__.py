from __future__ import annotations

import io
import os

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from ..imaging.pipeline import preprocess_image
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


def _preprocess_image(image: Image.Image) -> Image.Image:
    configure_tesseract()
    return preprocess_image(image).processed_image


def _ocr_image(image: Image.Image) -> tuple[str, float]:
    try:
        result = _DEFAULT_ROUTER.recognize(image)
    except OCRTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except OCRError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result.text, result.confidence


def _ocr_data(image: Image.Image) -> dict[str, list[object]]:
    return _DEFAULT_TESSERACT.recognize_data(image)


__all__ = [
    "OCREngine", "OCRResult", "TesseractEngine", "ExperimentalEngine",
    "RestrictedExperimentalEngine", "OCRRouter", "_configure_tesseract",
    "_decode_image", "_preprocess_image", "_ocr_image", "_ocr_data",
]
