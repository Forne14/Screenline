# 0004 — Strip-append vertical stitching

- Status: Accepted
- Date: 2026-06-22

## Context

A scroll run must become one tall, high-quality image. Generic panorama stitchers
(`cv2.Stitcher`, feature-based blending) are built for photographic overlap and
tend to ghost or fail on flat UI content with sticky chrome (a persistent header
that does *not* move while the body scrolls).

## Decision

Stitch by **appending only the newly revealed strip**. Start from the first
frame; for each subsequent frame, append the bottom `dy` pixels (the content that
just scrolled into view). Upward scrolls are normalized by reversing the run so
the output is always top-to-bottom. Height is capped (`stitch_max_height_px`) as
a runaway-scroll guard.

## Consequences

- **Good:** Because each strip is taken from the *leading edge* of motion, a
  sticky **header** never duplicates. Verified on the sample: Sections 1→8 flow
  continuously with no ghosting.
- **Good:** Trivial, fast, transparent — no blending artifacts, no feature
  detection to tune.
- **Trade-off / accepted (documented limitations):**
  - Vertical scroll only; horizontal / 2-D panoramas are future work.
  - A sticky **footer** can duplicate into appended strips.
  - A low-confidence run falls back to a single keyframe rather than producing a
    bad stitch.

## Alternatives considered

- **`cv2.Stitcher` / feature blending** — ghosting on flat UI, sticky-chrome
  failures, slow.
- **Overwrite-on-canvas at cumulative offsets** — simpler to reason about but
  reintroduces sticky-header duplication.
