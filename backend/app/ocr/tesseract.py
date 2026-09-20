from __future__ import annotations

import os
import shutil
from typing import Any

from PIL import Image
import pytesseract

from .types import OCRError, OCRResult, OCRTimeoutError


TESSERACT_CONFIG = "--oem 1 --psm 3"
TESSERACT_TIMEOUT_SECONDS = 15


def configure_tesseract() -> None:
    if shutil.which("tesseract"):
        return

    possible_paths = [
        r"C:\Users\soham\AppData\Local\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return


class TesseractEngine:
    name = "tesseract"

    def recognize(self, image: Image.Image) -> OCRResult:
        configure_tesseract()
        try:
            raw_text = pytesseract.image_to_string(
                image,
                config=TESSERACT_CONFIG,
                timeout=TESSERACT_TIMEOUT_SECONDS,
            ).strip()
        except pytesseract.TesseractError as exc:
            raise OCRError(f"OCR failed: {exc}") from exc
        except RuntimeError as exc:
            raise OCRTimeoutError(
                "OCR timed out. Use a smaller or cleaner image."
            ) from exc

        text_length_score = min(100.0, max(0.0, len(raw_text) * 2.5))
        return OCRResult(
            text=raw_text,
            confidence=text_length_score,
            engine=self.name,
            metadata={
                "config": TESSERACT_CONFIG,
                "timeout_seconds": TESSERACT_TIMEOUT_SECONDS,
            },
        )

    def recognize_data(self, image: Image.Image) -> dict[str, list[Any]]:
        """Return Tesseract word/layout data for legacy template extraction."""
        configure_tesseract()
        try:
            return pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
                timeout=TESSERACT_TIMEOUT_SECONDS,
            )
        except (pytesseract.TesseractError, RuntimeError):
            return {
                "text": [],
                "conf": [],
                "left": [],
                "line_num": [],
                "par_num": [],
                "block_num": [],
            }
