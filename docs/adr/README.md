# Architecture Decision Records

Short records of the non-obvious decisions behind Screenline and *why* they were
made — so future contributors (and reviewers) can challenge them with full
context instead of re-deriving the reasoning.

Format: lightweight [MADR](https://adr.github.io/madr/). One decision per file.

| ADR | Decision | Status |
| --- | -------- | ------ |
| [0001](0001-json-manifest-as-source-of-truth.md) | A JSON manifest is the source of truth, not a database | Accepted |
| [0002](0002-pluggable-embedder-zero-ml-default.md) | Pluggable embedder with a zero-ML default; CLIP optional | Accepted |
| [0003](0003-template-matching-for-scroll-detection.md) | NCC template-matching for scroll detection, not phase correlation | Accepted |
| [0004](0004-strip-append-scroll-stitching.md) | Strip-append vertical stitching | Accepted |
| [0005](0005-project-centric-cross-recording-dedup.md) | Project-centric model with cross-recording state dedup | Accepted |
| [0006](0006-noise-robust-segmentation-hysteresis.md) | Noise-robust segmentation via temporal hysteresis | Accepted |
