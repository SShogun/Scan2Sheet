from __future__ import annotations

import io

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from ..imaging.pipeline import preprocess_image
from .base import OCREngine
from .experimental import ExperimentalEngine
from .router import OCRRouter
from .tesseract import TesseractEngine, configure_tesseract
from .types import OCRError, OCRResult, OCRTimeoutError


_DEFAULT_TESSERACT = TesseractEngine()
_DEFAULT_ROUTER = OCRRouter(primary=_DEFAULT_TESSERACT)


def _configure_tesseract() -> None:
    """Backward-compatible wrapper retained for existing internal callers."""
    configure_tesseract()


def _decode_image(image_bytes: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except UnidentifiedImageError as exc:
        raise HTTPException(
            status_code=400,
            detail="Unsupported or corrupt image file.",
        ) from exc
    return image


def _preprocess_image(image: Image.Image) -> Image.Image:
    """Backward-compatible preprocessing wrapper from the pre-2A OCR module."""
    configure_tesseract()
    return preprocess_image(image).processed_image


def _ocr_image(image: Image.Image) -> tuple[str, float]:
    """Backward-compatible tuple API backed by the primary OCR router."""
    try:
        result = _DEFAULT_ROUTER.recognize(image)
    except OCRTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except OCRError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result.text, result.confidence


def _ocr_data(image: Image.Image) -> dict[str, list[object]]:
    """Compatibility adapter for template layout extraction."""
    return _DEFAULT_TESSERACT.recognize_data(image)


__all__ = [
    "OCREngine",
    "OCRResult",
    "TesseractEngine",
    "ExperimentalEngine",
    "OCRRouter",
    "_configure_tesseract",
    "_decode_image",
    "_preprocess_image",
    "_ocr_image",
    "_ocr_data",
]
