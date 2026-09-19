# Preprocessing Trade-offs — Milestone 1A

## Scope

This document freezes the research boundaries for the future Adaptive Preprocessing V1. No preprocessing implementation belongs in Milestone 1A Section 1.

Allowed future transforms from the execution plan:

- orientation normalization;
- deskewing;
- denoising;
- contrast enhancement;
- adaptive thresholding;
- blur scoring.

Explicitly excluded:

- neural enhancement;
- super-resolution;
- complex document segmentation;
- handwriting recognition;
- cloud OCR or network-dependent preprocessing.

## Current baseline

The current `backend/app/ocr.py` preprocessing only flattens transparency, converts to grayscale, and resizes. This is the baseline that Part 1A Section 2 must capture before any adaptive OpenCV preprocessing is introduced.

That matters because comparing a future pipeline against the README description instead of the executable code would corrupt the benchmark.

## 1. Otsu vs adaptive thresholding

### Otsu thresholding

Otsu chooses one global threshold from the image histogram to minimize within-class variance.

Best fit:

- document has reasonably uniform illumination;
- foreground/background histogram separation is meaningful;
- one threshold can serve the whole page.

Risks:

- shadows, gradients, or uneven phone lighting violate the global-threshold assumption;
- faint text can disappear if the global threshold is dominated by brighter regions.

### Adaptive thresholding

Adaptive thresholding computes a threshold from a local neighborhood for each region/pixel. OpenCV provides mean- and Gaussian-neighborhood variants.

Best fit:

- uneven lighting;
- shadows across a phone photo;
- local background variation.

Risks:

- block size and constant `C` are sensitive parameters;
- small neighborhoods can amplify texture/noise;
- aggressive settings can break thin characters into fragments;
- it is more expensive than one global threshold.

### Planned decision rule

Do not apply either thresholding mode blindly to every document.

Part 1B should evaluate a bounded policy such as:

~~~~text
quality profile
   -> if contrast/illumination is adequate: preserve grayscale
   -> if globally low contrast but uniform: evaluate Otsu
   -> if illumination varies materially: evaluate adaptive threshold
~~~~

The exact conditions must come from benchmark evidence, not hard-coded assumptions in this research section.

## 2. Denoising

Potential classical operations include Gaussian filtering, median filtering, and morphology after binarization.

### Gaussian blur

Useful for suppressing Gaussian-like high-frequency noise. It also softens text edges, so overuse can reduce OCR character separation.

### Median filtering

Useful for salt-and-pepper noise while preserving edges better than a strong linear blur in many cases. Large kernels can still destroy punctuation and narrow glyphs.

### Morphological opening/closing

OpenCV morphology operates using a structuring element.

- opening = erosion then dilation; can remove small foreground noise;
- closing = dilation then erosion; can close small holes/gaps.

Risks for OCR:

- erosion can remove punctuation and thin strokes;
- dilation can merge adjacent characters;
- a kernel suitable for a 300-DPI scan may be too large for a small phone image.

Therefore kernel sizes must remain small and be tied to actual fixture evidence.

## 3. Contrast enhancement

### Global histogram equalization

Pros:

- simple;
- deterministic;
- may increase separation on flat, globally low-contrast scans.

Cons:

- can over-enhance already good areas;
- may amplify background artifacts;
- can make clean documents worse.

### CLAHE

Pros:

- local enhancement helps nonuniform lighting;
- clip limiting reduces runaway amplification compared with unrestricted local equalization.

Cons:

- can amplify local scanner noise;
- tile size and clip limit create parameter sensitivity;
- can change clean inputs unnecessarily.

Acceptance requirement from the plan is stronger than “looks better”: selected degraded categories must improve measurably while clean documents show no meaningful regression.

## 4. Orientation normalization

A coarse orientation correction should be separated from deskewing.

Desired behavior:

- recognize only well-supported 0/90/180/270 decisions;
- rotate once;
- preserve page content without cropping;
- abstain when evidence is weak.

Failure mode to avoid: interpreting an uncertain orientation as certain and rotating a clean upright document incorrectly.

This will be tested by RED-01 and later clean non-regression tests.

## 5. Deskewing

Deskew should correct small rotations, not serve as a general perspective-correction system.

Candidate sequence:

~~~~text
canonical grayscale
 -> foreground/edge representation
 -> estimate dominant text/page angle
 -> normalize angle convention
 -> reject implausible estimate
 -> rotate with explicit border fill
~~~~

Important implementation concerns for Part 1B:

- distinguish +/− angle conventions from OpenCV APIs;
- keep a maximum correction range appropriate to the ±3–10° corpus;
- ensure rotation expands/pads or otherwise avoids clipping;
- fill new background pixels consistently, normally white;
- use deterministic interpolation;
- record the applied angle in `transforms_applied`.

Perspective correction is outside the stated V1 scope.

## 6. Transform order

Transform order can change the result, so it must be explicit and tested.

Research recommendation for a first bounded pipeline:

~~~~text
decode
 -> flatten transparency
 -> coarse orientation normalization
 -> canonical grayscale
 -> quality measurements
 -> small-angle deskew
 -> conditional denoise
 -> conditional contrast enhancement
 -> conditional threshold
 -> OCR
~~~~

Why measure quality before enhancement:

- the profile should describe the input defect, not an already altered image;
- later benchmark comparisons need stable, interpretable measurements.

Why deskew before threshold can be preferable in some cases:

- interpolation after binary thresholding can introduce jagged artifacts;
- grayscale rotation followed by thresholding can produce cleaner edges.

This is a hypothesis to validate on the RED corpus, not a guaranteed rule.

## 7. Clean-document safety

RED-06 exists because preprocessing can make already-good OCR worse.

Part 1B should have a clean-path policy:

- if input quality is already adequate, apply as little as possible;
- every transform must justify itself via the quality profile;
- benchmark clean CER, WER, and exact-field accuracy before and after;
- a visually “sharper” image is not a pass unless OCR metrics remain acceptable.

## 8. Severe blur behavior

Severe blur should trigger a quality warning rather than a false claim of OCR certainty.

The current `_ocr_image` computes its OCR confidence from text length:

~~~~text
min(100, len(raw_text) * 2.5)
~~~~

That is not recognition confidence. A long but incorrect OCR string can score highly.

Part 1A Section 2 should expose this weakness with RED-05. Part 1B may add an independent blur warning, but changing OCR confidence semantics should be treated carefully because API compatibility matters in later milestones.

## 9. What the benchmark must decide

Before Part 1B implementation, collect evidence for:

- clean non-regression tolerance;
- category-specific CER/WER changes;
- exact-field hit changes;
- processing-time cost;
- blur-score distributions;
- contrast-statistic distributions;
- skew-estimation error;
- transform determinism.

If no candidate transform improves a category without unacceptable clean regressions, the correct result is to abstain or keep that transform out of V1.

## Sources

- OpenCV — Image Thresholding (simple, adaptive, Otsu): https://docs.opencv.org/4.x/d7/d4d/tutorial_py_thresholding.html
- OpenCV — Morphological Transformations: https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html
- OpenCV — Histogram Equalization / CLAHE: https://docs.opencv.org/4.x/d5/daf/tutorial_py_histogram_equalization.html
- OpenCV — Laplace Operator: https://docs.opencv.org/4.x/d5/db5/tutorial_laplace_operator.html
- OpenCV — Hough Line Transform: https://docs.opencv.org/4.x/d9/db0/tutorial_hough_lines.html
- OpenCV — Structural Analysis / minAreaRect: https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html
