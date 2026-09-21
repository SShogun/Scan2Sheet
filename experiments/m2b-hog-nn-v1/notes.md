# m2b-hog-nn-v1 experiment notes

## Decision

Selected a restricted HOG + pixel/geometry nearest-neighbor recognizer after
considering a tiny CRNN/CTC model, Tesseract whitelist-only recognition and
classical template/KNN-style recognition.

The choice was frozen using train + validation only.

## Frozen model

- engine: `experimental-restricted-v1`
- vocabulary: `ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,/-:`
- generated model SHA-256:
  `275530db43b188bae28362bba7d644e3a3d9a843795116cb18a95b975bf5acb8`
- runtime dependencies added: none
- model binary committed: no
- artifact is regenerated deterministically from the committed manifests

## Validation before held-out evaluation

- supported tokens: 10/10 exact
- unknown-character samples: 8/8 abstained
- no train/validation duplicate PNG hashes

`FROZEN_BEFORE_TEST` records the model/config freeze boundary.

## Held-out evaluation

The final test manifest was evaluated after the freeze and was not used for
selection or repair.

- supported samples: 15
- experimental exact: 5/15 = 33.3%
- experimental abstention on supported samples: 10/15 = 66.7%
- unknown-character samples: 7
- safe experimental abstention: 7/7 = 100%
- current Tesseract exact on supported crops: 8/15 = 53.3%

No post-test tuning was performed.

## Interpretation

The experimental model is intentionally conservative and currently weaker than
Tesseract on held-out supported crops. This is a useful negative result: the
engine has demonstrated safe abstention and provenance, but has not demonstrated
enough recognition quality to become a default or replacement OCR path.

Milestone 2 may expose it only behind the experimental feature flag. Candidate
arbitration remains deferred to Milestone 3.
