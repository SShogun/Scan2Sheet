from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.ocr_benchmark import run_benchmark

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def fixture_manifest() -> dict[str, object]:
    return json.loads((ROOT / "tests" / "ocr_fixtures" / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def current_benchmark(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    output = tmp_path_factory.mktemp("ocr-benchmark") / "current.json"
    return run_benchmark(output)


@pytest.fixture(scope="session")
def metrics_by_category(current_benchmark: dict[str, object]) -> dict[str, dict[str, object]]:
    return {item["category"]: item for item in current_benchmark["fixtures"]}
