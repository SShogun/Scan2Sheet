from __future__ import annotations

import cv2
import numpy as np
import pytesseract
from PIL import Image


def estimate_dominant_line_angle(gray: np.ndarray) -> float:
    """Estimate dominant page/text angle in OpenCV coordinates, modulo 180."""
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    min_line = max(50, int(min(gray.shape[:2]) * 0.18))
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


def orientation_hint_degrees(gray: np.ndarray) -> int:
    """Return 90 when page structure is clearly vertical, else 0.

    The hint deliberately does not guess clockwise vs counter-clockwise. That
    direction is resolved locally by Tesseract OSD only when a 90-degree
    orientation correction is actually indicated.
    """
    return 90 if abs(estimate_dominant_line_angle(gray)) > 45.0 else 0


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


def normalize_orientation(gray: np.ndarray) -> tuple[np.ndarray, int]:
    """Normalize a clearly sideways page using local Tesseract OSD.

    OSD is only consulted after image geometry indicates a coarse 90-degree
    problem. Failure is a safe no-op; preprocessing never calls a network.
    """
    if orientation_hint_degrees(gray) == 0:
        return gray, 0

    try:
        osd = pytesseract.image_to_osd(Image.fromarray(gray), output_type=pytesseract.Output.DICT)
        rotation = int(osd.get("rotate", 0)) % 360
    except (pytesseract.TesseractError, RuntimeError, ValueError, TypeError):
        return gray, 0

    if rotation not in {90, 180, 270}:
        return gray, 0
    return _rotate_quadrant(gray, rotation), rotation
