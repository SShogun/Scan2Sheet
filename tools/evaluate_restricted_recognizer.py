from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytesseract

from backend.app.ocr.experimental import RestrictedExperimentalEngine
from tools.recognizer_dataset import load_manifest, render_sample, verify_manifest

TESSERACT_CONFIG = "--oem 1 --psm 3"


def evaluate(model_path: Path, train_manifest_path: Path, test_manifest_path: Path, output_path: Path) -> dict[str, object]:
    verify_manifest(train_manifest_path); verify_manifest(test_manifest_path)
    train_manifest, test_manifest = load_manifest(train_manifest_path), load_manifest(test_manifest_path)
    train_hashes = {str(sample["sha256"]) for sample in train_manifest["samples"]}; test_hashes = {str(sample["sha256"]) for sample in test_manifest["samples"]}
    if train_hashes & test_hashes:
        raise RuntimeError("Train/test leakage detected.")

    actual_model_sha256 = hashlib.sha256(model_path.read_bytes()).hexdigest()
    expected_model_sha256 = str(test_manifest["frozen_model_sha256"])
    if actual_model_sha256 != expected_model_sha256:
        raise RuntimeError(
            f"Model hash mismatch: {actual_model_sha256} != {expected_model_sha256}"
        )

    engine = RestrictedExperimentalEngine(model_path)
    known = correct = known_abstained = unknown = unknown_safe = tess_correct = 0; details = []
    for sample in test_manifest["samples"]:
        image = render_sample(sample); result = engine.recognize(image)
        try:
            tess_text = pytesseract.image_to_string(image, config=TESSERACT_CONFIG, timeout=15).strip()
        except Exception as exc:
            tess_text = f"<ERROR:{type(exc).__name__}>"
        expected_abstain = bool(sample.get("expected_abstain"))
        if expected_abstain:
            unknown += 1; unknown_safe += int(result.abstained); tess_exact = None
        else:
            known += 1; correct += int(not result.abstained and result.text == sample["text"]); known_abstained += int(result.abstained); tess_exact = tess_text == sample["text"]; tess_correct += int(tess_exact)
        details.append({"id": sample["id"], "kind": sample["kind"], "expected": sample["text"], "expected_abstain": expected_abstain, "experimental": {"text": result.text, "confidence": round(float(result.confidence), 4), "abstained": result.abstained, "reason": result.metadata.get("reason", "")}, "tesseract": {"text": tess_text, "exact_match": tess_exact}})

    payload = {"model_sha256": actual_model_sha256, "known_samples": known, "experimental_known_exact_accuracy": correct / known, "experimental_known_abstention_rate": known_abstained / known, "unknown_samples": unknown, "experimental_unknown_abstention_rate": unknown_safe / unknown, "tesseract_known_exact_accuracy": tess_correct / known, "details": details}
    output_path.parent.mkdir(parents=True, exist_ok=True); output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"); return payload


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--model", type=Path, default=Path("artifacts/models/restricted_hog_nn_v1.npz")); parser.add_argument("--train-manifest", type=Path, default=Path("data/recognizer/train/manifest.json")); parser.add_argument("--test-manifest", type=Path, default=Path("data/recognizer/test/manifest.json")); parser.add_argument("--output", type=Path, default=Path("artifacts/benchmarks/current_m2b_recognizer.json")); args = parser.parse_args()
    result = evaluate(args.model, args.train_manifest, args.test_manifest, args.output)
    print(json.dumps({key: result[key] for key in ("experimental_known_exact_accuracy", "experimental_unknown_abstention_rate", "tesseract_known_exact_accuracy")}, indent=2))


if __name__ == "__main__":
    main()
