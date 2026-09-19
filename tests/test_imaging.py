from pathlib import Path

import numpy as np
from PIL import Image

from backend.app.imaging.pipeline import preprocess_image
from tests.generate_ocr_fixtures import ensure_fixtures

ROOT = Path(__file__).resolve().parent / "ocr_fixtures"


def _load(category: str) -> Image.Image:
    ensure_fixtures()
    return Image.open(next((ROOT / category).glob("invoice_01.*")))


def test_blurred_input_is_flagged_without_sharpening() -> None:
    result = preprocess_image(_load("blurred"))
    assert result.quality_profile.is_blurred
    assert "severe_blur" in result.quality_profile.warnings
    assert not any("sharpen" in item for item in result.transforms_applied)


def test_rotated_input_applies_orientation_normalization() -> None:
    result = preprocess_image(_load("rotated"))
    assert "orientation:90" in result.transforms_applied


def test_skewed_input_applies_bounded_deskew() -> None:
    result = preprocess_image(_load("skewed"))
    deskews = [item for item in result.transforms_applied if item.startswith("deskew:")]
    assert len(deskews) == 1
    angle = float(deskews[0].split(":", 1)[1])
    assert -10.0 <= angle <= -3.0


def test_noisy_input_uses_median_denoise() -> None:
    result = preprocess_image(_load("noisy"))
    assert result.quality_profile.is_noisy
    assert "denoise:median3" in result.transforms_applied


def test_low_contrast_input_uses_clahe_and_adaptive_threshold() -> None:
    result = preprocess_image(_load("low_contrast"))
    assert result.quality_profile.is_low_contrast
    assert "contrast:clahe" in result.transforms_applied
    assert "threshold:adaptive_gaussian" in result.transforms_applied


def test_clean_input_avoids_damage_prone_enhancements() -> None:
    result = preprocess_image(_load("clean"))
    assert not result.quality_profile.is_blurred
    assert not result.quality_profile.is_low_contrast
    assert not result.quality_profile.is_noisy
    assert "denoise:median3" not in result.transforms_applied
    assert "contrast:clahe" not in result.transforms_applied
    assert "threshold:adaptive_gaussian" not in result.transforms_applied


def test_processed_pixels_are_deterministic() -> None:
    image = _load("clean")
    first = preprocess_image(image)
    second = preprocess_image(image)
    assert first == second or np.array_equal(np.asarray(first.processed_image), np.asarray(second.processed_image))
    assert first.quality_profile == second.quality_profile
    assert first.transforms_applied == second.transforms_applied
