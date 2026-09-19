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
- M1B final local suite after external review fixes: **21 passed**.
- Python compile check: passed.
- Fixture integrity: **7/7 SHA-256 hashes verified**.
- Final benchmark: `artifacts/benchmarks/m1b_after.json`, tied to implementation commit `a2de2905671132bd3b4173f3cabe477ff5863a1b`.
- Clean non-regression: CER 0 → 0, field accuracy 1.0 → 1.0.
- Rotation: field accuracy 0 → 1.0.
- Skew: field accuracy 0 → 1.0.
- Low contrast: field accuracy 0 → 1.0.
- Noise: field accuracy 0 → 0.857143.
- Severe blur: field accuracy 0.857143 → 1.0 and image is independently flagged as blurred.
- Phone-photo perspective fixture remains unchanged at 0 field accuracy; perspective correction is explicitly outside V1.
- 180° page regression: passed.
- default benchmark cannot overwrite `baseline.json`: passed.
- large-image quality analysis capped to 1600 px max dimension: passed.

## Security sanity check

- No network calls in `backend/app/imaging/`.
- No shell execution in the preprocessing package.
- No dynamic code loading.
- No write-to-arbitrary-path behavior.
- No secret/credential pattern hits in Milestone 1 backend/test code.
- Tesseract OCR and OSD are local and time-bounded.
- OSD has an explicit 5-second timeout and safe no-op fallback.
- Image analysis is performed on a bounded representation before expensive Hough/Laplacian work.
- Pixel-wise denoising/enhancement is bounded by the OCR sizing policy.

## Dependency and provenance audit

Runtime dependencies were not expanded for M1B. Existing project dependencies already included OpenCV, pytesseract, and Pillow.

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

## External Sourcery review

Sourcery initially returned **Approval pending** with four blocking findings:

1. default benchmark regeneration could overwrite the historical baseline;
2. 180° pages were not normalized;
3. OSD had no timeout;
4. quality/Hough work could be unbounded for huge images.

All four findings were addressed in commit `a2de2905671132bd3b4173f3cabe477ff5863a1b`, covered by regression tests, and revalidated locally before requesting a fresh review.

## CI / merge gate

`.github/workflows/ci.yml` defines a `quality-gate` job for pull requests to `main`:

1. Python setup and dependencies;
2. Tesseract installation;
3. compile check;
4. full pytest suite;
5. OCR benchmark smoke run;
6. Node setup;
7. frontend production build.

The initial PR run was fully GREEN. A new run is required for the final Sourcery-fix head and is treated as part of milestone sign-off.

## Main branch protection status

**Not applied by this automation.**

GitHub reports no repository rulesets. The active ChatGPT GitHub App has contents/workflows/PR write access but no repository-administration permission and exposes no create/update-ruleset or branch-protection write action.

Recommended ruleset for `main`:

- target: `refs/heads/main`;
- require pull request before merge;
- require status check `quality-gate`;
- require branch to be up to date before merge;
- block force pushes;
- block branch deletion;
- do not require signed commits yet because existing project commits are unsigned;
- human approval count may remain 0 under the current automated-review workflow.

This is an external repository-setting blocker, not a Milestone 1 code/test failure.

## Final PR verification

- final reviewed code head passed local **21/21** tests;
- GitHub Actions `quality-gate` passed compile, pytest, OCR benchmark and frontend build on the post-review head;
- all four Sourcery blocking threads are resolved with exact fix replies;
- Sourcery was explicitly asked twice to re-review the fixed head, but no second disposition was posted during this execution;
- the earlier blocking findings are therefore treated as **addressed and resolved**, not silently ignored.

## Audit verdict

**PASS — Milestone 1 engineering exit gate satisfied.**

The implementation, regression evidence, external-review findings and CI gate are complete. Main-branch ruleset activation remains the separate repository-administration action outstanding.
