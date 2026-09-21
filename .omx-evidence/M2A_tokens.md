# M2A Token / Execution Evidence

Part: Milestone 2 — Part 2A OCR Engine Boundary  
Branch: `milestone-2a-ocr-interface`  
Date: 2026-09-20 (Asia/Kolkata)

| Metric | Start | End |
|---|---:|---:|
| root tokens | unavailable | unavailable |
| subagent tokens | unavailable | unavailable |
| cached input | unavailable | unavailable |
| output tokens | unavailable | unavailable |
| number of agents | 3 bounded logical roles | 3 bounded logical roles |
| number of turns | unavailable | unavailable |
| wall-clock duration | unavailable | unavailable |
| files changed | 0 | OCR module→package migration + parser boundary + research/tests/result |
| tests added | 0 | 11 Part 2A contract/compatibility tests |
| tests passed | 21 inherited M1 tests before refactor | 32/32 total after refactor |

## RED / GREEN evidence

Pre-refactor 2A contract run:

- 6 failed;
- 1 control passed;
- inherited M1 suite: 21/21 passed.

Post-refactor:

- Part 2A contract suite: 11/11 passed;
- inherited M1 suite: 21/21 passed;
- total: 32/32 passed;
- compileall: passed;
- M1B normalized OCR text/CER/WER/field-accuracy compatibility: passed for all 7 categories.

## Commit-economy note

Part 2A deliberately uses two meaningful commits only:

1. engine-boundary migration + tests + research;
2. independent-review cleanup + final evidence.

Unavailable token/cache/turn metrics are not estimated.
