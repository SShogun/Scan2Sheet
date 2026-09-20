# OCR Metrics and Benchmark Design — Milestone 1A

## Scope

This note defines how Part 1A Section 2 should measure the **current** OCR system before preprocessing improvements.

The benchmark is not allowed to silently repair OCR output, discard hard fixtures, or alter ground truth to improve scores.

## 1. Ground truth rule

Every fixture needs manually verified ground truth.

For each document, store at minimum:

- canonical expected text;
- important expected fields;
- fixture category;
- source/provenance note confirming the sample is permitted for the public repository.

Ground truth should be reviewed before baseline execution. Once baseline numbers are captured, changing ground truth requires an explicit correction note because otherwise historical comparisons become invalid.

No confidential production samples or client-specific documents belong in the public fixture corpus.

## 2. Text normalization policy

CER/WER can change dramatically depending on normalization. Freeze the normalization before computing baseline metrics.

Recommended benchmark normalization:

1. Unicode-normalize consistently;
2. normalize line endings;
3. trim leading/trailing whitespace;
4. collapse repeated whitespace for WER;
5. preserve letters, digits, punctuation, and case unless the benchmark explicitly defines a second case-insensitive diagnostic metric.

Do **not** silently remove punctuation or change `0/O`, `1/I`, decimal separators, GSTIN characters, invoice identifiers, or monetary formatting. Those are exactly the OCR errors the benchmark needs to expose.

Keep both:

- raw OCR text;
- normalized text used for each metric.

## 3. Character Error Rate (CER)

CER is based on minimum edit distance at character level.

Let:

- S = substitutions;
- D = deletions;
- I = insertions;
- N = number of characters in the reference.

Then:

~~~~text
CER = (S + D + I) / N
~~~~

Lower is better; 0 is exact.

Why CER matters here:

- invoices contain identifiers and amounts where one wrong character is important;
- it captures punctuation/digit confusions that a word metric can hide;
- rotated, blurred, and noisy samples should show measurable degradation.

Edge case: when reference text is empty, define behavior explicitly instead of dividing by zero. The Part 1A corpus should normally use non-empty references.

## 4. Word Error Rate (WER)

WER applies the same edit-distance idea to word tokens.

~~~~text
WER = (S + D + I) / N_reference_words
~~~~

Lower is better.

WER is useful for overall readable text quality, but it is insufficient alone for accounting documents. A single wrong amount can be business-critical even if WER is low.

## 5. Exact-field accuracy / important-field hits

Field evaluation must complement text metrics.

For each fixture, define a fixed set of important fields relevant to that fixture.

Invoice examples from the public MVP contract:

- GSTIN;
- invoice number;
- date;
- taxable amount;
- CGST;
- SGST;
- IGST;
- total.

A field hit is counted only when the extracted value matches the manually verified expected value after a **field-specific, predeclared normalization**.

Examples of acceptable deterministic normalization:

- trim surrounding whitespace;
- normalize a date representation only if the benchmark explicitly declares equivalent formats;
- normalize numeric grouping separators only if the expected semantic value is defined and the parser is already intended to do so.

Do not use fuzzy matching for “exact-field accuracy.”

For a fixture:

~~~~text
field_accuracy = exact_hits / expected_important_fields
~~~~

Also record the per-field booleans so a score cannot hide which field failed.

For ledgers, use expected row/field keys defined by the fixture rather than inventing a global row match. The baseline harness should initially keep ledger matching conservative and auditable.

## 6. Processing time

Record wall-clock processing time per fixture in milliseconds.

Rules:

- use a monotonic high-resolution clock;
- record OCR + current preprocessing time consistently;
- do not compare first-run model/process startup timings with warmed runs without labeling them;
- timing is diagnostic, not the primary quality gate.

Tesseract performance can vary by machine. Benchmark JSON should record enough environment metadata to interpret timing later.

## 7. Quality measurements in baseline.json

Even before Part 1B uses quality adaptively, Section 2 should record deterministic measurements for each fixture where practical.

Planned fields:

