from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from .deskew import deskew
from .enhance import adaptive_threshold, denoise, enhance_contrast, resize_for_ocr
from .orientation import detect_orientation_degrees, normalize_orientation
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


def preprocess_image(image: Image.Image) -> PreprocessResult:
    original_size = tuple(int(value) for value in image.size)
    gray = _canonical_grayscale(image)
    orientation = detect_orientation_degrees(gray)
    quality = analyze_quality(gray, orientation_degrees=orientation)
    transforms: list[str] = []

    gray, rotation = normalize_orientation(gray, orientation)
    if rotation:
        transforms.append(f"orientation:{rotation}")

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
