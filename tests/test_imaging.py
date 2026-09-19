from pathlib import Path
import numpy as np
from PIL import Image
from backend.app.imaging.pipeline import preprocess_image
from tests.generate_ocr_fixtures import ensure_fixtures
ROOT=Path(__file__).resolve().parent/'ocr_fixtures'
def _load(category): ensure_fixtures(); return Image.open(next((ROOT/category).glob('invoice_01.*')))
def test_blurred_input_is_flagged_without_sharpening():
    r=preprocess_image(_load('blurred')); assert r.quality_profile.is_blurred and 'severe_blur' in r.quality_profile.warnings and not any('sharpen' in x for x in r.transforms_applied)
def test_rotated_input_applies_orientation_normalization(): assert 'orientation:90' in preprocess_image(_load('rotated')).transforms_applied
def test_skewed_input_applies_bounded_deskew():
    d=[x for x in preprocess_image(_load('skewed')).transforms_applied if x.startswith('deskew:')]; assert len(d)==1 and -10.0<=float(d[0].split(':')[1])<=-3.0
def test_noisy_input_uses_median_denoise():
    r=preprocess_image(_load('noisy')); assert r.quality_profile.is_noisy and 'denoise:median3' in r.transforms_applied
def test_low_contrast_input_uses_clahe_and_adaptive_threshold():
    r=preprocess_image(_load('low_contrast')); assert r.quality_profile.is_low_contrast and 'contrast:clahe' in r.transforms_applied and 'threshold:adaptive_gaussian' in r.transforms_applied
def test_clean_input_avoids_damage_prone_enhancements():
    r=preprocess_image(_load('clean')); assert not r.quality_profile.is_blurred and not r.quality_profile.is_low_contrast and not r.quality_profile.is_noisy; assert 'denoise:median3' not in r.transforms_applied and 'contrast:clahe' not in r.transforms_applied and 'threshold:adaptive_gaussian' not in r.transforms_applied
def test_processed_pixels_are_deterministic():
    image=_load('clean'); a=preprocess_image(image); b=preprocess_image(image); assert np.array_equal(np.asarray(a.processed_image),np.asarray(b.processed_image)); assert a.quality_profile==b.quality_profile and a.transforms_applied==b.transforms_applied
def test_clean_white_background_is_not_treated_as_impulse_noise():
    r=preprocess_image(Image.new('L',(800,600),255)); assert not r.quality_profile.is_noisy and 'denoise:median3' not in r.transforms_applied

def test_upside_down_input_applies_180_orientation_normalization() -> None:
    image = _load('clean').rotate(180, expand=True, fillcolor=(250, 250, 247))
    result = preprocess_image(image)
    assert 'orientation:180' in result.transforms_applied


def test_quality_analysis_is_bounded_for_large_images(monkeypatch) -> None:
    from backend.app.imaging import quality as quality_module
    original = quality_module.cv2.Laplacian
    seen = {}
    def recording_laplacian(image, depth):
        seen['shape'] = image.shape
        return original(image, depth)
    monkeypatch.setattr(quality_module.cv2, 'Laplacian', recording_laplacian)
    image = Image.new('L', (6000, 5000), 240)
    preprocess_image(image)
    assert max(seen['shape']) <= 1600
