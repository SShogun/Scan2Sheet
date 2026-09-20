from __future__ import annotations

from PIL import Image

from .types import OCRResult


class ExperimentalEngine:
    """Part 2A placeholder; Part 2B may replace it with a restricted recognizer."""

    name = "experimental"

    def recognize(self, image: Image.Image) -> OCRResult:
        return OCRResult.abstain(engine=self.name, reason="not_configured")
