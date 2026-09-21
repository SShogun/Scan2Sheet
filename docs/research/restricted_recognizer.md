# Restricted Experimental Recognizer — Part 2B Research

## Scope

Part 2B does **not** attempt general-purpose OCR. The allowed vocabulary is:

```text
A-Z
0-9
.
,
/
-
:
```

The intended inputs are isolated, single-line crops for monetary values, dates,
invoice identifiers and GSTIN-like alphanumeric strings. Anything outside that
scope should abstain rather than guess.

## Options considered

### Tiny CRNN / CTC recognizer

A compact CNN/CRNN with CTC decoding matches the sequence-recognition concepts
studied in Part 2A and could generalize beyond fixed templates. It was rejected
for this milestone because it would add a new ML runtime, a larger dependency
and model-provenance surface, and more training complexity than the restricted
experiment needs.

### Tesseract with a character whitelist

Tesseract supports restricted character whitelists and single-line page
segmentation. This is useful as a comparison/baseline, but it is not an
independent secondary recognizer because Scan2Sheet's primary OCR is already
Tesseract.

### Classical HOG + nearest-neighbor character recognition

Selected. It uses the existing OpenCV/NumPy/Pillow stack and adds no runtime
package or downloaded model.

## Selected experiment

1. deterministic public DejaVu fonts generate synthetic token crops;
2. each token is segmented by vertical ink projection;
3. each glyph is normalized to a 32×32 canvas;
4. features combine OpenCV HOG, a 16×16 normalized pixel thumbnail and five
   geometry features;
5. recognition uses one-nearest-neighbor distance over training glyph features;
6. validation calibrates per-class distance and margin thresholds;
7. the token abstains if any glyph is unknown/uncertain or token confidence is
   below the frozen threshold.

This is a research recognizer, not a production OCR engine.

## Dataset boundary

All samples are synthetic and public-safe. No client records, private invoices
or production data are used. Train, validation and final test generated-image
SHA-256 values are disjoint. The final test manifest was generated/evaluated only
after the model configuration and thresholds were frozen. No post-test tuning
was performed.

## Model artifact strategy

The binary `.npz` model is generated and gitignored. The repository stores the
deterministic manifests, trainer/generator code, frozen config, expected model
SHA-256 and held-out benchmark. The experiment-sensitive NumPy/OpenCV/Pillow
versions are pinned in `backend/requirements-repro.txt` because the raw model
bytes depend on those numeric/image-library versions. A clean checkout using the
pinned development environment regenerates the model locally; there is no
network/model download.

## Held-out conclusion

- validation known exact: 10/10;
- validation unknown abstention: 8/8;
- held-out known exact: 5/15 (33.3%);
- held-out unknown abstention: 7/7 (100%);
- current Tesseract exact on the same supported held-out crops: 8/15 (53.3%).

This does **not** justify replacing Tesseract. The experimental engine remains
feature-flag-only, primary OCR remains authoritative, and candidate arbitration
is deferred to Milestone 3.
