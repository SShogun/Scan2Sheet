from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import pytest
from PIL import Image

from backend.app.ocr.experimental import RestrictedExperimentalEngine
from backend.app.ocr.router import OCRRouter
from backend.app.ocr.types import OCRResult
from tools.evaluate_restricted_recognizer import evaluate
from tools.recognizer_dataset import load_manifest, render_sample
from tools.train_restricted_recognizer import MODEL_ARCHIVE_TIMESTAMP, MODEL_MEMBER_ORDER, train


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL_HASH = (
    ROOT / "experiments/m2b-hog-nn-v1/model_hash.txt"
).read_text(encoding="utf-8").strip()


@pytest.fixture(scope="session")
def reproduced_model(tmp_path_factory: pytest.TempPathFactory) -> Path:
    work = tmp_path_factory.mktemp("restricted-recognizer")
    model = work / "restricted_hog_nn_v1.npz"
    actual = train(
        ROOT / "data/recognizer/train/manifest.json",
        ROOT / "data/recognizer/validation/manifest.json",
        model,
        work / "experiment",
    )
    assert actual == EXPECTED_MODEL_HASH
    return model


def _sample(split: str, text: str) -> dict[str, object]:
    manifest = load_manifest(
        ROOT / "data" / "recognizer" / split / "manifest.json"
    )
    return next(sample for sample in manifest["samples"] if sample["text"] == text)


def _engine(model: Path) -> RestrictedExperimentalEngine:
    return RestrictedExperimentalEngine(model)


def test_red_20_unknown_characters_abstain_instead_of_hallucinating(
    reproduced_model: Path,
) -> None:
    sample = _sample("validation", "INV@102")
    result = _engine(reproduced_model).recognize(render_sample(sample))

    assert result.abstained
    assert result.text == ""
    assert result.metadata["reason"] == "unknown_or_uncertain"


def test_red_21_confident_primary_skips_secondary_and_never_gets_overridden() -> None:
    calls: list[int] = []

    class Primary:
        def recognize(self, image: Image.Image) -> OCRResult:
            return OCRResult("PRIMARY", 90.0, "tesseract", {})

    class Secondary:
        def recognize(self, image: Image.Image) -> OCRResult:
            calls.append(1)
            return OCRResult(
                "SECONDARY",
                10.0,
                "experimental-restricted-v1",
                {"experimental": True},
            )

    router = OCRRouter(
        Primary(),
        Secondary(),
        secondary_trigger_confidence=60.0,
    )
    result = router.recognize(Image.new("L", (20, 20), 255))

    assert result.text == "PRIMARY"
    assert result.engine == "tesseract"
    assert not calls
    assert result.metadata["secondary_skipped"] == "primary_confident"


def test_red_21_low_confidence_secondary_is_only_a_candidate() -> None:
    class Primary:
        def recognize(self, image: Image.Image) -> OCRResult:
            return OCRResult("PRIMARY", 20.0, "tesseract", {})

    class Secondary:
        def recognize(self, image: Image.Image) -> OCRResult:
            return OCRResult(
                "SECONDARY",
                10.0,
                "experimental-restricted-v1",
                {"experimental": True},
            )

    result = OCRRouter(
        Primary(),
        Secondary(),
        secondary_trigger_confidence=60.0,
    ).recognize(Image.new("L", (20, 20), 255))

    assert result.text == "PRIMARY"
    assert result.engine == "tesseract"
    assert result.metadata["secondary_candidate"]["text"] == "SECONDARY"
    assert result.metadata["secondary_candidate"]["confidence"] == 10.0


def test_red_22_zero_o_one_i_confusion_is_represented_and_recognized(
    reproduced_model: Path,
) -> None:
    sample = _sample("validation", "INV-0O1I")
    result = _engine(reproduced_model).recognize(render_sample(sample))

    assert not result.abstained
    assert result.text == "INV-0O1I"


def test_red_22_decimal_and_comma_amount_is_represented_and_recognized(
    reproduced_model: Path,
) -> None:
    sample = _sample("validation", "12,345.67")
    result = _engine(reproduced_model).recognize(render_sample(sample))

    assert not result.abstained
    assert result.text == "12,345.67"


def test_red_23_train_and_heldout_hashes_do_not_overlap() -> None:
    train_manifest = load_manifest(
        ROOT / "data/recognizer/train/manifest.json"
    )
    validation_manifest = load_manifest(
        ROOT / "data/recognizer/validation/manifest.json"
    )
    test_manifest = load_manifest(
        ROOT / "data/recognizer/test/manifest.json"
    )

    train_hashes = {
        sample["sha256"] for sample in train_manifest["samples"]
    }
    validation_hashes = {
        sample["sha256"] for sample in validation_manifest["samples"]
    }
    test_hashes = {
        sample["sha256"] for sample in test_manifest["samples"]
    }

    assert train_hashes.isdisjoint(test_hashes)
    assert validation_hashes.isdisjoint(test_hashes)


