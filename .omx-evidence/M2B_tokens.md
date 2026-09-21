# M2B Token / Execution Evidence

Part: Milestone 2 — Part 2B Restricted Experimental Recognizer  
Branch: `milestone-2b-recognizer`  
Date: 2026-09-21 (Asia/Kolkata)

## Start / end snapshot

| Metric | Start | End |
|---|---|---|
| root tokens | unavailable — no trustworthy historical counter exposed | unavailable — not fabricated |
| subagent tokens | unavailable — no trustworthy historical counter exposed | unavailable — not fabricated |
| cached input | unavailable | unavailable |
| output tokens | unavailable | unavailable |
| number of agents | not reliably metered; bounded orchestration roles were used | not reliably metered; external automated review is tracked separately |
| number of turns | unavailable | unavailable |
| wall-clock duration | unavailable across connector/sandbox boundaries | unavailable — not estimated |
| files changed | 0 for Part 2B at the 2A base | **21 tracked files** in the 2A→2B implementation compare before result/audit evidence |
| tests added | 0 | **14 Part 2B/reproducibility tests** after the PR repair cycle |
| tests passed | **32/32** inherited M1+M2A gate | **44/44** full Python gate |

## Reproducibility evidence

- Train split expanded-sample hash: `023322321bd3fa6d25d190a4920056fca6604b94e32d3f058b7993140e58ad7f`
- Validation split expanded-sample hash: `7ea8668678e77bebafdc60773fc1fbc12134a6864d8e9c635532285073e04e12`
- Held-out test expanded-sample hash: `f3746fb84530a581b58975a31073431d0ab8bc6912f444452462637e28324fb9`
- Frozen model SHA-256: `db5a625cc660eba09f37c9523f6a0769c8e916257a85a10e79c221400e1e3981`
- Direct trainer CLI regenerates the frozen model hash.
- Held-out evaluator reproduces the committed benchmark.
- Train/test and validation/test generated-image hashes are disjoint.
- Trainer source does not read the held-out test manifest.

## RED / GREEN evidence

Required contracts covered:

- RED-20 unknown characters → abstention;
- RED-21 low-confidence secondary cannot override primary OCR;
- RED-22 `0/O`, `1/I`, decimal and comma confusion cases;
- RED-23 train/test leakage protection;
- RED-24 explicit experimental provenance;
- RED-25 experimental failure cannot break primary OCR.

Final local exact-state Python verification:

- compileall: PASS;
- Part 2B suite: PASS;
- full Python suite: **44/44 PASS**;
- M1 OCR regression: exact;
- model reproduction: PASS;
- held-out benchmark reproduction: PASS.

## Held-out result

- experimental supported exact: **5/15 = 33.3%**;
- Tesseract supported exact: **8/15 = 53.3%**;
- experimental supported-input abstention: **10/15 = 66.7%**;
- experimental unknown-input safe abstention: **7/7 = 100%**.

No post-held-out tuning was performed.

## Telemetry rule

Unavailable token/cache/turn/wall-clock fields remain `unavailable`. They are intentionally not estimated just to complete the token-experiment table.


## PR clean-run repair evidence

The first PR quality-gate ran in a fresh GitHub environment and reported:

- **39 passed, 5 errors**;
- all five errors had the same cause: the regenerated raw model hash differed
  from the locally frozen hash;
- clean-run generated hash: `db5a625cc660eba09f37c9523f6a0769c8e916257a85a10e79c221400e1e3981`.

The repair pins the three experiment-sensitive existing dependencies and adds
an evaluator-side actual-file hash check. Final test/CI counts are recorded in
`M2_AUDIT.md` after the repaired head finishes.
