# Milestone 1 — Part 1B Result

## Scope executed

Part 1B — Adaptive Preprocessing V1, Sections 1 and 2.

Implementation branch: `milestone-1b-preprocessing`  
Implementation benchmark commit: `de08cf11a2986d39a8a17fca264cb52636672cc4`

## Intended plan vs current status

| Planned requirement | Status | Evidence |
|---|---|---|
| Create `backend/app/imaging/` | complete | package with `quality.py`, `orientation.py`, `deskew.py`, `enhance.py`, `pipeline.py` |
| `PreprocessResult` contract | complete | original size, processed image, quality profile, transforms applied |
| Orientation normalization | complete | geometry hint + local Tesseract OSD; safe no-op on weak/failing evidence |
| Deskewing | complete | bounded ±12° Hough-line estimate and non-cropping rotate-bound |
| Denoising | complete | conditional median-3 only on detected impulse noise |
| Contrast enhancement | complete | conditional CLAHE |
| Adaptive thresholding | complete | conditional Gaussian adaptive threshold after CLAHE |
| Blur scoring | complete | Laplacian variance warning; no sharpening |
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

- `pytest -q`: **18 passed**.
- `python -m compileall -q backend tests`: passed.
- Fixture SHA-256 verification: **7/7**.
- Credential-pattern scan over Milestone 1 backend/tests: no hits.
- Repeated deterministic preprocessing checks: passed.
- Reviewer pass found a false-positive noise-classification risk on white pages; implementation was changed to measure local median deviation and a regression test was added.

## Missing things / bugs / known limitations

1. Perspective correction is intentionally outside V1. The perspective-distorted `phone_photo` fixture therefore remains a known failure.
2. The pre-existing OCR confidence value remains text-length based. M1B adds independent image-quality warnings but deliberately does not change the public OCR confidence contract in this milestone.
3. Quality thresholds are calibrated to the current public regression corpus and are intentionally conservative; more diverse public samples should be added before claiming broad scanner/camera coverage.
4. The main branch protection request is a repository-administration concern, not an image-pipeline defect. The connected GitHub app can read rulesets but does not expose/write repository administration, so protection cannot be applied from this integration.

## Exit verdict

**PASS — Part 1B exit gate satisfied.**

All mandatory RED contracts are GREEN, clean documents do not regress, degraded categories improve materially, blur is flagged, and output is deterministic.
