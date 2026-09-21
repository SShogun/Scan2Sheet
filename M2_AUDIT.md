# Milestone 2 Audit — Modular OCR & Experimental Recognition

Audit date: 2026-09-21  
Branches: `milestone-2a-ocr-interface` → `milestone-2b-recognizer`  
Current implementation head before this audit/evidence commit: `3cd780dc38f933a8726df6a4c0551588ff8fd315`

## Audit state

The Milestone 2 PR/CI repair cycle has completed for the current implementation.

Engineering gates are GREEN on the repaired PR head. Automated external review
was requested, but both available PR-review bots were quota-blocked. Sourcery
created no substantive inline review threads; that external quota limitation is
recorded explicitly rather than treated as a successful review.

An independent full PR-diff review was performed during the blocked external
review window. Its two legitimate reproducibility/integrity findings were fixed
before the final CI run.

## Scope verification

Milestone 2 stayed within the supplied execution plan:

- OCR implementation is behind a clean engine boundary;
- Tesseract remains the primary engine;
- experimental OCR is restricted, feature-flagged and non-authoritative;
- no general-purpose neural OCR was introduced;
- no cloud OCR/network inference was added;
- no confidential/client dataset was added;
- no candidate arbitration/promotion logic was introduced early;
- arbitration remains deferred to Milestone 3.

## Part 2A — OCR engine boundary

Part 2A introduced:

```text
backend/app/ocr/
├── __init__.py
├── base.py
├── tesseract.py
├── experimental.py
├── router.py
└── types.py
```

Verified contracts:

- `OCREngine.recognize(input) -> OCRResult`;
- OCRResult carries text, confidence, engine and metadata;
- historical Tesseract API error behavior is preserved;
- parser no longer imports/invokes pytesseract directly;
- OCR engine files do not depend on invoice/ledger rules;
- secondary-engine abstention is supported;
- primary OCR cannot be silently replaced;
- `/api/extract` compatibility is preserved;
- M1 benchmark OCR text/CER/WER/field accuracy stayed equal.

Part 2A exit evidence: **32/32 tests GREEN**.

## Part 2B — restricted recognizer

Restricted vocabulary:

`ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,/-:`

Target classes:

- monetary values;
- dates;
- invoice identifiers;
- GSTIN-like alphanumeric strings.

Implementation:

- deterministic public synthetic dataset generator;
- HOG + pixel-thumbnail + geometry features;
- one-nearest-neighbor glyph classification;
- validation-calibrated distance/margin thresholds;
- whole-token abstention if any glyph is uncertain;
- feature-flagged secondary routing;
- no automatic secondary-over-primary replacement.

## Required RED contracts

| Contract | Final status |
|---|---|
| RED-20 unknown characters abstain | GREEN |
| RED-21 low-confidence secondary cannot override primary | GREEN |
| RED-22 0/O, 1/I, decimal/comma confusion cases | GREEN |
| RED-23 train/test duplicate-hash protection | GREEN |
| RED-24 experimental provenance visible | GREEN |
| RED-25 experimental failure cannot break primary OCR | GREEN |

## Full regression status before PR

- Python compile check: **PASS**.
- Full Python suite: **44/44 PASS**.
- Historical M1 OCR benchmark outputs: **exactly preserved**.
- Part 2B direct trainer CLI: **PASS after import-path repair**.
- Frozen model reproduction: **PASS**.
- Held-out evaluator reproduction: **PASS**.

The import-path problem was found during exact-state verification before PR creation. The 2B implementation commit was amended, preserving the user's low-commit requirement rather than adding a repair commit.

## Dataset / leakage audit

Committed manifests:

- `data/recognizer/train/manifest.json`
- `data/recognizer/validation/manifest.json`
- `data/recognizer/test/manifest.json`

Expanded sample hashes:

- train: `023322321bd3fa6d25d190a4920056fca6604b94e32d3f058b7993140e58ad7f`;
- validation: `7ea8668678e77bebafdc60773fc1fbc12134a6864d8e9c635532285073e04e12`;
- held-out test: `f3746fb84530a581b58975a31073431d0ab8bc6912f444452462637e28324fb9`.

Audit checks:

- train/test generated-image hashes are disjoint;
- validation/test generated-image hashes are disjoint;
- abstention samples are prohibited from training;
- trainer source does not consume the held-out test manifest;
- model/config/threshold freeze is explicitly recorded before held-out evaluation;
- no post-held-out tuning is recorded.

## Model configuration / provenance

Experiment: `m2b-hog-nn-v1`.

Frozen generated model SHA-256:

`db5a625cc660eba09f37c9523f6a0769c8e916257a85a10e79c221400e1e3981`

Model strategy:

- generated locally;
- binary model is gitignored;
- committed manifests + trainer reproduce it;
- no downloaded opaque model;
- no new ML runtime;
- no runtime dependency added by Part 2B.

The public synthetic dataset is generated from locally available public DejaVu fonts. No client or production document is used.

## Held-out evaluation

Validation results, used for calibration:

- supported: **10/10 exact = 100%**;
- unknown-character samples: **8/8 abstained = 100%**.

Final held-out results:

- experimental supported exact: **5/15 = 33.3%**;
- experimental abstention on supported inputs: **10/15 = 66.7%**;
- Tesseract supported exact on the same crops: **8/15 = 53.3%**;
- experimental unknown/out-of-scope abstention: **7/7 = 100%**.

Conclusion: the experiment is **not** accurate enough to replace Tesseract. Its useful demonstrated property is conservative abstention/provenance, not recognition superiority.

## Fallback / primary-safety audit

PASS locally.

