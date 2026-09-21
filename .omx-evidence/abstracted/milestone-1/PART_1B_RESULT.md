# Milestone 1 — Part 1B Result

## Scope executed

Part 1B — Adaptive Preprocessing V1, Sections 1 and 2.

Implementation branch: `milestone-1b-preprocessing`  
Reviewed implementation commit: `a2de2905671132bd3b4173f3cabe477ff5863a1b`

## Intended plan vs current status

| Planned requirement | Status | Evidence |
|---|---|---|
| Create `backend/app/imaging/` | complete | package with `quality.py`, `orientation.py`, `deskew.py`, `enhance.py`, `pipeline.py` |
| `PreprocessResult` contract | complete | original size, processed image, quality profile, transforms applied |
| Orientation normalization | complete | bounded local Tesseract OSD supports 0/90/180/270 with hard timeout |
| Deskewing | complete | bounded Hough-line estimate and non-cropping rotate-bound |
| Denoising | complete | conditional median-3; small images denoise before upscaling, large inputs downscale first |
| Contrast enhancement | complete | conditional CLAHE |
| Adaptive thresholding | complete | conditional Gaussian adaptive threshold after CLAHE |
| Blur scoring | complete | Laplacian variance warning; no sharpening |
| Resource-bounded analysis | complete | quality/Hough/OSD analysis capped at 1600 px max dimension |
| Historical baseline immutability | complete | default benchmark output is `current.json`, never `baseline.json` |
| Clean non-regression | complete | clean CER/WER remain 0; 7/7 important fields |
| Determinism | complete | repeated profiles/transforms/pixels identical |
| Full benchmark rerun | complete | `artifacts/benchmarks/m1b_after.json` |
| Frontend unchanged | complete | no UI source modifications in M1B |
| CI quality gate | complete | `.github/workflows/ci.yml` runs compile, pytest, OCR benchmark, frontend build |

## RED → GREEN result

| Category | Baseline CER | M1B CER | Baseline field accuracy | M1B field accuracy |
|---|---:|---:|---:|---:|
| clean | 0.000000 | 0.000000 | 1.000000 | 1.000000 |
| rotated | 0.923077 | 0.000000 | 0.000000 | 1.000000 |
| skewed | 1.000000 | 0.000000 | 0.000000 | 1.000000 |
| low_contrast | 1.000000 | 0.000000 | 0.000000 | 1.000000 |
| noisy | 1.000000 | 0.006410 | 0.000000 | 0.857143 |
| blurred | 0.019231 | 0.006410 | 0.857143 | 1.000000 |
| phone_photo | 1.000000 | 1.000000 | 0.000000 | 0.000000 |

Selected degraded categories improve materially and the clean control does not regress.

## Verification

- `pytest -q`: **21 passed** after Sourcery review fixes.
- `python -m compileall -q backend tests`: passed.
- Fixture SHA-256 verification: **7/7**.
- Credential-pattern scan over Milestone 1 backend/tests: no hits.
- 180° orientation regression test: passed.
- Large-image bounded-analysis regression test: passed.
- Historical baseline overwrite regression test: passed.
- Reviewer pass previously found a false-positive noise-classification risk on white pages; implementation was changed to measure local median deviation and covered by a regression test.

## Sourcery review

Sourcery reported four blocking findings and all were addressed:

1. benchmark default could overwrite historical `baseline.json` → default moved to `current.json`;
2. 180° orientation was missed → OSD now checks all quadrant orientations;
3. OSD could run without a timeout → hard 5-second timeout with safe no-op fallback;
4. quality/Hough work was unbounded on huge images → bounded analysis representation added and pixel-wise transforms are size-bounded.

## Missing things / bugs / known limitations

1. Perspective correction is intentionally outside V1. The perspective-distorted `phone_photo` fixture therefore remains a known failure.
2. The pre-existing OCR confidence value remains text-length based. M1B adds independent image-quality warnings but deliberately does not change the public OCR confidence contract in this milestone.
3. Quality thresholds are calibrated to the current public regression corpus and are intentionally conservative; more diverse public samples should be added before claiming broad scanner/camera coverage.
4. Main branch ruleset activation remains a repository-administration blocker because the active GitHub connection has no administration-write operation.

## Exit verdict

**PASS — Part 1B exit gate satisfied after external Sourcery review fixes.**

All mandatory RED contracts are GREEN, clean documents do not regress, degraded categories improve materially, blur is flagged, analysis is resource-bounded, output is deterministic, and the historical baseline cannot be overwritten by the default benchmark command.
