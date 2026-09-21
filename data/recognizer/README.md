# Restricted recognizer dataset

This directory contains manifests for the public synthetic Part 2B experiment.

```text
data/recognizer/
├── train/manifest.json
├── validation/manifest.json
└── test/manifest.json
```

Images are generated deterministically from public DejaVu fonts by
`tools/recognizer_dataset.py` and are intentionally not committed. Each manifest
stores the SHA-256 of the generated PNG.

The train/validation splits were used to fit and calibrate the model. The final
test split is held-out evidence and must not be used by the trainer.

No confidential, client or production data is present.
