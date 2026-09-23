from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .deskew import estimate_skew_degrees
from .orientation import bounded_analysis

BLUR_VARIANCE_THRESHOLD = 20.0
LOW_CONTRAST_STDDEV_THRESHOLD = 15.0
IMPULSE_NOISE_THRESHOLD = 0.01
UNEVEN_ILLUMINATION_RANGE_THRESHOLD = 40.0
ILLUMINATION_ANALYSIS_SIZE = 32


@dataclass(frozen=True)
class QualityProfile:
    width: int
    height: int
    mean_intensity: float
    intensity_stddev: float
    p05: float
    p95: float
    dynamic_range: float
    illumination_range: float
    laplacian_variance: float
    impulse_noise_fraction: float
    orientation_degrees: int
    estimated_skew_degrees: float
    is_blurred: bool
    is_low_contrast: bool
    is_noisy: bool
    is_unevenly_illuminated: bool
    warnings: tuple[str, ...]


def analyze_quality(gray: np.ndarray, *, orientation_degrees: int = 0) -> QualityProfile:
    if gray.ndim != 2:
        raise ValueError("Quality analysis requires a grayscale image.")

    analysis = bounded_analysis(gray)
    p05, p95 = np.percentile(analysis, [5, 95])
    laplacian_variance = float(cv2.Laplacian(analysis, cv2.CV_64F).var())
    stddev = float(np.std(analysis))
    illumination_sample = cv2.resize(
        analysis,
        (ILLUMINATION_ANALYSIS_SIZE, ILLUMINATION_ANALYSIS_SIZE),
        interpolation=cv2.INTER_AREA,
    )
    illumination = cv2.GaussianBlur(
        illumination_sample,
        (0, 0),
        sigmaX=2.0,
        sigmaY=2.0,
    )
    illumination_p05, illumination_p95 = np.percentile(illumination, [5, 95])
    illumination_range = float(illumination_p95 - illumination_p05)
    local_median = cv2.medianBlur(analysis, 3)
    impulse_noise_fraction = float(np.mean(cv2.absdiff(analysis, local_median) >= 80))
    skew = 0.0 if orientation_degrees else estimate_skew_degrees(analysis)

    is_blurred = laplacian_variance < BLUR_VARIANCE_THRESHOLD
    is_low_contrast = stddev < LOW_CONTRAST_STDDEV_THRESHOLD
    is_noisy = impulse_noise_fraction >= IMPULSE_NOISE_THRESHOLD
    is_unevenly_illuminated = illumination_range >= UNEVEN_ILLUMINATION_RANGE_THRESHOLD

    warnings: list[str] = []
    if is_blurred:
        warnings.append("severe_blur")
    if is_low_contrast:
        warnings.append("low_contrast")
    if is_noisy:
        warnings.append("impulse_noise")
    if is_unevenly_illuminated:
        warnings.append("uneven_illumination")
    if orientation_degrees:
        warnings.append("orientation")
    if abs(skew) >= 0.5:
        warnings.append("skew")

    return QualityProfile(
        width=int(gray.shape[1]),
        height=int(gray.shape[0]),
        mean_intensity=round(float(np.mean(analysis)), 6),
        intensity_stddev=round(stddev, 6),
        p05=round(float(p05), 6),
        p95=round(float(p95), 6),
        dynamic_range=round(float(p95 - p05), 6),
        illumination_range=round(illumination_range, 6),
        laplacian_variance=round(laplacian_variance, 6),
        impulse_noise_fraction=round(impulse_noise_fraction, 8),
        orientation_degrees=orientation_degrees,
        estimated_skew_degrees=round(skew, 6),
        is_blurred=is_blurred,
        is_low_contrast=is_low_contrast,
        is_noisy=is_noisy,
        is_unevenly_illuminated=is_unevenly_illuminated,
        warnings=tuple(warnings),
    )
