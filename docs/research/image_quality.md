# Image Quality Research — Milestone 1A

## Scope

This note supports Milestone 1, Part 1A, Section 1 only. It does not implement preprocessing.

The public Scan2Sheet MVP must stay local-first and generic. The quality layer may inspect document images, but it must not introduce client-specific schemas, production URLs, confidential datasets, cloud calls, or proprietary models.

## Repository baseline observed on 19 September 2026

The current image path in `backend/app/ocr.py` is:

1. decode with Pillow;
2. flatten transparency onto white;
3. convert to RGB;
4. convert to grayscale;
5. resize toward a 2500–4000 px maximum dimension;
6. run Tesseract with `--oem 1 --psm 3`.

Important: the current implementation does **not** yet perform OpenCV denoising, thresholding, deskewing, orientation normalization, contrast enhancement, or blur analysis, even though parts of the README describe a richer preprocessing flow. Section 2 must benchmark the code that actually exists.

## 1. OpenCV image representations

OpenCV-Python represents an image as a NumPy array.

Relevant properties:

- grayscale image: two dimensions, `height x width`;
- BGR image: three dimensions, `height x width x channels`;
- common decoded 8-bit images use intensity values 0–255;
- OpenCV color images are BGR by default, not RGB;
- operations used for quality metrics should use explicit grayscale conversion so channel order cannot affect the result.

For this project, quality measurements should be calculated on a deterministic grayscale image derived from the decoded input. The original image must remain available so later transforms can be applied without cumulative encode/decode loss.

Recommended invariant for the future quality module:

~~~~text
decoded input
    -> canonical grayscale for measurements
    -> immutable quality measurements
    -> preprocessing decisions
~~~~

Do not measure quality after an enhancement and then report the values as if they describe the original input.

## 2. Histogram and contrast analysis

A grayscale histogram counts how many pixels occur at each intensity. It is useful for understanding whether a document occupies a narrow intensity range, has clipped shadows/highlights, or contains broad foreground/background separation.

Candidate measurements for the future quality profile:

- mean intensity;
- standard deviation of intensity;
- low/high percentiles, e.g. p05 and p95;
- robust dynamic range: `p95 - p05`;
- optional histogram entropy.

The robust percentile range is preferred over raw min/max because one isolated black or white pixel can make min/max look healthy while the document remains low contrast.

A single contrast threshold must **not** be declared from theory alone. The threshold needs calibration from the Part 1A corpus: clean vs low-contrast fixtures should show whether the chosen statistic separates useful from degraded inputs.

### Global equalization vs CLAHE

Global histogram equalization redistributes intensities over the whole image. It can improve global contrast but can also over-amplify regions that were already adequate.

CLAHE divides the image into tiles, equalizes locally, and clips excessive histogram amplification. It is a better candidate when illumination varies across a phone photo, but it can still amplify local noise.

For Scan2Sheet, contrast enhancement should later be conditional rather than unconditional.

## 3. Laplacian-based sharpness / blur measurement

The Laplacian is a second-derivative operator that reacts strongly to intensity transitions such as text edges.

A common blur heuristic is:

~~~~text
gray -> Laplacian response -> variance(response)
~~~~

Interpretation:

- higher variance usually means more high-frequency edge structure;
- lower variance often correlates with blur.

This is a **heuristic**, not a universal blur probability. Text size, resolution, compression, halftone backgrounds, borders, and document layout all affect the score.

Therefore:

1. compute the metric deterministically;
2. store the raw numeric value in the benchmark;
3. calibrate any future `blurred` threshold from clean/blurred fixtures;
4. never convert a low Laplacian score directly into fabricated OCR confidence.

RED-05 later needs to prove the current system can appear confident on severely blurred input; Part 1B can then add a separate quality warning.

## 4. Orientation vs skew

These are different problems and should remain separate.

### Orientation

Orientation is a coarse 90-degree state: 0°, 90°, 180°, or 270°. A page photographed sideways needs orientation normalization before small-angle deskew.

Possible local signals include OCR orientation/script detection or image-layout evidence. Any method chosen in Part 1B must be deterministic and must have a safe no-op path when evidence is weak.

### Skew

Skew is a smaller rotation around the correct coarse orientation, e.g. approximately ±3–10° for the planned RED corpus.

Two classical local candidates are:

- Hough-line based estimation: detect text/border lines and aggregate their angles;
- foreground-point estimation: threshold foreground pixels and use a rotated minimum-area rectangle or a fitted line.

Trade-offs:

- Hough methods can be robust when long baselines/table rules exist, but borders can dominate;
- foreground geometry is simpler but can be biased by logos, sparse text, or page margins.

The future implementation should normalize angle conventions explicitly and use a bounded correction range. If the estimated skew is implausible, abstain instead of rotating aggressively.

## 5. Proposed quality profile contract for later architecture

This is a research target, not an implementation in Part 1A Section 1.

~~~~text
QualityProfile
- width
- height
- mean_intensity
- intensity_stddev
- p05
- p95
- dynamic_range
- laplacian_variance
- estimated_skew_degrees
- orientation_degrees
- warnings
~~~~

Rules:

- values describe the original decoded input or a documented canonical grayscale derivative;
- units and angle sign conventions must be fixed in tests;
- no random sampling;
- no network calls;
- no OCR-domain fields such as GSTIN, invoice total, debit, or credit inside the quality analyzer;
- quality warnings are separate from Tesseract confidence.

## 6. Determinism requirements

RED-07 requires identical input to produce the same preprocessing profile later.

To preserve determinism:

- use fixed algorithm parameters;
- avoid random sampling, or fix and expose a seed if randomness becomes unavoidable;
- avoid time-dependent metadata in profiles;
- do not let thread scheduling change aggregation order;
- preserve exact transform order;
- serialize floating-point metrics with a documented precision when writing benchmark JSON.

## 7. Questions that Section 2 must answer with evidence

The corpus and baseline benchmark must determine:

- how Laplacian variance differs between clean and severely blurred samples;
- how dynamic range differs between clean and low-contrast samples;
- whether OCR error increases predictably for ±3–10° skew;
- whether 90° rotation causes a reproducible failure on the present Tesseract path;
- whether current OCR confidence is correlated with actual CER/WER;
- whether clean fixtures are stable enough to become non-regression controls.

No quality threshold should be frozen before these measurements exist.

## Sources

- OpenCV — Basic Operations on Images: https://docs.opencv.org/4.x/d3/df2/tutorial_py_basic_ops.html
- OpenCV — Operations with images: https://docs.opencv.org/4.x/d5/d98/tutorial_mat_operations.html
- OpenCV — Histogram Equalization / CLAHE: https://docs.opencv.org/4.x/d5/daf/tutorial_py_histogram_equalization.html
- OpenCV — Laplace Operator: https://docs.opencv.org/4.x/d5/db5/tutorial_laplace_operator.html
- OpenCV — Hough Line Transform: https://docs.opencv.org/4.x/d9/db0/tutorial_hough_lines.html
- OpenCV — Structural Analysis / minAreaRect: https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html
