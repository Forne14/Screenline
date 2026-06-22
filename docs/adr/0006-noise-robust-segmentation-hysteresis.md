# 0006 — Noise-robust segmentation via temporal hysteresis

- Status: Accepted
- Date: 2026-06-22

## Context

The headline requirement: mouse movement, hover, focus rings, spinners, caret
blinks and toasts must **never** create a screenshot, while real screens, modals
and sections must. A naive per-frame threshold over-fires on transient noise;
too-coarse thresholds miss real states.

## Decision

Decide boundaries on a **fused signal with temporal hysteresis**
(`segmentation.py`):

1. Classify each consecutive frame-pair `scroll | cut | static`. **Scroll takes
   precedence over cut** (scrolling changes many pixels but is not a boundary).
2. Split at `cut`s, then clean up:
   - drop short segments (`< min_state_seconds`) that revert to their neighbour
     (`A → X → A`) — kills toasts/spinners/flashes;
   - merge adjacent near-identical segments (`merge_distance`) — repairs
     over-splitting from slow transitions.
3. A scroll pair additionally requires real embedding change
   (`scroll_min_embedding_change`) so a repetitive static screen can't read as
   scrolling.

## Consequences

- **Good:** On the sample, a moving cursor + blinking caret produced **zero**
  false states; 18 frames → 4 clean states. Behaviour is tunable via `config.py`,
  and the config is persisted into the manifest for explainability.
- **Trade-off / accepted:** Hysteresis trades a little boundary-timing precision
  for large robustness. A genuine modal dismissed faster than
  `min_state_seconds` could be dropped — acceptable, and tunable.

## Alternatives considered

- **Per-frame distance threshold only** — simplest, but over-fires on noise and
  shatters scroll runs into many cuts.
- **Fixed-interval keyframes** — trivial but defeats the entire "meaning, not
  pixels" goal.
