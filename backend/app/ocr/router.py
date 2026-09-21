from __future__ import annotations

from PIL import Image

from .base import OCREngine
from .types import OCRResult


class OCRRouter:
    """Keep primary OCR authoritative while optionally collecting a secondary candidate."""

    def __init__(
        self,
        primary: OCREngine,
        secondary: OCREngine | None = None,
        *,
        secondary_trigger_confidence: float | None = None,
    ) -> None:
        self.primary = primary
        self.secondary = secondary
        self.secondary_trigger_confidence = secondary_trigger_confidence

    def recognize(self, image: Image.Image) -> OCRResult:
        primary_result = self.primary.recognize(image)
        if self.secondary is None:
            return primary_result

        if (
            self.secondary_trigger_confidence is not None
            and primary_result.confidence >= self.secondary_trigger_confidence
        ):
            return primary_result.with_metadata(
                secondary_skipped="primary_confident",
                secondary_trigger_confidence=self.secondary_trigger_confidence,
            )

        try:
            secondary_result = self.secondary.recognize(image)
        except Exception as exc:
            return primary_result.with_metadata(
                secondary_error=type(exc).__name__,
                secondary_trigger_confidence=self.secondary_trigger_confidence,
            )

        if secondary_result.abstained:
            return primary_result.with_metadata(
                secondary_engine=secondary_result.engine,
                secondary_abstained=True,
                secondary_reason=secondary_result.metadata.get("reason", ""),
                secondary_provenance=dict(secondary_result.metadata),
                secondary_trigger_confidence=self.secondary_trigger_confidence,
            )

        return primary_result.with_metadata(
            secondary_engine=secondary_result.engine,
            secondary_abstained=False,
            secondary_candidate={
                "text": secondary_result.text,
                "confidence": secondary_result.confidence,
                "engine": secondary_result.engine,
                "metadata": dict(secondary_result.metadata),
            },
            secondary_trigger_confidence=self.secondary_trigger_confidence,
        )
