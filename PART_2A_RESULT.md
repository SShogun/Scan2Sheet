# Part 2A Result — OCR Engine Boundary

Branch: `milestone-2a-ocr-interface`

## Scope executed

Part 2A Sections 1 and 2 were executed against merged Milestone 1.

The part is intentionally an internal architecture migration with almost no
new user-visible behavior.

## Intended plan vs current status

| Planned requirement | Status | Evidence |
|---|---|---|
| Training topics reviewed | complete | `docs/research/ocr_engine_boundary.md` |
| `backend/app/ocr/` architecture | complete | base, tesseract, experimental, router, types |
| `OCREngine.recognize(input) -> OCRResult` | complete | Protocol + frozen OCRResult |
| OCRResult text/confidence/engine/metadata | complete | `types.py` |
| Existing extraction output stable | complete | M1B benchmark compatibility test |
| Tesseract API errors stable | complete | 500 + 504 wrapper tests |
| OCR engine independent of invoice/ledger rules | complete | static boundary test |
| Parser avoids direct Tesseract import | complete | parser now calls OCR package adapters |
| Router supports abstaining secondary | complete | primary remains authoritative |
| `/api/extract` contract compatible | complete | route decorator/signature control |
| Current tests remain green | complete | 32/32 local tests |
| No Paddle runtime/weights | complete | no dependency/model changes |

## RED evidence before refactor

Before implementation, the new 2A contract suite produced:

- **6 failures**:
  - OCR engine package/contract absent;
  - TesseractEngine absent;
  - API-error migration contract absent;
  - parser directly imported `pytesseract`;
  - engine package boundary absent;
  - abstaining-secondary router absent.
- **1 control pass**: existing `/api/extract` signature/decorator was present.
- Existing Milestone 1 suite remained **21/21 GREEN** before the migration.

The RED failures were executed rather than represented with `xfail`.

## GREEN evidence

After migration:

- 11 Part 2A contract/compatibility tests pass;
- 21 inherited Milestone 1 tests pass;
- total local gate: **32/32 GREEN**;
- Python compile check passes;
- benchmark comparison exactly preserves, for every M1 fixture:
  - normalized OCR text;
  - CER;
  - WER;
  - important-field accuracy.

Thus the required gate:

```text
old pipeline output ≈ new TesseractEngine output
```

is satisfied with equality on the committed regression corpus for the compared
OCR outputs/metrics.

## Architecture result

```text
backend/app/ocr/
├── __init__.py
├── base.py
├── tesseract.py
├── experimental.py
├── router.py
└── types.py
```

The legacy internal helpers `_decode_image`, `_preprocess_image`, and
`_ocr_image` remain available from `backend.app.ocr`, so existing routes and
the OCR benchmark do not need a public-contract change.

The old `backend/app/ocr.py` module is replaced by the package.

## Reviewer findings and repairs

The reviewer found one architectural issue in the first implementation cut:
`TesseractEngine` raised FastAPI `HTTPException` directly. That was repaired
before exit:

- engine layer now raises `OCRError` / `OCRTimeoutError`;
- the compatibility/API wrapper maps them back to the exact historical
  HTTP 500/504 behavior;
- engine files have no parser or FastAPI dependency.

## Security / dependency / provenance review

- runtime requirements unchanged;
- no PaddleOCR or PaddlePaddle runtime;
- no model/weight file introduced;
- no cloud/network OCR call introduced;
- no secret/credential pattern introduced;
- Tesseract remains the existing local primary engine;
- experimental engine is a non-model abstaining placeholder only.

## Missing things / known limitations

1. OCR confidence remains the existing text-length heuristic. It is preserved
   deliberately so a calibration change is not mixed into the interface refactor.
2. Part 2A does not arbitrate between OCR candidates; even a non-abstaining
   secondary candidate cannot replace primary Tesseract.
3. `ExperimentalEngine` is intentionally only an abstaining placeholder.
   Restricted recognition belongs to Part 2B.
4. Legacy template-table extraction still uses Tesseract layout data, but the
   parser no longer imports or invokes `pytesseract` directly.
5. No PR is opened for 2A because repository workflow is one PR per completed
   milestone; Milestone 2 PR waits for Part 2B + M2 audit.

## Exit verdict

**PASS — Part 2A gate satisfied.**

The engine boundary is modular, old OCR behavior is preserved, the parser no
longer directly owns Tesseract, and the secondary-engine boundary can abstain
without changing primary extraction.
