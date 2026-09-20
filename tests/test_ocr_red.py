from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from PIL import Image


def _field_accuracy(metrics_by_category: dict[str, dict[str, object]], category: str) -> float:
    return float(metrics_by_category[category]["important_field_accuracy"])


def test_red_01_rotation_should_preserve_clean_field_accuracy(metrics_by_category) -> None:
    clean = _field_accuracy(metrics_by_category, "clean")
    rotated = _field_accuracy(metrics_by_category, "rotated")
    assert rotated >= clean - 0.05, (
        f"RED-01: rotated field accuracy {rotated:.3f} is far below clean {clean:.3f}; "
        "coarse orientation normalization is missing."
    )


def test_red_02_skew_should_preserve_most_clean_field_accuracy(metrics_by_category) -> None:
    clean = _field_accuracy(metrics_by_category, "clean")
    skewed = _field_accuracy(metrics_by_category, "skewed")
    assert skewed >= clean - 0.10, (
        f"RED-02: +9 degree skew field accuracy {skewed:.3f} is far below clean {clean:.3f}; "
        "small-angle deskew is missing."
    )


def test_red_03_low_contrast_should_remain_ocr_readable(metrics_by_category) -> None:
    clean = _field_accuracy(metrics_by_category, "clean")
    low_contrast = _field_accuracy(metrics_by_category, "low_contrast")
    assert low_contrast >= clean - 0.10, (
        f"RED-03: low-contrast field accuracy {low_contrast:.3f} is far below clean {clean:.3f}; "
        "conditional contrast/threshold handling is missing."
    )


def test_red_04_noise_should_remain_ocr_readable(metrics_by_category) -> None:
    clean = _field_accuracy(metrics_by_category, "clean")
    noisy = _field_accuracy(metrics_by_category, "noisy")
    assert noisy >= clean - 0.15, (
        f"RED-04: noisy field accuracy {noisy:.3f} is far below clean {clean:.3f}; "
        "bounded denoising is missing."
    )


def test_red_05_severe_blur_must_be_flagged(metrics_by_category) -> None:
    try:
        pipeline = importlib.import_module("backend.app.imaging.pipeline")
    except ModuleNotFoundError as exc:
        pytest.fail(f"RED-05: severe blur flagging is not implemented yet: {exc}")

    fixture = Path(__file__).parent / "ocr_fixtures" / metrics_by_category["blurred"]["fixture"]
    result = pipeline.preprocess_image(Image.open(fixture))
    assert result.quality_profile.is_blurred, "RED-05: severe blur must be flagged independently of OCR text length."


def test_red_06_clean_non_regression_control(metrics_by_category) -> None:
    clean = metrics_by_category["clean"]
    assert float(clean["cer"]) <= 0.02
    assert float(clean["important_field_accuracy"]) >= 0.80


def test_red_07_preprocessing_profile_must_be_deterministic(fixture_manifest) -> None:
    try:
        pipeline = importlib.import_module("backend.app.imaging.pipeline")
    except ModuleNotFoundError as exc:
        pytest.fail(f"RED-07: deterministic preprocessing profile contract is not implemented yet: {exc}")

    fixture_root = Path(__file__).parent / "ocr_fixtures"
    clean_item = next(item for item in fixture_manifest["fixtures"] if item["category"] == "clean")
    image = Image.open(fixture_root / clean_item["fixture"])
    first = pipeline.preprocess_image(image)
    second = pipeline.preprocess_image(image)
    assert first.original_size == second.original_size
    assert first.quality_profile == second.quality_profile
    assert first.transforms_applied == second.transforms_applied
