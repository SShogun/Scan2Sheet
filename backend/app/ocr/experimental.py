from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .types import OCRResult


ENGINE_NAME = "experimental-restricted-v1"
RESTRICTED_VOCABULARY = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,/-:"
MODEL_ENV = "SCAN2SHEET_EXPERIMENTAL_MODEL"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[3] / "artifacts" / "models" / "restricted_hog_nn_v1.npz"
MAX_GLYPHS = 32
MIN_TOKEN_CONFIDENCE = 10.0

_BINARY_THRESHOLD = 200
_GEOMETRY_SCALE = 1000
_PIXEL_BLOCK_SCALE = 250
_MARGIN_SCALE = 10_000


@dataclass(frozen=True)
class _RestrictedModel:
    features: np.ndarray
    labels: np.ndarray
    distance_thresholds: dict[str, int]
    margin_thresholds: dict[str, int]
    sha256: str


def _abstain(reason: str, *, model_sha256: str = "", confidence: float = 0.0, **extra: Any) -> OCRResult:
    metadata: dict[str, Any] = {
        "abstained": True,
        "reason": reason,
        "experimental": True,
        "scope": "restricted-token",
        "not_general_purpose_ocr": True,
        "model_sha256": model_sha256,
    }
    metadata.update(extra)
    return OCRResult(text="", confidence=float(confidence), engine=ENGINE_NAME, metadata=metadata)


@lru_cache(maxsize=4)
def _load_model(model_path: str) -> _RestrictedModel:
    path = Path(model_path)
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    with np.load(path, allow_pickle=False) as data:
        features = np.asarray(data["features"], dtype="<i2")
        labels = np.asarray(data["labels"]).astype("<U1")
        class_labels = np.asarray(data["class_labels"]).astype("<U1")
        distances = np.asarray(data["distance_thresholds"], dtype="<i8")
        margins = np.asarray(data["margin_thresholds"], dtype="<i4")

    if features.ndim != 2 or len(features) != len(labels):
        raise ValueError("Invalid restricted recognizer model shape.")
    if len(class_labels) != len(distances) or len(class_labels) != len(margins):
        raise ValueError("Invalid restricted recognizer threshold shape.")
    if set(class_labels.tolist()) != set(RESTRICTED_VOCABULARY):
        raise ValueError("Restricted recognizer vocabulary does not match model.")

    features.setflags(write=False)
    labels.setflags(write=False)
    return _RestrictedModel(
        features=features,
        labels=labels,
        distance_thresholds={
            str(label): int(value)
            for label, value in zip(class_labels, distances, strict=True)
        },
        margin_thresholds={
            str(label): int(value)
            for label, value in zip(class_labels, margins, strict=True)
        },
        sha256=digest,
    )


def _scaled_ratio(numerator: int, denominator: int, scale: int = _GEOMETRY_SCALE) -> int:
    if denominator <= 0:
        return 0
    return (int(numerator) * scale + denominator // 2) // denominator


def _binarize(image: Image.Image) -> np.ndarray:
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    return (gray < _BINARY_THRESHOLD).astype(np.uint8)


def _segment_glyphs(image: Image.Image) -> list[tuple[np.ndarray, np.ndarray]]:
    binary = _binarize(image)
    ys, xs = np.where(binary > 0)
    if len(xs) == 0:
        return []

    line = binary[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    active = (line > 0).sum(axis=0) >= 1
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, is_active in enumerate(active):
        if is_active and start is None:
            start = index
        elif not is_active and start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(active)))

    line_height = max(1, int(line.shape[0]))
    glyphs: list[tuple[np.ndarray, np.ndarray]] = []
    for left, right in runs:
        full = line[:, left:right]
        gy, gx = np.where(full > 0)
        if len(gx) == 0:
            continue
        tight = full[gy.min() : gy.max() + 1, gx.min() : gx.max() + 1]
        ink_pixels = int(np.count_nonzero(tight))
        geometry = np.asarray(
            [
                _scaled_ratio(int(gy.min()), line_height),
                _scaled_ratio(int(gy.max()) + 1, line_height),
                _scaled_ratio(int(tight.shape[1]), line_height),
                _scaled_ratio(int(tight.shape[0]), line_height),
                _scaled_ratio(ink_pixels, int(tight.size)),
            ],
            dtype="<i2",
        )
        glyphs.append((tight, geometry))
    return glyphs


