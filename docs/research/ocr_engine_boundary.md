# OCR Engine Boundary — Part 2A Research

## Goal

Part 2A is an architecture refactor, not a recognizer upgrade. The existing
Tesseract behavior remains primary while OCR execution is separated from
invoice/ledger parsing so a restricted experimental recognizer can be added
later without leaking model logic into accounting rules.

The implementation must not add PaddleOCR/PaddlePaddle runtime dependencies or
weights.

## Detection vs recognition

Text detection answers **where text is**. Text recognition answers **what the
detected text says**. Scan2Sheet currently uses Tesseract for both page-level
recognition and word/layout information in template tables. The 2A boundary
therefore keeps recognition behind an engine contract and keeps Tesseract-only
layout data behind the Tesseract adapter instead of exposing pytesseract to the
parser.

## CTC, CNN/CRNN and vocabulary

CTC-style recognizers model a sequence of character probabilities and collapse
blank/repeated alignments into a final transcription. CNN/CRNN approaches
typically use convolutional features followed by sequence modelling so they can
recognize variable-length strings without explicit character segmentation.

These concepts matter for Part 2B, but Part 2A deliberately does not implement
or train a neural recognizer. The future restricted vocabulary is an engine
concern; invoice and ledger parsers must remain independent from recognizer
vocabulary.

## Confidence calibration

The existing public OCR path uses the historical text-length score. Part 2A
preserves it exactly because changing calibration during an interface refactor
would make compatibility failures ambiguous. The new `OCRResult.confidence`
therefore carries the current score unchanged. Calibration and arbitration are
separate later concerns.

Tesseract can also expose word confidence through TSV/`image_to_data`, but
that is not substituted for the current API score in this part.

## Model inference lifecycle

A clean OCR lifecycle is:

1. decode image;
2. deterministic preprocessing;
3. invoke an OCR engine;
4. return an `OCRResult` with engine provenance;
5. parse document-specific fields outside the OCR engine;
6. validate accounting structure outside the OCR engine.

This keeps file/image handling, recognition, parsing and validation testable as
separate concerns.

## Protocol vs ABC

Python `typing.Protocol` provides structural subtyping: an implementation only
needs to provide the declared method shape. That is preferable here to forcing
Tesseract and a future experimental recognizer into an inheritance hierarchy.

Part 2A therefore freezes the minimal contract:

```python
class OCREngine(Protocol):
    def recognize(self, image: Image.Image) -> OCRResult: ...
```

The protocol is not marked `runtime_checkable`; no runtime type check is
needed in the request path.

## Result contract

`OCRResult` has four public fields:

- `text`;
- `confidence`;
- `engine`;
- `metadata`.

Abstention is represented through metadata rather than a parser-specific
sentinel. The future secondary engine can therefore return an empty candidate
with `abstained=True` while the router keeps primary OCR authoritative.

## Router boundary

Part 2A intentionally does not arbitrate OCR candidates. If a secondary engine
is configured, the router may record its abstention/candidate provenance in
metadata, but it must return the primary text and confidence. Candidate
selection belongs to later integration work.

## Dependency and provenance decision

No runtime dependency changes are required. The implementation uses the
existing Pillow, pytesseract and Tesseract installation. No model file,
download, cloud endpoint, Paddle runtime or Paddle weight is introduced.

## References reviewed

- Python documentation: `typing.Protocol` and structural subtyping.
- pytesseract documentation: `image_to_string`, `image_to_data`, output
  types and timeout behavior.
- Tesseract TSV documentation: word-level bounding boxes and confidence fields.
- CRNN/CTC literature was reviewed only as training context for Part 2B; no
  neural runtime is introduced in Part 2A.
