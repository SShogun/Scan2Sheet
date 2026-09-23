from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from .deskew import deskew
from .enhance import adaptive_threshold, denoise, enhance_contrast, resize_for_ocr
from .orientation import bounded_analysis, detect_orientation_degrees, normalize_orientation
from .quality import QualityProfile, analyze_quality


@dataclass(frozen=True)
class PreprocessResult:
    original_size: tuple[int, int]
    processed_image: Image.Image
    quality_profile: QualityProfile
    transforms_applied: tuple[str, ...]


def _canonical_grayscale(image: Image.Image) -> np.ndarray:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        background = Image.new("RGB", image.size, (255, 255, 255))
        rgba = image.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[3])
        rgb = background
    else:
        rgb = image.convert("RGB")
    return cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2GRAY)


_PAGE_QUAD_MIN_AREA_RATIO = 0.50
_PAGE_QUAD_MIN_SPAN_RATIO = 0.70


def _detect_page_quadrilateral(gray: np.ndarray) -> np.ndarray | None:
    """Find a large page-like quadrilateral on a bounded analysis image."""
    analysis = bounded_analysis(gray)
    blurred = cv2.GaussianBlur(analysis, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    analysis_area = float(analysis.shape[0] * analysis.shape[1])

    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        area_ratio = cv2.contourArea(contour) / analysis_area
        if area_ratio < _PAGE_QUAD_MIN_AREA_RATIO:
            break
        perimeter = cv2.arcLength(contour, True)
        approximation = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approximation) != 4 or not cv2.isContourConvex(approximation):
            continue

        _, _, span_width, span_height = cv2.boundingRect(approximation)
        if (
            span_width / analysis.shape[1] < _PAGE_QUAD_MIN_SPAN_RATIO
            or span_height / analysis.shape[0] < _PAGE_QUAD_MIN_SPAN_RATIO
        ):
            continue

        points = approximation.reshape(4, 2).astype(np.float32)
        scale = np.array(
            [
                gray.shape[1] / analysis.shape[1],
                gray.shape[0] / analysis.shape[0],
            ],
            dtype=np.float32,
        )
        return points * scale
    return None


def _order_quadrilateral(points: np.ndarray) -> np.ndarray:
    ordered = np.empty((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(-1)
    ordered[0] = points[np.argmin(sums)]
    ordered[1] = points[np.argmin(differences)]
    ordered[2] = points[np.argmax(sums)]
    ordered[3] = points[np.argmax(differences)]
    return ordered


def _rectify_page(gray: np.ndarray, points: np.ndarray) -> np.ndarray:
    top_left, top_right, bottom_right, bottom_left = _order_quadrilateral(points)
    width = int(
        round(
            max(
                np.hypot(*(top_right - top_left)),
                np.hypot(*(bottom_right - bottom_left)),
            )
        )
    )
    height = int(
        round(
            max(
                np.hypot(*(bottom_left - top_left)),
                np.hypot(*(bottom_right - top_right)),
            )
        )
    )
    if width < 2 or height < 2:
        return gray

    destination = np.array(
        [
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(
        np.array([top_left, top_right, bottom_right, bottom_left], dtype=np.float32),
        destination,
    )
    return cv2.warpPerspective(
        gray,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )


def preprocess_image(image: Image.Image) -> PreprocessResult:
    original_size = tuple(int(value) for value in image.size)
    gray = _canonical_grayscale(image)
    orientation = detect_orientation_degrees(gray)
    quality = analyze_quality(gray, orientation_degrees=orientation)
    transforms: list[str] = []

    gray, rotation = normalize_orientation(gray, orientation)
    if rotation:
        transforms.append(f"orientation:{rotation}")

    if quality.is_unevenly_illuminated:
        page_quadrilateral = _detect_page_quadrilateral(gray)
        if page_quadrilateral is not None:
            gray = _rectify_page(gray, page_quadrilateral)
            transforms.append("perspective:page_quad")
        gray = enhance_contrast(gray)
        transforms.append("illumination:clahe")

    gray, skew_angle = deskew(gray)
    if skew_angle:
        transforms.append(f"deskew:{skew_angle:.3f}")

    # Denoise before upscaling small images so isolated noise is not enlarged.
    # For large inputs, downscale first so pixel-wise work stays resource-bounded.
    denoised = False
    if quality.is_noisy and max(gray.shape[:2]) <= 4000:
        gray = denoise(gray)
        transforms.append("denoise:median3")
        denoised = True

    gray, resized = resize_for_ocr(gray)
    if resized:
        transforms.append("resize_for_ocr")

    if quality.is_noisy and not denoised:
        gray = denoise(gray)
        transforms.append("denoise:median3")

    if quality.is_low_contrast:
        if not quality.is_unevenly_illuminated:
            gray = enhance_contrast(gray)
            transforms.append("contrast:clahe")
        gray = adaptive_threshold(gray)
        transforms.append("threshold:adaptive_gaussian")

    return PreprocessResult(
        original_size=original_size,
        processed_image=Image.fromarray(gray),
        quality_profile=quality,
        transforms_applied=tuple(transforms),
    )