def test_red_24_experimental_result_has_explicit_provenance(
    reproduced_model: Path,
) -> None:
    sample = _sample("validation", "12,345.67")
    result = _engine(reproduced_model).recognize(render_sample(sample))

    assert result.engine == "experimental-restricted-v1"
    assert result.metadata["experimental"] is True
    assert result.metadata["scope"] == "restricted-token"
    assert result.metadata["not_general_purpose_ocr"] is True
    assert result.metadata["model_sha256"] == EXPECTED_MODEL_HASH


def test_red_25_experimental_failure_cannot_break_primary_ocr() -> None:
    class Primary:
        def recognize(self, image: Image.Image) -> OCRResult:
            return OCRResult("PRIMARY", 20.0, "tesseract", {})

    class FailingSecondary:
        def recognize(self, image: Image.Image) -> OCRResult:
            raise RuntimeError("boom")

    result = OCRRouter(
        Primary(),
        FailingSecondary(),
        secondary_trigger_confidence=60.0,
    ).recognize(Image.new("L", (20, 20), 255))

    assert result.text == "PRIMARY"
    assert result.engine == "tesseract"
    assert result.metadata["secondary_error"] == "RuntimeError"


def test_model_hash_matches_frozen_test_manifest(
    reproduced_model: Path,
) -> None:
    actual = hashlib.sha256(reproduced_model.read_bytes()).hexdigest()
    test_manifest = load_manifest(
        ROOT / "data/recognizer/test/manifest.json"
    )

    assert actual == EXPECTED_MODEL_HASH
    assert test_manifest["frozen_model_sha256"] == EXPECTED_MODEL_HASH


def test_model_archive_has_canonical_metadata(
    reproduced_model: Path,
) -> None:
    with zipfile.ZipFile(reproduced_model) as archive:
        entries = archive.infolist()

    assert [entry.filename for entry in entries] == [
        f"{name}.npy" for name in MODEL_MEMBER_ORDER
    ]
    assert all(entry.compress_type == zipfile.ZIP_STORED for entry in entries)
    assert all(entry.date_time == MODEL_ARCHIVE_TIMESTAMP for entry in entries)
    assert all(entry.create_system == 3 for entry in entries)
    assert all(entry.external_attr == 0o600 << 16 for entry in entries)


def test_model_generation_is_byte_stable(
    reproduced_model: Path,
    tmp_path: Path,
) -> None:
    second_model = tmp_path / "restricted_hog_nn_v1-second.npz"
    second_hash = train(
        ROOT / "data/recognizer/train/manifest.json",
        ROOT / "data/recognizer/validation/manifest.json",
        second_model,
    )

    assert second_hash == EXPECTED_MODEL_HASH
    assert second_model.read_bytes() == reproduced_model.read_bytes()


def test_trainer_does_not_read_heldout_test_manifest() -> None:
    source = (
        ROOT / "tools/train_restricted_recognizer.py"
    ).read_text(encoding="utf-8")

    assert "data/recognizer/test" not in source
    assert "--test-manifest" not in source


def test_default_generation_paths_do_not_overwrite_frozen_evidence() -> None:
    trainer = (
        ROOT / "tools/train_restricted_recognizer.py"
    ).read_text(encoding="utf-8")
    evaluator = (
        ROOT / "tools/evaluate_restricted_recognizer.py"
    ).read_text(encoding="utf-8")

    assert 'default=Path("artifacts/generated/m2b-current")' in trainer
    assert 'default=Path("artifacts/benchmarks/current_m2b_recognizer.json")' in evaluator


def test_heldout_report_records_safe_abstention_without_claiming_superiority() -> None:
    report = json.loads(
        (
            ROOT / "artifacts/benchmarks/m2b_recognizer.json"
        ).read_text(encoding="utf-8")
    )

    assert report["experimental_unknown_abstention_rate"] == 1.0
    assert report["experimental_known_exact_accuracy"] > 0.0
    assert report["model_sha256"] == EXPECTED_MODEL_HASH


def test_evaluator_rejects_model_hash_mismatch(
    reproduced_model: Path,
    tmp_path: Path,
) -> None:
    mutated = tmp_path / "mutated-model.npz"
    mutated.write_bytes(reproduced_model.read_bytes() + b"x")

    with pytest.raises(RuntimeError, match="Model hash mismatch"):
        evaluate(
            mutated,
            ROOT / "data/recognizer/train/manifest.json",
            ROOT / "data/recognizer/test/manifest.json",
            tmp_path / "heldout.json",
        )


def test_reproducibility_dependencies_are_pinned() -> None:
    pins = {
        line.strip()
        for line in (ROOT / "backend/requirements-repro.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert pins == {
        "numpy==2.4.6",
        "opencv-python==4.14.0.94",
        "Pillow==11.3.0",
    }
