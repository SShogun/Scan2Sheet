from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from .accounting import check_invoice_total


@dataclass(frozen=True)
class FieldCandidate:
    value: str
    engine: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArbitrationDecision:
    value: str
    selected_engine: str
    reason: str
    candidates: tuple[FieldCandidate, ...]


@dataclass(frozen=True)
class CandidateCrop:
    image: Image.Image
    confidence: float
    box: tuple[int, int, int, int]


def arbitrate_invoice_total(
    fields: dict[str, str],
    primary: FieldCandidate,
    secondary: FieldCandidate | None,
) -> ArbitrationDecision:
    candidates = (primary,) if secondary is None else (primary, secondary)
    primary_check = check_invoice_total(fields, primary.value)
    if secondary is None:
        return ArbitrationDecision(primary.value, primary.engine, "primary_only", candidates)

    secondary_check = check_invoice_total(fields, secondary.value)
    if primary_check.matches is None or secondary_check.matches is None:
        return ArbitrationDecision(
            primary.value,
            primary.engine,
            "insufficient_accounting_context",
            candidates,
        )
    if secondary_check.matches and not primary_check.matches:
        return ArbitrationDecision(
            secondary.value,
            secondary.engine,
            "secondary_matches_accounting_total",
            candidates,
        )
    return ArbitrationDecision(primary.value, primary.engine, "primary_preserved", candidates)


def _numeric_value(value: object) -> float | None:
    try:
        return float(
            str(value)
            .replace(",", "")
            .replace("Rs", "")
            .replace("INR", "")
            .strip()
        )
    except ValueError:
        return None


def find_amount_candidate_crop(
    image: Image.Image,
    data: dict[str, list[object]],
    target_value: str,
) -> CandidateCrop | None:
    target = _numeric_value(target_value)
    if target is None:
        return None

    texts = data.get("text", [])
    required = ("conf", "left", "top", "width", "height")
    if not texts or any(len(data.get(key, [])) < len(texts) for key in required):
        return None

    candidates: list[tuple[int, float, int]] = []
    for index, token in enumerate(texts):
        token_value = _numeric_value(token)
        if token_value is None or abs(token_value - target) > 0.005:
            continue
        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError):
            confidence = -1.0

        label_bonus = 0
        line_key = tuple(
            data.get(key, [None] * len(texts))[index]
            for key in ("block_num", "par_num", "line_num")
        )
        for previous in range(max(0, index - 3), index):
            prev_key = tuple(
                data.get(key, [None] * len(texts))[previous]
                for key in ("block_num", "par_num", "line_num")
            )
            if (
                prev_key == line_key
                and str(texts[previous]).strip().lower() in {"total", "grand"}
            ):
                label_bonus = 1
        candidates.append((label_bonus, confidence, index))

    if not candidates:
        return None

    _, confidence, index = max(candidates, key=lambda item: (item[0], item[1]))
    left = int(data["left"][index])
    top = int(data["top"][index])
    width = int(data["width"][index])
    height = int(data["height"][index])
    pad_x = max(4, int(width * 0.08))
    pad_y = max(4, int(height * 0.20))
    x0 = max(0, left - pad_x)
    y0 = max(0, top - pad_y)
    x1 = min(image.width, left + width + pad_x)
    y1 = min(image.height, top + height + pad_y)
    if x1 <= x0 or y1 <= y0:
        return None

    return CandidateCrop(
        image=image.crop((x0, y0, x1, y1)),
        confidence=max(0.0, confidence),
        box=(x0, y0, x1, y1),
    )
