from __future__ import annotations

from PIL import Image

from .base import OCREngine
from .types import OCRResult


class OCRRouter:
    """Keep primary OCR authoritative while allowing a secondary engine to abstain."""

    def __init__(self, primary: OCREngine, secondary: OCREngine | None = None) -> None:
        self.primary = primary
        self.secondary = secondary

    def recognize(self, image: Image.Image) -> OCRResult:
        primary_result = self.primary.recognize(image)
        if self.secondary is None:
            return primary_result

        try:
            secondary_result = self.secondary.recognize(image)
        except Exception as exc:
            return primary_result.with_metadata(secondary_error=type(exc).__name__)

        if secondary_result.abstained:
            return primary_result.with_metadata(
                secondary_engine=secondary_result.engine,
                secondary_abstained=True,
                secondary_reason=secondary_result.metadata.get("reason", ""),
            )

        # Part 2A intentionally never replaces primary OCR.
        # Arbitration belongs to Milestone 3.
        return primary_result.with_metadata(
            secondary_engine=secondary_result.engine,
            secondary_abstained=False,
            secondary_candidate={
                "text": secondary_result.text,
                "confidence": secondary_result.confidence,
            },
        )
