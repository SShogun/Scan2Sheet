from __future__ import annotations

from typing import Protocol

from PIL import Image

from .types import OCRResult


class OCREngine(Protocol):
    def recognize(self, image: Image.Image) -> OCRResult:
        """Recognize text without applying document-specific parsing rules."""
        ...