~~~~json
{
  "fixture": "rotated/sample_01.png",
  "category": "rotated",
  "ocr_text": "...",
  "normalized_ocr_text": "...",
  "cer": 0.0,
  "wer": 0.0,
  "important_field_hits": {
    "invoice_number": true,
    "date": false,
    "total": true
  },
  "processing_ms": 0.0,
  "quality_measurements": {
    "laplacian_variance": 0.0,
    "mean_intensity": 0.0,
    "intensity_stddev": 0.0,
    "p05": 0.0,
    "p95": 0.0,
    "dynamic_range": 0.0
  }
}
~~~~

The exact schema should be versioned, e.g. `"benchmark_schema": 1`, so later additions do not silently reinterpret old results.

## 8. Baseline benchmark artifact

Required path from the execution plan:

`artifacts/benchmarks/baseline.json`

Recommended top-level structure:

~~~~json
{
  "benchmark_schema": 1,
  "git_commit": "<sha>",
  "tesseract_version": "<version>",
  "python_version": "<version>",
  "opencv_version": "<version>",
  "normalization": "<documented policy id>",
  "fixtures": []
}
~~~~

The `git_commit` should identify the implementation that generated the baseline.

Do not overwrite baseline results after preprocessing work begins. Later benchmark output should be a separate artifact or an explicitly versioned comparison.

## 9. RED test design

The plan requires realistic failures before implementation.

The seven initial RED tests should be driven by fixtures rather than synthetic assertions detached from OCR behavior:

- RED-01 Rotation;
- RED-02 Skew;
- RED-03 Contrast;
- RED-04 Noise;
- RED-05 Severe Blur;
- RED-06 Clean Non-Regression;
- RED-07 Determinism.

Important nuance: RED-06 is a future-safety contract. Before Part 1B exists, it can encode the clean baseline/tolerance that future preprocessing must preserve rather than forcing a meaningless failure merely to be “red.”

RED-07 should compare deterministic profile/decision output once the harness contract exists. If the current system has no profile yet, the test should fail for the missing behavior rather than be marked green through a placeholder.

No `xfail` should be used simply to hide mandatory RED failures. The evidence report should show the expected failures explicitly.

## 10. pytest fixtures and parametrization

The repository currently has no backend test suite or pytest dependency declared.

Section 2 should add a minimal test setup deliberately.

Use pytest fixtures for shared resources such as:

- corpus root;
- fixture manifest;
- verified ground truth;
- Tesseract availability/version;
- benchmark output temporary path.

Use `@pytest.mark.parametrize` to run the same regression contract across fixture cases/categories. Explicit test IDs should include the fixture category/name so failures are readable.

Keep expensive OCR execution scoped carefully. Do not make test order matter.

If Tesseract is genuinely unavailable in an environment, the test harness may report a clear environment prerequisite; it must not generate fake OCR results.

## 11. Dependency choice for metrics

JiWER is a well-known implementation of WER/CER using minimum edit distance, but it is **not currently a project dependency**.

For this MVP, Section 2 should first consider a small, tested local Levenshtein implementation for CER/WER because:

- the formulas are simple;
- it avoids adding a dependency solely for two metrics;
- the project has an explicit provenance/dependency audit requirement.

If JiWER is added instead, document the reason, version range, licence/provenance, and dependency change in the evidence/audit trail.

## 12. Benchmark integrity checks

The Verifier/angel oversight pass for Part 1A should reject the baseline if any of these occur:

- fixture ground truth is unreviewed;
- categories are missing;
- benchmark omits raw OCR text;
- metrics use undocumented normalization;
- failed fixtures are dropped;
- baseline is generated after preprocessing implementation;
- benchmark is not tied to a commit;
- results are non-reproducible from the same input/environment;
- confidential or restricted material enters the public corpus.

## Sources

- JiWER usage — WER/CER and minimum-edit-distance evaluation: https://github.com/jitsi/jiwer/blob/master/docs/usage.md
- JiWER project documentation: https://github.com/jitsi/jiwer
- pytest API — fixtures and parametrization: https://docs.pytest.org/en/latest/reference/reference.html
- pytest parametrization guide: https://docs.pytest.org/en/latest/how-to/parametrize.html
