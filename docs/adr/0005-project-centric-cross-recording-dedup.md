# 0005 — Project-centric model with cross-recording state dedup

- Status: Accepted
- Date: 2026-06-22

## Context

The same screen (e.g. a Dashboard) appears across many recordings and many times
within one. A per-video design would emit duplicate screenshots and lose the fact
that recordings describe one product. The brief is explicit: design around a
**project**, not a single video.

## Decision

A project (a folder with `.screenline/`) is the primary unit. Recordings are
*referenced* (never copied). The build runs per-recording segmentation, then a
**global clustering** stage (`clustering.py`) groups segments across all
recordings into shared `State`s. Each state keeps **one** representative
screenshot and an `occurrences[]` list (recording + timecodes). Clustering is
greedy single-pass agglomeration on segment centroids with a cosine threshold
(`merge_distance`).

## Consequences

- **Good:** "Dashboard seen in 3 meetings" → one state, three occurrences.
  Verified: 6 segments → 4 states on the two-recording sample (33% dedup).
- **Good:** Scroll states are kept apart from static viewports during clustering
  (a stitched page and a single frame are different artifacts).
- **Good:** Greedy O(n²-ish) over *segments* (tens–hundreds), not frames — no
  FAISS/ANN needed; deterministic and fast.
- **Trade-off / accepted:** Greedy clustering is order-sensitive at the margins;
  with a sensible `merge_distance` this is immaterial at MVP scale. A future
  large-scale mode could swap in ANN behind the same interface.

## Alternatives considered

- **Per-video processing** — simpler, but violates the core requirement and
  duplicates output.
- **Full hierarchical clustering / FAISS** — unnecessary at this scale; more deps
  and tuning.
