# 0002 — Pluggable embedder with a zero-ML default; CLIP optional

- Status: Accepted
- Date: 2026-06-22

## Context

State detection and deduplication need a per-frame similarity signal that is
robust to UI noise (cursor, hover, spinners). CLIP/OpenCLIP gives strong semantic
similarity but pulls in `torch` (~1–2 GB) and is a frequent install failure — a
real barrier to adoption for a local-first OSS CLI. Pure pixel diffs are too
noise-sensitive.

## Decision

Make the embedder a pluggable backend (`embeddings.py`) with a **zero-ML
default**: a normalized 32×32 structural thumbnail (layout) concatenated with an
HSV colour histogram (theme). CLIP is an opt-in extra: `pip install
'screenline[clip]'`, selected with `--embedder clip`. All embeddings are
L2-normalized so a single cosine-distance threshold works for either backend.

## Consequences

- **Good:** Installs everywhere with light deps; fast; deterministic;
  debuggable. At 32×32 a cursor/caret/hover is sub-pixel noise, so "same page +
  mouse moved" stays the same vector — exactly the robustness we need.
- **Good:** A clean upgrade path to semantic quality without changing any other
  stage.
- **Trade-off / accepted:** The default dedupes on *visual* similarity, not
  concept — it won't always know "same page, different data = same screen". That
  is what `--embedder clip` is for. Documented in README and architecture.md.

## Alternatives considered

- **CLIP as the default** — best quality, but the heavy/fragile install
  contradicts local-first and would shrink the user base.
- **Perceptual hash only** — even lighter, but too brittle for clustering and
  carries no colour signal.
