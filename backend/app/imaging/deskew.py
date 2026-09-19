from __future__ import annotations

import cv2
import numpy as np

from .orientation import estimate_dominant_line_angle

MAX_DESKEW_DEGREES = 12.0
MIN_DESKEW_DEGREES = 0.5


def estimate_skew_degrees(gray: np.ndarray) -> float:
    angle = estimate_dominant_line_angle(gray)
    if abs(angle) > 45.0:
        return 0.0
    return angle


def rotate_bound(gray: np.ndarray, angle_degrees: float) -> np.ndarray:
    height, width = gray.shape[:2]
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, angle_degrees, 1.0)
    cosine = abs(matrix[0, 0])
    sine = abs(matrix[0, 1])
    new_width = int((height * sine) + (width * cosine))
    new_height = int((height * cosine) + (width * sine))
    matrix[0, 2] += (new_width / 2.0) - center[0]
    matrix[1, 2] += (new_height / 2.0) - center[1]
    return cv2.warpAffine(
        gray,
        matrix,
        (new_width, new_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )


def deskew(gray: np.ndarray) -> tuple[np.ndarray, float]:
    angle = estimate_skew_degrees(gray)
    if not (MIN_DESKEW_DEGREES <= abs(angle) <= MAX_DESKEW_DEGREES):
        return gray, 0.0
    return rotate_bound(gray, angle), angle
