from __future__ import annotations

import cv2
import numpy as np


def denoise(gray: np.ndarray) -> np.ndarray:
    """Remove bounded impulse noise while preserving text edges."""
    return cv2.medianBlur(gray, 3)


def enhance_contrast(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=1.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def adaptive_threshold(gray: np.ndarray) -> np.ndarray:
    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        51,
        9,
    )


def resize_for_ocr(gray: np.ndarray) -> tuple[np.ndarray, bool]:
    """Preserve the pre-M1B Tesseract sizing policy."""
    height, width = gray.shape[:2]
    max_dimension = max(width, height)
    if max_dimension < 2500:
        scale = 2500.0 / max_dimension
        resized = cv2.resize(
            gray,
            (int(round(width * scale)), int(round(height * scale))),
            interpolation=cv2.INTER_LANCZOS4,
        )
        return resized, True
    if max_dimension > 4000:
        scale = 4000.0 / max_dimension
        resized = cv2.resize(
            gray,
            (int(round(width * scale)), int(round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
        return resized, True
    return gray, False
