from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.ocr.experimental import MIN_TOKEN_CONFIDENCE, RESTRICTED_VOCABULARY, RestrictedExperimentalEngine, _feature_vector, _segment_glyphs
from tools.recognizer_dataset import load_manifest, render_sample, verify_manifest


MODEL_ARCHIVE_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
MODEL_MEMBER_ORDER = (
    "features",
    "labels",
    "class_labels",
    "distance_thresholds",
    "margin_thresholds",
)


def _classify(glyph, features: np.ndarray, labels: np.ndarray) -> tuple[str, float, float]:
    query = _feature_vector(glyph)
    distances = np.linalg.norm(features - query, axis=1)
    ranked = sorted(((label, float(distances[labels == label].min())) for label in sorted(set(labels.tolist()))), key=lambda item: (item[1], item[0]))
    (best, d1), (_, d2) = ranked[:2]
    return str(best), d1, float((d2 - d1) / max(d2, 1e-9))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _npy_bytes(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    np.save(buffer, np.ascontiguousarray(array), allow_pickle=False)
    return buffer.getvalue()


def _write_deterministic_model(output_model: Path, arrays: dict[str, np.ndarray]) -> None:
    missing = set(MODEL_MEMBER_ORDER) - arrays.keys()
    extra = arrays.keys() - set(MODEL_MEMBER_ORDER)
    if missing or extra:
        raise ValueError(f"Unexpected model arrays: missing={sorted(missing)}, extra={sorted(extra)}")

    output_model.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_model, mode="w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for name in MODEL_MEMBER_ORDER:
            info = zipfile.ZipInfo(f"{name}.npy", date_time=MODEL_ARCHIVE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o600 << 16
            info.flag_bits = 0
            archive.writestr(info, _npy_bytes(arrays[name]))


def train(train_manifest_path: Path, validation_manifest_path: Path, output_model: Path, experiment_dir: Path | None = None) -> str:
    verify_manifest(train_manifest_path); verify_manifest(validation_manifest_path)
    train_manifest = load_manifest(train_manifest_path); validation_manifest = load_manifest(validation_manifest_path)
    train_hashes = {sample["sha256"] for sample in train_manifest["samples"]}; validation_hashes = {sample["sha256"] for sample in validation_manifest["samples"]}
    if train_hashes & validation_hashes:
        raise RuntimeError("Train/validation leakage detected.")

    features, labels = [], []
    for sample in train_manifest["samples"]:
        if sample.get("expected_abstain"):
            raise RuntimeError("Abstention samples are not permitted in training.")
        text = str(sample["text"]); glyphs = _segment_glyphs(render_sample(sample))
        if len(glyphs) != len(text):
            raise RuntimeError(f"Training segmentation mismatch for {sample['id']}.")
        for character, glyph in zip(text, glyphs, strict=True):
            if character not in RESTRICTED_VOCABULARY:
                raise RuntimeError(f"Out-of-vocabulary training character: {character!r}")
            features.append(_feature_vector(glyph)); labels.append(character)

    matrix = np.stack(features).astype(np.float32); label_array = np.asarray(labels, dtype="<U1")
    if set(label_array.tolist()) != set(RESTRICTED_VOCABULARY):
        raise RuntimeError("Training data does not cover the complete restricted vocabulary.")

    known_distance = {char: [] for char in RESTRICTED_VOCABULARY}; known_margin = {char: [] for char in RESTRICTED_VOCABULARY}; unknown = {char: [] for char in RESTRICTED_VOCABULARY}
    for sample in validation_manifest["samples"]:
        text = str(sample["text"]); glyphs = _segment_glyphs(render_sample(sample))
        if len(glyphs) != len(text):
            raise RuntimeError(f"Validation segmentation mismatch for {sample['id']}.")
        for character, glyph in zip(text, glyphs, strict=True):
            predicted, distance, margin = _classify(glyph, matrix, label_array)
            if sample.get("expected_abstain") and character not in RESTRICTED_VOCABULARY:
                unknown[predicted].append((distance, margin))
            elif not sample.get("expected_abstain") and character == predicted:
                known_distance[character].append(distance); known_margin[character].append(margin)

    same_label = {char: [] for char in RESTRICTED_VOCABULARY}
    for index, (feature, label) in enumerate(zip(matrix, label_array, strict=True)):
        candidates = np.where(label_array == label)[0]; candidates = candidates[candidates != index]
        if len(candidates):
            same_label[str(label)].append(float(np.linalg.norm(matrix[candidates] - feature, axis=1).min()))

    distance_thresholds, margin_thresholds = {}, {}
    for character in RESTRICTED_VOCABULARY:
        known_max = max(known_distance[character]) if known_distance[character] else (float(np.percentile(same_label[character], 99)) if same_label[character] else 0.25)
        distance_threshold = max(0.12, known_max * 1.10 + 0.03)
        if unknown[character]:
            unknown_min = min(distance for distance, _ in unknown[character])
            if unknown_min > known_max:
                distance_threshold = min(distance_threshold, (known_max + unknown_min) / 2)
        distance_thresholds[character] = float(distance_threshold)
        margin_threshold = max(0.03, min(known_margin[character]) * 0.70) if known_margin[character] else 0.08
        if unknown[character] and known_margin[character]:
            unknown_max_margin = max(margin for _, margin in unknown[character]); known_min_margin = min(known_margin[character])
            if known_min_margin > unknown_max_margin:
                margin_threshold = max(margin_threshold, (known_min_margin + unknown_max_margin) / 2)
        margin_thresholds[character] = float(margin_threshold)

    class_labels = np.asarray(sorted(RESTRICTED_VOCABULARY), dtype="<U1")
    _write_deterministic_model(
        output_model,
        {
            "features": matrix,
            "labels": label_array,
            "class_labels": class_labels,
            "distance_thresholds": np.asarray([distance_thresholds[label] for label in class_labels], dtype=np.float32),
            "margin_thresholds": np.asarray([margin_thresholds[label] for label in class_labels], dtype=np.float32),
        },
    )
    digest = hashlib.sha256(output_model.read_bytes()).hexdigest()

    engine = RestrictedExperimentalEngine(output_model); known_total = known_correct = unknown_total = unknown_safe = 0; details = []
    for sample in validation_manifest["samples"]:
        result = engine.recognize(render_sample(sample)); expected_abstain = bool(sample.get("expected_abstain"))
        if expected_abstain:
            unknown_total += 1; unknown_safe += int(result.abstained)
        else:
            known_total += 1; known_correct += int(not result.abstained and result.text == sample["text"])
        details.append({"id": sample["id"], "kind": sample["kind"], "expected": sample["text"], "expected_abstain": expected_abstain, "predicted": result.text, "confidence": round(float(result.confidence), 4), "abstained": result.abstained})

    if experiment_dir is not None:
        experiment_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "run_id": "m2b-hog-nn-v1", "status": "frozen-before-heldout-evaluation", "engine_name": "experimental-restricted-v1", "scope": "restricted-token", "not_general_purpose_ocr": True, "restricted_vocabulary": RESTRICTED_VOCABULARY,
            "feature_extractor": {"glyph_canvas": [32, 32], "hog": {"win": [32, 32], "block": [16, 16], "stride": [8, 8], "cell": [8, 8], "bins": 9}, "pixel_thumbnail": [16, 16], "pixel_weight": 0.75, "geometry_weight": 1.5},
            "classifier": "1-nearest-neighbor over synthetic glyph features", "segmentation": "single-line vertical ink projection; max 32 glyphs", "threshold_calibration": "train nearest-neighbor distances + validation known/unknown glyphs", "min_token_confidence": MIN_TOKEN_CONFIDENCE,
            "model_file": "artifacts/models/restricted_hog_nn_v1.npz (generated, gitignored)", "model_sha256": digest, "model_committed": False, "runtime_dependencies_added": [], "training_splits": ["train", "validation"], "heldout_test_used_for_selection": False,
        }
        metrics = {"run_id": "m2b-hog-nn-v1", "selection_phase": "validation-only", "train_samples": len(train_manifest["samples"]), "validation_samples": len(validation_manifest["samples"]), "training_glyphs": len(label_array), "validation_known_exact_accuracy": known_correct / known_total, "validation_unknown_abstention_rate": unknown_safe / unknown_total, "validation_details": details, "heldout": None}
        _write_json(experiment_dir / "config.json", config); _write_json(experiment_dir / "metrics.json", metrics); (experiment_dir / "model_hash.txt").write_text(digest + "\n", encoding="utf-8"); (experiment_dir / "FROZEN_BEFORE_TEST").write_text("Model/config/thresholds frozen before final held-out manifest generation.\n", encoding="utf-8")
    return digest


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--train-manifest", type=Path, default=Path("data/recognizer/train/manifest.json")); parser.add_argument("--validation-manifest", type=Path, default=Path("data/recognizer/validation/manifest.json")); parser.add_argument("--output-model", type=Path, default=Path("artifacts/models/restricted_hog_nn_v1.npz")); parser.add_argument("--experiment-dir", type=Path, default=Path("artifacts/generated/m2b-current")); parser.add_argument("--expected-hash"); args = parser.parse_args()
    digest = train(args.train_manifest, args.validation_manifest, args.output_model, args.experiment_dir)
    if args.expected_hash and digest != args.expected_hash:
        raise SystemExit(f"Model hash mismatch: {digest} != {args.expected_hash}")
    print(digest)


if __name__ == "__main__":
    main()
