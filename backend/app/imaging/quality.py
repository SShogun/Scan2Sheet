from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .deskew import estimate_skew_degrees
from .orientation import orientation_hint_degrees

BLUR_VARIANCE_THRESHOLD = 20.0
LOW_CONTRAST_STDDEV_THRESHOLD = 15.0
IMPULSE_NOISE_THRESHOLD = 0.01


@dataclass(frozen=True)
class QualityProfile:
    width: int
    height: int
    mean_intensity: float
    intensity_stddev: float
    p05: float
    p95: float
    dynamic_range: float
    laplacian_variance: float
    impulse_noise_fraction: float
    orientation_degrees: int
    estimated_skew_degrees: float
    is_blurred: bool
    is_low_contrast: bool
    is_noisy: bool
    warnings: tuple[str, ...]


def analyze_quality(gray: np.ndarray) -> QualityProfile:
    if gray.ndim != 2:
        raise ValueError("Quality analysis requires a grayscale image.")

    p05, p95 = np.percentile(gray, [5, 95])
    laplacian_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    stddev = float(np.std(gray))
    local_median = cv2.medianBlur(gray, 3)
    impulse_noise_fraction = float(np.mean(cv2.absdiff(gray, local_median) >= 80))
    orientation = orientation_hint_degrees(gray)
    skew = 0.0 if orientation else estimate_skew_degrees(gray)

    is_blurred = laplacian_variance < BLUR_VARIANCE_THRESHOLD
    is_low_contrast = stddev < LOW_CONTRAST_STDDEV_THRESHOLD
    is_noisy = impulse_noise_fraction >= IMPULSE_NOISE_THRESHOLD

    warnings: list[str] = []
    if is_blurred:
        warnings.append("severe_blur")
    if is_low_contrast:
        warnings.append("low_contrast")
    if is_noisy:
        warnings.append("impulse_noise")
    if orientation:
        warnings.append("orientation")
    if abs(skew) >= 0.5:
        warnings.append("skew")

    return QualityProfile(
        width=int(gray.shape[1]),
        height=int(gray.shape[0]),
        mean_intensity=round(float(np.mean(gray)), 6),
        intensity_stddev=round(stddev, 6),
        p05=round(float(p05), 6),
        p95=round(float(p95), 6),
        dynamic_range=round(float(p95 - p05), 6),
        laplacian_variance=round(laplacian_variance, 6),
        impulse_noise_fraction=round(impulse_noise_fraction, 8),
        orientation_degrees=orientation,
        estimated_skew_degrees=round(skew, 6),
        is_blurred=is_blurred,
        is_low_contrast=is_low_contrast,
        is_noisy=is_noisy,
        warnings=tuple(warnings),
    )
