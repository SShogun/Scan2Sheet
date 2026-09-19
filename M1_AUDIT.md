# Milestone 1 Audit — Preprocessing & OCR Quality

Audit date: 2026-09-19  
Branches: `milestone-1a-baseline` → `milestone-1b-preprocessing`

## Scope verification

Milestone 1 stayed within the execution plan:

- deterministic OpenCV/Pillow/Tesseract preprocessing only;
- orientation normalization, bounded deskew, denoising, contrast enhancement, adaptive thresholding and blur scoring;
- no neural enhancement;
- no super-resolution;
- no complex document segmentation;
- no handwriting recognition;
- no cloud OCR;
- no network-dependent model or preprocessing call;
- no client-specific schema or production URL;
- no confidential/private dataset.

The public OCR corpus is synthetic and contains only invented accounting values.

## Test and benchmark audit

- M1A baseline captured before preprocessing implementation.
- Mandatory RED failures were demonstrated without `xfail`.
- M1B final suite: **18 passed**.
- Python compile check: passed.
- Fixture integrity: **7/7 SHA-256 hashes verified**.
- Final benchmark: `artifacts/benchmarks/m1b_after.json`.
- Clean non-regression: CER 0 → 0, field accuracy 1.0 → 1.0.
- Rotation: field accuracy 0 → 1.0.
- Skew: field accuracy 0 → 1.0.
- Low contrast: field accuracy 0 → 1.0.
- Noise: field accuracy 0 → 0.857143.
- Severe blur: field accuracy 0.857143 → 1.0 and image is independently flagged as blurred.
- Phone-photo perspective fixture remains unchanged at 0 field accuracy; perspective correction is explicitly outside V1.

## Security sanity check

- No network calls in `backend/app/imaging/`.
- No shell execution in the preprocessing package.
- No dynamic code loading.
- No write-to-arbitrary-path behavior.
- No secret/credential pattern hits in Milestone 1 backend/test code.
- Tesseract invocation remains local with a timeout.
- Image transformations operate on decoded in-memory arrays/images.

## Dependency and provenance audit

Runtime dependencies were not expanded for M1B. Existing project dependencies already included:

- OpenCV;
- pytesseract;
- Pillow.

Part 1A adds only a development/test dependency, pytest, through `backend/requirements-dev.txt`.

The implementation uses standard local OpenCV algorithms and Tesseract OSD; no external model asset, opaque binary model download, restricted-weight dependency, or proprietary corpus is introduced.

## Optional proprietary model check

No proprietary model is used. Therefore no optional-model fallback/provenance branch is required for Milestone 1.

## Public/private boundary audit

PASS.

- fixture content is synthetic;
- repository code contains no client identifiers;
- no production/internal URL is introduced;
- benchmark artifacts contain only synthetic OCR outputs and local environment versions;
- no real accounting records are stored.

## Independent reviewer / angel pass

The reviewer challenged clean-path safety and found that the initial impulse-noise heuristic could count legitimate pure-white page background as noise. It was replaced with a local-median deviation metric and covered by a regression test. The full suite remained GREEN afterward.

## CI / merge gate

`.github/workflows/ci.yml` defines a `quality-gate` job for pull requests to `main`:

1. Python setup and dependencies;
2. Tesseract installation;
3. compile check;
4. full pytest suite;
5. OCR benchmark smoke run;
6. Node setup;
7. frontend production build.

## Main branch protection status

**Not applied by this automation.**

GitHub reports no repository rulesets. The active GitHub App connection lacks repository-administration mutation access; its classic branch-protection endpoint returns `403 Resource not accessible by integration`, and no create/update-ruleset action is exposed.

Recommended ruleset for `main`:

- target: `refs/heads/main`;
- require pull request before merge;
- require status check `quality-gate`;
- require branch to be up to date before merge;
- block force pushes;
- block branch deletion;
- do not require signed commits yet because existing project commits are unsigned;
- human approval count can remain 0 under the current automated-review workflow.

This is an external repository-setting blocker, not a Milestone 1 code/test failure.

## Audit verdict

**PASS — Milestone 1 engineering exit gate is satisfied.**

Milestone 1 may be submitted as one pull request to `main`. Main-branch ruleset activation remains the only requested repository-admin action outstanding.