def _fit_size(width: int, height: int) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        return 1, 1
    if 24 * height <= 26 * width:
        new_width = 24
        new_height = max(1, min(26, (height * 24 + width // 2) // width))
    else:
        new_height = 26
        new_width = max(1, min(24, (width * 26 + height // 2) // height))
    return new_width, new_height


def _resize_nearest(binary: np.ndarray, width: int, height: int) -> np.ndarray:
    source_height, source_width = binary.shape
    x_indices = (np.arange(width, dtype=np.int64) * source_width) // width
    y_indices = (np.arange(height, dtype=np.int64) * source_height) // height
    return binary[y_indices[:, None], x_indices[None, :]].astype(np.uint8, copy=False)


def _normalize_glyph(crop: np.ndarray) -> np.ndarray:
    ys, xs = np.where(crop > 0)
    if len(xs) == 0:
        return np.zeros((32, 32), dtype=np.uint8)

    tight = crop[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    new_width, new_height = _fit_size(int(tight.shape[1]), int(tight.shape[0]))
    resized = _resize_nearest(tight, new_width, new_height)

    canvas = np.zeros((32, 32), dtype=np.uint8)
    x = (32 - new_width) // 2
    y = (32 - new_height) // 2
    canvas[y : y + new_height, x : x + new_width] = resized
    return canvas


def _feature_vector(glyph: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    crop, geometry = glyph
    normalized = _normalize_glyph(crop)

    block_counts = (
        normalized.reshape(16, 2, 16, 2)
        .sum(axis=(1, 3), dtype=np.int16)
        .reshape(-1)
    )
    pixel_features = block_counts * _PIXEL_BLOCK_SCALE
    return np.concatenate([pixel_features, geometry]).astype("<i2", copy=False)


def _squared_distance(left: np.ndarray, right: np.ndarray) -> int:
    a = np.asarray(left).reshape(-1)
    b = np.asarray(right).reshape(-1)
    if len(a) != len(b):
        raise ValueError("Feature vectors must have the same length.")
    return sum(
        (int(x) - int(y)) * (int(x) - int(y))
        for x, y in zip(a, b, strict=True)
    )


def _margin_score(best_distance: int, second_distance: int) -> int:
    if second_distance <= 0:
        return 0
    return (
        max(0, int(second_distance) - int(best_distance)) * _MARGIN_SCALE
    ) // int(second_distance)


def _classify_glyph(glyph: tuple[np.ndarray, np.ndarray], model: _RestrictedModel) -> tuple[str, int, int]:
    query = _feature_vector(glyph)
    distances = [_squared_distance(feature, query) for feature in model.features]
    by_class: list[tuple[str, int]] = []
    for label in model.distance_thresholds:
        class_distances = [
            distance
            for distance, candidate_label in zip(distances, model.labels, strict=True)
            if candidate_label == label
        ]
        by_class.append((label, min(class_distances)))
    by_class.sort(key=lambda item: (item[1], item[0]))
    (best_label, best_distance), (_, second_distance) = by_class[:2]
    return best_label, best_distance, _margin_score(best_distance, second_distance)


class RestrictedExperimentalEngine:
    """Experimental recognizer for isolated restricted-vocabulary tokens only."""

    name = ENGINE_NAME

    def __init__(self, model_path: str | Path | None = None, *, min_token_confidence: float = MIN_TOKEN_CONFIDENCE) -> None:
        configured = os.getenv(MODEL_ENV)
        self.model_path = Path(model_path if model_path is not None else configured or DEFAULT_MODEL_PATH)
        self.min_token_confidence = float(min_token_confidence)

    def recognize(self, image: Image.Image) -> OCRResult:
        try:
            model = _load_model(str(self.model_path.resolve()))
        except (OSError, ValueError, KeyError) as exc:
            return _abstain("model_unavailable", model_error=type(exc).__name__)

        glyphs = _segment_glyphs(image)
        if not glyphs or len(glyphs) > MAX_GLYPHS:
            return _abstain("segmentation", model_sha256=model.sha256, glyph_count=len(glyphs))

        output: list[str] = []
        confidences: list[float] = []
        for glyph in glyphs:
            label, distance, margin = _classify_glyph(glyph, model)
            distance_threshold = model.distance_thresholds[label]
            margin_threshold = model.margin_thresholds[label]
            if distance > distance_threshold or margin < margin_threshold:
                return _abstain(
                    "unknown_or_uncertain",
                    model_sha256=model.sha256,
                    predicted_label=label,
                    distance_squared=distance,
                    margin=round(margin / _MARGIN_SCALE, 6),
                )

            distance_score = max(
                0.0,
                min(1.0, 1.0 - distance / max(distance_threshold, 1)),
            )
            margin_ratio = margin / _MARGIN_SCALE
            margin_threshold_ratio = margin_threshold / _MARGIN_SCALE
            margin_score = max(
                0.0,
                min(
                    1.0,
                    margin_ratio / max(margin_threshold_ratio * 4, 0.3),
                ),
            )
            confidence = 100.0 * (0.65 * distance_score + 0.35 * margin_score)
            output.append(label)
            confidences.append(confidence)

        token_confidence = min(confidences)
        if token_confidence < self.min_token_confidence:
            return _abstain(
                "low_confidence",
                model_sha256=model.sha256,
                confidence=token_confidence,
                glyph_count=len(glyphs),
            )

        return OCRResult(
            text="".join(output),
            confidence=token_confidence,
            engine=self.name,
            metadata={
                "experimental": True,
                "scope": "restricted-token",
                "not_general_purpose_ocr": True,
                "model_sha256": model.sha256,
                "glyph_count": len(glyphs),
                "vocabulary": RESTRICTED_VOCABULARY,
            },
        )


ExperimentalEngine = RestrictedExperimentalEngine
