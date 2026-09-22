from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import numpy as np
from PIL import Image

from backend.app.ocr.experimental import RestrictedExperimentalEngine, restricted_model_contract_for_path
from backend.app.ocr.router import OCRRouter
from backend.app.ocr.types import OCRResult
from tools.evaluate_restricted_recognizer import evaluate
from tools.recognizer_dataset import load_manifest, render_sample
from tools.train_restricted_recognizer import train


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL_HASH = (
    ROOT / "experiments/m2b-hog-nn-v1/model_hash.txt"
).read_text(encoding="utf-8").strip()
EXPECTED_MODEL_CONTRACT = (
    ROOT / "experiments/m2b-hog-nn-v1/model_contract_hash.txt"
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
    assert actual == EXPECTED_MODEL_CONTRACT
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
    assert len(result.metadata["model_sha256"]) == 64
    assert result.metadata["model_contract_sha256"] == EXPECTED_MODEL_CONTRACT
    assert len(result.metadata["model_integrity_sha256"]) == 64


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


def test_model_contract_matches_frozen_test_manifest(
    reproduced_model: Path,
) -> None:
    actual_contract = restricted_model_contract_for_path(reproduced_model)
    actual_file_sha256 = hashlib.sha256(reproduced_model.read_bytes()).hexdigest()
    test_manifest = load_manifest(
        ROOT / "data/recognizer/test/manifest.json"
    )

    assert actual_contract == EXPECTED_MODEL_CONTRACT
    assert len(actual_file_sha256) == 64
    assert test_manifest["frozen_model_sha256"] == EXPECTED_MODEL_HASH
    assert test_manifest["frozen_model_contract_sha256"] == EXPECTED_MODEL_CONTRACT


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
    assert report["model_contract_sha256"] == EXPECTED_MODEL_CONTRACT


def test_evaluator_rejects_model_hash_mismatch(
    reproduced_model: Path,
    tmp_path: Path,
) -> None:
    mutated = tmp_path / "mutated-model.npz"
    with np.load(reproduced_model, allow_pickle=False) as data:
        payload = {key: np.asarray(data[key]).copy() for key in data.files}
    payload["features"][0, 0] += 0.1
    np.savez_compressed(mutated, **payload)

    with pytest.raises(RuntimeError, match="Model integrity mismatch"):
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
