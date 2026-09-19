# Milestone 1 — Part 1A Result

## Scope executed

Part 1A — Baseline & Failure Corpus, Sections 1 and 2.

No adaptive preprocessing implementation was introduced in this part. The baseline was captured against the existing Pillow grayscale/resize + Tesseract path before the future `backend.app.imaging` package exists.

## Intended plan vs current status

| Planned requirement | Status | Evidence |
|---|---|---|
| Research topics | complete | `docs/research/` |
| Corpus categories | complete | deterministic generator + manifest for clean/rotated/skewed/low_contrast/noisy/blurred/phone_photo |
| Ground truth reviewed | complete | synthetic source visually checked against generated clean and phone-photo fixtures |
| Reproducible fixtures | complete | `tests/generate_ocr_fixtures.py`; binary images regenerate on demand |
| RED-01 Rotation | RED as required | rotated field accuracy 0.000 vs clean 1.000 |
| RED-02 Skew | RED as required | +9° skew field accuracy 0.000 vs clean 1.000 |
| RED-03 Contrast | RED as required | low-contrast field accuracy 0.000 vs clean 1.000 |
| RED-04 Noise | RED as required | noisy field accuracy 0.000 vs clean 1.000 |
| RED-05 Severe Blur | RED as required | blur-profile package absent; baseline blur also degrades CER while current text-length confidence remains 100 |
| RED-06 Clean Non-Regression | control GREEN | clean CER 0.000; field accuracy 1.000 |
| RED-07 Determinism | RED as required | preprocessing profile/package absent |
| Baseline JSON | complete | `artifacts/benchmarks/baseline.json` |
| Required benchmark evidence | complete | OCR text, CER, WER, field hits, processing_ms, quality measurements |
| Public/confidential boundary | complete | synthetic data only |

## Baseline snapshot

| Category | CER | WER | Important-field accuracy | Current OCR confidence |
|---|---:|---:|---:|---:|
| clean | 0.000000 | 0.000000 | 1.000000 | 100 |
| rotated | 0.923077 | 1.100000 | 0.000000 | 100 |
| skewed | 1.000000 | 1.000000 | 0.000000 | 0 |
| low_contrast | 1.000000 | 1.000000 | 0.000000 | 0 |
| noisy | 1.000000 | 1.000000 | 0.000000 | 0 |
| blurred | 0.019231 | 0.150000 | 0.857143 | 100 |
| phone_photo | 1.000000 | 1.000000 | 0.000000 | 0 |

## Verification evidence

- 3 metric-unit tests passed.
- Mandatory OCR contract suite on the pre-improvement system: 6 failed, 1 clean-control test passed.
- Total before implementation: **4 passed, 6 failed**.
- RED failures are not hidden with `xfail`.
- Removing generated image binaries and rerunning the benchmark recreates the corpus and reproduces OCR/CER/WER/field-hit results; timing varies by run.
- No network dependency is used by fixture generation or benchmark execution.

## Missing things / bugs found

1. No orientation normalization: 90° input is unreadable while the current text-length heuristic can still report confidence 100.
2. No small-angle deskew: +9° returns no usable OCR text.
3. No low-contrast recovery.
4. No bounded denoising.
5. OCR confidence is text-length based rather than recognition confidence; the blurred sample has worse CER while still reporting 100.
6. Phone-photo perspective distortion remains difficult; perspective correction is outside Adaptive Preprocessing V1.
7. No repository CI existed at this gate.

## Exit verdict

**PASS — Part 1A exit gate satisfied.**

The corpus definition exists, ground truth is reviewed, the pre-improvement baseline is captured, realistic RED failures are demonstrated, and results are reproducible.
