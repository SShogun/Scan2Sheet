from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping


class OCRError(RuntimeError):
    """Base OCR-engine failure independent from HTTP/API transport."""


class OCRTimeoutError(OCRError):
    """OCR engine exceeded its bounded execution time."""


@dataclass(frozen=True)
class OCRResult:
    text: str
    confidence: float
    engine: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def abstained(self) -> bool:
        return bool(self.metadata.get("abstained", False))

    @classmethod
    def abstain(cls, *, engine: str, reason: str) -> "OCRResult":
        return cls(
            text="",
            confidence=0.0,
            engine=engine,
            metadata={"abstained": True, "reason": reason},
        )

    def with_metadata(self, **updates: Any) -> "OCRResult":
        merged = dict(self.metadata)
        merged.update(updates)
        return replace(self, metadata=merged)