- confident primary OCR can skip secondary work;
- low-confidence primary can collect a secondary candidate;
- secondary candidate remains metadata only;
- secondary abstention preserves primary output;
- secondary exception preserves primary output;
- experimental model missing/corrupt path returns controlled abstention rather than breaking primary OCR.

Candidate arbitration is intentionally not implemented in Milestone 2.

## Dependency / network provenance

Milestone 2 adds no new runtime/development package. After the first PR clean-run exposed raw-model hash drift across numeric/image-library versions, the repair adds `backend/requirements-repro.txt` to pin the existing experiment-sensitive packages (`numpy==2.4.6`, `opencv-python==4.14.0.94`, `Pillow==11.3.0`) for development/CI reproduction.

Review of added M2 diff text found no added network client/API call, model-download URL, production endpoint, credential material or client-specific implementation. Mentions of “production/client” occur only in documentation statements declaring those items absent/out of scope.

## Public/confidential boundary

PASS for current M2 diff.

- recognizer corpus is deterministic synthetic data;
- no real invoice/accounting record is committed;
- no proprietary model is committed;
- no department/tender workflow is implemented;
- no production/internal endpoint is introduced;
- experimental model evidence contains only public synthetic sample outputs and hashes.

## Clean-repository reproduction

PASS on GitHub Actions.

The authoritative clean runner checked out the PR merge ref and completed:

- dependency installation;
- Python compile check;
- full pytest suite;
- OCR benchmark smoke run;
- restricted-model reproduction;
- held-out benchmark reproduction;
- Node setup;
- frontend dependency installation/build.

Final repaired-head run: GitHub Actions `ci` run **#9** / run ID
`35606510633`.

Result: **quality-gate SUCCESS**.

## Token / orchestration evidence

- `.omx-evidence/M2A_tokens.md`
- `.omx-evidence/M2B_tokens.md`

Historical root/subagent/cache/output token counters are unavailable from the execution surface and are not fabricated.

## Known limitations

1. Experimental held-out exact accuracy is **33.3%**, below Tesseract's **53.3%** on the same supported token crops.
2. The experiment abstains on **66.7%** of supported held-out inputs; it is deliberately conservative.
3. Full phone-photo/perspective OCR remains a known M1 limitation and is not solved by the restricted token recognizer.
4. Tesseract's existing confidence heuristic remains unchanged.
5. Milestone 3 arbitration and accounting-validation-based candidate choice are not implemented.
6. Automated external PR review remains quota-blocked: Sourcery exhausted its
   250,000-diff-character 7-day budget and Copilot also reported a quota limit.
   Sourcery produced **0 substantive inline threads**. This is an external
   review-service limitation, not a hidden code/CI pass.
7. The GitHub Actions log carries Node/action deprecation warnings, but they do
   not fail the current quality gate.

## Pre-PR verdict

The pre-PR audit was **CONDITIONAL PASS** pending clean CI and PR review. That
condition led directly to the clean-run reproducibility failure and repair
described below.

## PR / review cycle — interim

- PR: **#2** — `Milestone 2: modular OCR and restricted experimental recognizer`.
- First GitHub `quality-gate`: **FAILED** at pytest with **39 passed, 5 errors**.
- Failure cause: clean-run model SHA differed from the unpinned local environment.
- Clean-run SHA: `db5a625cc660eba09f37c9523f6a0769c8e916257a85a10e79c221400e1e3981`.
- Independent diff review found the same reproducibility defect and a second
  integrity problem: the held-out evaluator reported the manifest's expected
  hash without independently verifying the supplied model file.
- Repair: pin the existing experiment-sensitive dependency versions, make the
  evaluator verify the actual model hash, and add two regression tests.
- Sourcery auto-review: **attempted but quota-blocked**; no substantive Sourcery
  inline threads exist to inspect or resolve.
- Copilot auto-review: quota-blocked.
- Final repaired-head CI: **PASS** — GitHub Actions run #9 / `35606510633`.
- Final repaired-head pytest: **46/46 PASS**.
- OCR benchmark smoke run: **PASS**.
- Restricted model reproduction and exact held-out benchmark comparison: **PASS**.
- Frontend production build: **PASS** (`vite build`, completed successfully).
- Held-out metrics remained unchanged:
  - experimental supported exact: **33.3%**;
  - experimental unknown abstention: **100%**;
  - Tesseract supported exact: **53.3%**.

## Final PR / review status

PR **#2** is open and contains the single Milestone 2 integration/review cycle.

### Automated external review

- Sourcery auto-review was requested/attempted.
- Sourcery response: review budget exhausted; another substantive review cannot
  be obtained until its quota resets.
- Substantive Sourcery inline threads inspected: **0**.
- Copilot PR review was also quota-blocked.
- These quota responses are **not** counted as code-review approval.

### Independent review + repair

Because both external review bots were unavailable, an independent full PR-diff
review was performed instead. It found two legitimate issues:

1. raw model reproducibility depended on unpinned NumPy/OpenCV/Pillow versions;
2. the held-out evaluator echoed the manifest's expected model hash without
   independently hashing and validating the supplied model file.

Both were repaired in commit
`ece58293c731b20df2a0bdc6f8aefc68c333f65a`, with regression tests.

### Final engineering verdict

**PASS — Milestone 2 implementation, regression, reproducibility, fallback,
provenance, clean-run CI and frontend build gates are satisfied.**

**External-review status: BLOCKED BY REVIEW-SERVICE QUOTA, explicitly recorded.**

This audit does not claim a Sourcery approval that did not occur. No substantive
Sourcery thread was skipped. Milestone 3 arbitration remains out of scope and
has not been started.
