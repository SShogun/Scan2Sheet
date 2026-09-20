# OCR regression fixtures

The seven fixture categories required by Milestone 1A are committed as a deterministic corpus definition. Binary images are generated on demand by `tests/generate_ocr_fixtures.py` and ignored by Git to keep the public repository small.

Ground truth and expected important fields are in `manifest.json`. The benchmark calls the generator automatically if binaries are absent.
