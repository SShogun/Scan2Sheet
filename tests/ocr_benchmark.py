from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import time
import unicodedata
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
from PIL import Image

from backend.app.ocr import _ocr_image, _preprocess_image
from tests.generate_ocr_fixtures import ensure_fixtures

FIXTURE_ROOT = ROOT / "tests" / "ocr_fixtures"
DEFAULT_OUTPUT = ROOT / "artifacts" / "benchmarks" / "baseline.json"
BASELINE_IMPLEMENTATION_COMMIT = "1c975402258e2b15144dfa1e909ffc2809e618e7"


def normalize_text(value: str, *, words: bool = False) -> str:
    value = unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n").strip()
    if words:
        return " ".join(value.split())
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.split("\n")]
    return "\n".join(line for line in lines if line)


def edit_distance(reference: list[str] | str, hypothesis: list[str] | str) -> int:
    previous = list(range(len(hypothesis) + 1))
    for i, ref_item in enumerate(reference, 1):
        current = [i]
        for j, hyp_item in enumerate(hypothesis, 1):
            substitution = previous[j - 1] + (ref_item != hyp_item)
            deletion = previous[j] + 1
            insertion = current[j - 1] + 1
            current.append(min(substitution, deletion, insertion))
        previous = current
    return previous[-1]


def error_rate(reference: list[str] | str, hypothesis: list[str] | str) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return edit_distance(reference, hypothesis) / len(reference)


def quality_measurements(image_path: Path) -> dict[str, float]:
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise RuntimeError(f"Unable to load fixture: {image_path}")
    p05, p95 = np.percentile(gray, [5, 95])
    return {
        "laplacian_variance": round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 6),
        "mean_intensity": round(float(np.mean(gray)), 6),
        "intensity_stddev": round(float(np.std(gray)), 6),
        "p05": round(float(p05), 6),
        "p95": round(float(p95), 6),
        "dynamic_range": round(float(p95 - p05), 6),
    }


def tesseract_version() -> str:
    result = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, check=True)
    return result.stdout.splitlines()[0].strip()


def run_benchmark(output_path: Path = DEFAULT_OUTPUT, *, kind: str = "pre-preprocessing-baseline", git_commit: str = BASELINE_IMPLEMENTATION_COMMIT) -> dict[str, object]:
    ensure_fixtures()
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    fixture_results: list[dict[str, object]] = []
    for item in manifest["fixtures"]:
        image_path = FIXTURE_ROOT / item["fixture"]
        original = Image.open(image_path)
        started = time.perf_counter()
        processed = _preprocess_image(original)
        ocr_text, ocr_confidence = _ocr_image(processed)
        elapsed_ms = (time.perf_counter() - started) * 1000

        ref_chars = normalize_text(item["ground_truth_text"])
        hyp_chars = normalize_text(ocr_text)
        ref_words = normalize_text(item["ground_truth_text"], words=True).split()
        hyp_words = normalize_text(ocr_text, words=True).split()
        normalized_for_hits = normalize_text(ocr_text, words=True)
        field_hits = {
            key: normalize_text(value, words=True) in normalized_for_hits
            for key, value in item["important_fields"].items()
        }
        fixture_results.append({
            "fixture": item["fixture"],
            "fixture_sha256": item["sha256"],
            "category": item["category"],
            "ocr_text": ocr_text,
            "normalized_ocr_text": hyp_chars,
            "cer": round(error_rate(ref_chars, hyp_chars), 6),
            "wer": round(error_rate(ref_words, hyp_words), 6),
            "important_field_hits": field_hits,
            "important_field_accuracy": round(sum(field_hits.values()) / len(field_hits), 6),
            "ocr_confidence_current": round(float(ocr_confidence), 6),
            "processing_ms": round(elapsed_ms, 3),
            "quality_measurements": quality_measurements(image_path),
        })

    payload = {
        "benchmark_schema": 1,
        "benchmark_kind": kind,
        "git_commit": git_commit,
        "ground_truth_review": manifest["review_status"],
        "normalization": "NFKC; normalized line endings; trim; collapse horizontal whitespace; WER collapses all whitespace; case and punctuation preserved",
        "important_field_hit_definition": "Expected public fixture field value occurs exactly in whitespace-normalized raw OCR text; no fuzzy matching.",
        "environment": {
            "python": platform.python_version(),
            "opencv": cv2.__version__,
            "tesseract": tesseract_version(),
        },
        "fixtures": fixture_results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--kind", default="pre-preprocessing-baseline")
    parser.add_argument("--git-commit", default=BASELINE_IMPLEMENTATION_COMMIT)
    args = parser.parse_args()
    result = run_benchmark(args.output, kind=args.kind, git_commit=args.git_commit)
    for fixture in result["fixtures"]:
        print(
            fixture["category"],
            f"CER={fixture['cer']:.6f}",
            f"WER={fixture['wer']:.6f}",
            f"fields={fixture['important_field_accuracy']:.6f}",
            f"confidence={fixture['ocr_confidence_current']:.1f}",
            f"ms={fixture['processing_ms']:.1f}",
        )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
