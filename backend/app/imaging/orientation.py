from __future__ import annotations

import cv2
import numpy as np
import pytesseract
from PIL import Image

ANALYSIS_MAX_DIMENSION = 1600
OSD_TIMEOUT_SECONDS = 5


def bounded_analysis(gray: np.ndarray, max_dimension: int = ANALYSIS_MAX_DIMENSION) -> np.ndarray:
    """Return a deterministic bounded grayscale representation for analysis only."""
    height, width = gray.shape[:2]
    largest = max(width, height)
    if largest <= max_dimension:
        return gray
    scale = max_dimension / float(largest)
    return cv2.resize(
        gray,
        (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
        interpolation=cv2.INTER_AREA,
    )


def estimate_dominant_line_angle(gray: np.ndarray) -> float:
    """Estimate dominant page/text angle in OpenCV coordinates, modulo 180."""
    analysis = bounded_analysis(gray)
    edges = cv2.Canny(analysis, 50, 150, apertureSize=3)
    min_line = max(50, int(min(analysis.shape[:2]) * 0.18))
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=80,
        minLineLength=min_line,
        maxLineGap=20,
    )
    if lines is None:
        return 0.0

    candidates: list[tuple[float, float]] = []
    for x1, y1, x2, y2 in lines[:, 0]:
        dx = float(x2 - x1)
        dy = float(y2 - y1)
        length = float(np.hypot(dx, dy))
        angle = float(np.degrees(np.arctan2(dy, dx)))
        if angle < -90.0:
            angle += 180.0
        if angle >= 90.0:
            angle -= 180.0
        candidates.append((angle, length))

    if not candidates:
        return 0.0
    longest = sorted(candidates, key=lambda item: item[1], reverse=True)[:5]
    return float(np.median([item[0] for item in longest]))


def detect_orientation_degrees(gray: np.ndarray) -> int:
    """Return the clockwise 0/90/180/270 correction reported by local Tesseract OSD.

    OSD always receives a bounded analysis image and a hard timeout. Failures are
    a deterministic safe no-op rather than an unbounded preprocessing stall.
    """
    analysis = bounded_analysis(gray)
    try:
        osd = pytesseract.image_to_osd(
            Image.fromarray(analysis),
            output_type=pytesseract.Output.DICT,
            timeout=OSD_TIMEOUT_SECONDS,
        )
        rotation = int(osd.get("rotate", 0)) % 360
    except (pytesseract.TesseractError, RuntimeError, ValueError, TypeError):
        return 0
    return rotation if rotation in {0, 90, 180, 270} else 0


def orientation_hint_degrees(gray: np.ndarray) -> int:
    """Backward-compatible alias for the bounded 0/90/180/270 detector."""
    return detect_orientation_degrees(gray)


def _rotate_quadrant(gray: np.ndarray, clockwise_degrees: int) -> np.ndarray:
    rotation = clockwise_degrees % 360
    if rotation == 0:
        return gray
    if rotation == 90:
        return cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)
    if rotation == 180:
        return cv2.rotate(gray, cv2.ROTATE_180)
    if rotation == 270:
        return cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError(f"Unsupported quadrant rotation: {clockwise_degrees}")


def normalize_orientation(gray: np.ndarray, rotation: int | None = None) -> tuple[np.ndarray, int]:
    correction = detect_orientation_degrees(gray) if rotation is None else int(rotation) % 360
    if correction not in {90, 180, 270}:
        return gray, 0
    return _rotate_quadrant(gray, correction), correction
