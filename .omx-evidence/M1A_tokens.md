# M1A Token / Execution Evidence

Part: Milestone 1 — Part 1A Baseline & Failure Corpus  
Branch: `milestone-1a-baseline`  
Started: 2026-09-19 (Asia/Kolkata)

## Start snapshot

| Metric | Value |
|---|---|
| root tokens | unavailable — execution surface exposes no trustworthy counter |
| subagent tokens | unavailable — no trustworthy subagent token telemetry exposed |
| cached input | unavailable |
| output tokens | unavailable |
| number of agents | 3 bounded logical roles: Explorer, Researcher/Test Engineer, Angel/Conductor-Verifier |
| number of turns | unavailable as a reliable execution metric |
| wall-clock duration | unavailable across connector + sandbox boundaries; not estimated |
| files changed | 0 at part start |
| tests added | 0 at part start |
| tests passed | not run at part start |

## End snapshot

| Metric | Value |
|---|---|
| root tokens | unavailable — not fabricated |
| subagent tokens | unavailable — not fabricated |
| cached input | unavailable — not fabricated |
| output tokens | unavailable — not fabricated |
| number of agents | 3 bounded logical roles used |
| number of turns | unavailable — not fabricated |
| wall-clock duration | unavailable — not fabricated |
| files changed | research docs, benchmark/test harness, fixture generator/manifest/categories, baseline artifact, result/evidence docs |
| tests added | 10 total: 7 named OCR contracts + 3 metric/harness unit tests |
| tests passed | pre-implementation run: 4 passed; 6 mandatory RED failures observed as intended |

## Reproducibility evidence

- Generated binaries are intentionally gitignored; `tests/generate_ocr_fixtures.py` recreates all seven public synthetic fixtures from the committed corpus definition.
- Deleting generated fixture binaries and rerunning `python tests/ocr_benchmark.py` recreated the corpus and reproduced OCR/metric/quality results; `processing_ms` is machine/run dependent.
- RED failures are preserved as evidence rather than hidden with `xfail`.

## Telemetry rule

Unavailable token/cache/turn metrics remain `unavailable`; values are never estimated solely to fill the experiment table.
