from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from .types import OCRResult


ENGINE_NAME = "experimental-restricted-v1"
RESTRICTED_VOCABULARY = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,/-:"
MODEL_ENV = "SCAN2SHEET_EXPERIMENTAL_MODEL"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[3] / "artifacts" / "models" / "restricted_hog_nn_v1.npz"
MAX_GLYPHS = 32
MIN_TOKEN_CONFIDENCE = 10.0

_HOG = cv2.HOGDescriptor((32, 32), (16, 16), (8, 8), (8, 8), 9)


@dataclass(frozen=True)
class _RestrictedModel:
    features: np.ndarray
    labels: np.ndarray
    distance_thresholds: dict[str, float]
    margin_thresholds: dict[str, float]
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
        features = np.asarray(data["features"], dtype=np.float32)
        labels = np.asarray(data["labels"]).astype("<U1")
        class_labels = np.asarray(data["class_labels"]).astype("<U1")
        distances = np.asarray(data["distance_thresholds"], dtype=np.float32)
        margins = np.asarray(data["margin_thresholds"], dtype=np.float32)

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
        distance_thresholds={str(label): float(value) for label, value in zip(class_labels, distances, strict=True)},
        margin_thresholds={str(label): float(value) for label, value in zip(class_labels, margins, strict=True)},
        sha256=digest,
    )


def _binarize(image: Image.Image) -> np.ndarray:
    gray = np.asarray(image.convert("L"))
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


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

    line_height = max(1, line.shape[0])
    glyphs: list[tuple[np.ndarray, np.ndarray]] = []
    for left, right in runs:
        full = line[:, left:right]
        gy, gx = np.where(full > 0)
        if len(gx) == 0:
            continue
        tight = full[gy.min() : gy.max() + 1, gx.min() : gx.max() + 1]
        geometry = np.array(
            [
                gy.min() / line_height,
                (gy.max() + 1) / line_height,
                tight.shape[1] / line_height,
                tight.shape[0] / line_height,
                float((tight > 0).mean()),
            ],
            dtype=np.float32,
        )
        glyphs.append((tight, geometry))
    return glyphs


def _normalize_glyph(crop: np.ndarray) -> np.ndarray:
    ys, xs = np.where(crop > 0)
    if len(xs) == 0:
        return np.zeros((32, 32), dtype=np.uint8)

    tight = crop[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    height, width = tight.shape
    scale = min(24 / max(width, 1), 26 / max(height, 1))
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    resized = cv2.resize(tight, (new_width, new_height), interpolation=interpolation)

    canvas = np.zeros((32, 32), dtype=np.uint8)
    x = (32 - new_width) // 2
    y = (32 - new_height) // 2
    canvas[y : y + new_height, x : x + new_width] = resized
    return canvas


def _feature_vector(glyph: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    crop, geometry = glyph
    normalized = _normalize_glyph(crop)
    hog = _HOG.compute(normalized).reshape(-1).astype(np.float32)
    hog_norm = float(np.linalg.norm(hog))
    if hog_norm:
        hog /= hog_norm

    pixels = cv2.resize(normalized, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32).reshape(-1) / 255.0
    pixel_norm = float(np.linalg.norm(pixels))
    if pixel_norm:
        pixels /= pixel_norm

    return np.concatenate([hog, pixels * 0.75, geometry.astype(np.float32) * 1.5]).astype(np.float32)


def _classify_glyph(glyph: tuple[np.ndarray, np.ndarray], model: _RestrictedModel) -> tuple[str, float, float]:
    query = _feature_vector(glyph)
    distances = np.linalg.norm(model.features - query, axis=1)
    by_class: list[tuple[str, float]] = []
    for label in model.distance_thresholds:
        class_distances = distances[model.labels == label]
        by_class.append((label, float(class_distances.min())))
    by_class.sort(key=lambda item: item[1])
    (best_label, best_distance), (_, second_distance) = by_class[:2]
    margin = (second_distance - best_distance) / max(second_distance, 1e-9)
    return best_label, best_distance, float(margin)


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
                    distance=round(distance, 6),
                    margin=round(margin, 6),
                )

            distance_score = max(0.0, min(1.0, 1.0 - distance / max(distance_threshold, 1e-6)))
            margin_score = max(0.0, min(1.0, margin / max(margin_threshold * 4, 0.3)))
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
