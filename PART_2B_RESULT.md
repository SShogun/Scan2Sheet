# Part 2B Result — Restricted Experimental Recognizer

Branch: `milestone-2b-recognizer`  
Implementation commit: `3cd780dc38f933a8726df6a4c0551588ff8fd315`  
Date: 2026-09-21 (Asia/Kolkata)

## Scope executed

Part 2B Sections 1 and 2 were implemented as a deliberately restricted OCR experiment.

The recognizer is **not general-purpose OCR** and does not replace Tesseract. Its vocabulary is:

```text
ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,/-:
```

Target token classes are monetary values, dates, invoice identifiers and GSTIN-like alphanumeric strings.

## What was built

- deterministic synthetic train / validation / held-out test manifests;
- HOG + normalized pixel + geometry glyph features;
- one-nearest-neighbor restricted recognizer;
- per-class distance and margin thresholds;
- explicit abstention for uncertain or out-of-scope input;
- frozen model hash and experiment evidence;
- trainer and held-out evaluator CLIs;
- feature-flagged secondary OCR integration;
- primary-Tesseract safety/fallback behavior;
- RED-20 through RED-25 regression coverage;
- CI reproduction steps for model hash and held-out benchmark.

## RED → GREEN evidence

Part 2B adds 12 executable tests covering the required RED-20…RED-25 contracts plus model/evidence integrity.

Final local Python gate on the repaired exact implementation state:

- compileall: **PASS**;
- full Python suite: **44 / 44 PASS**;
- inherited M1 OCR benchmark outputs: **exactly preserved**;
- model regeneration: **PASS**;
- held-out benchmark reproduction: **PASS**.

A real CI-path defect was found during exact-state verification: direct execution of the trainer/evaluator from `tools/` initially could not import the repository `backend` package. The single implementation commit was amended rather than adding a repair commit. Direct CLI invocation now works.

## Frozen model

SHA-256:

`275530db43b188bae28362bba7d644e3a3d9a843795116cb18a95b975bf5acb8`

The generated model binary is not committed. It is reproduced from committed public synthetic manifests.

## Validation results

Validation is selection/calibration evidence, not final accuracy:

- supported validation tokens: **10 / 10 exact = 100%**;
- unknown-character validation samples: **8 / 8 abstained = 100%**.

## Held-out results

The final held-out split was not used for model selection or post-test repair.

Supported held-out tokens:

- experimental recognizer exact: **5 / 15 = 33.3%**;
- experimental recognizer abstention on supported inputs: **10 / 15 = 66.7%**;
- Tesseract exact on the same supported crops: **8 / 15 = 53.3%**.

Unknown / out-of-scope held-out inputs:

- experimental safe abstention: **7 / 7 = 100%**.

## Interpretation

The experiment demonstrates reproducibility, provenance, held-out separation and safe abstention. It does **not** demonstrate superiority over Tesseract.

Tesseract remains the authoritative primary engine. The experimental recognizer remains feature-flagged and only provides an optional candidate. Arbitration/promotion is deferred to Milestone 3.

## Remaining gate

Local frontend build could not be completed because the execution sandbox had no npm package cache and could not reach `registry.npmjs.org`.

The Milestone 2 PR therefore still requires the GitHub `quality-gate`, including:

- full pytest suite;
- OCR benchmark smoke run;
- recognizer reproduction;
- frontend `npm ci`;
- frontend `npm run build`.

## Exit status

**Part 2B implementation: complete.**  
**Python/OCR verification: complete and passing.**  
**Milestone 2 sign-off: pending GitHub CI + automated external review.**
