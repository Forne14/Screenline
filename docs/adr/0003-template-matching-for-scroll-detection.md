# 0003 — NCC template-matching for scroll detection, not phase correlation

- Status: Accepted
- Date: 2026-06-22

## Context

Detecting scroll requires estimating the vertical shift between consecutive
frames. The textbook choice is FFT phase correlation (`cv2.phaseCorrelate`). In
practice, on real screen content (sharp anti-aliased text, repeated rows, large
inter-frame shifts at 1 FPS) it produced **wrong-sign and inconsistent peaks** —
measured on the sample recording, scroll runs broke apart because individual
estimates flipped between `+180px` and `-166px`.

## Decision

Estimate the shift by **normalized cross-correlation template matching**
(`cv2.matchTemplate`, `TM_CCOEFF_NORMED`): take a horizontal band from the centre
of frame *N+1* and locate it inside frame *N*. The match position gives `dy`
(and `dx`), and the NCC peak gives a clean confidence score. The band is central
to avoid sticky headers/footers and corner cursor activity.

## Consequences

- **Good:** On the same sample, every scroll transition now resolves to a
  consistent `dy≈180px` with `response≈0.99`; the run is detected cleanly. Robust
  to large shifts (the band can be found anywhere in the search image) and to
  sharp text.
- **Good:** The same estimator is reused for stitching offsets.
- **Trade-off / accepted:** `matchTemplate` is O(W·H) per frame — fine at 1 FPS;
  it assumes near-pure translation (true for vertical scroll). Sub-pixel
  precision is integer-pixel here, which is adequate for stitching.
- A secondary guard (ADR-0006) requires real embedding change too, so a
  *repetitive static* screen with identical rows can't masquerade as scrolling.

## Alternatives considered

- **Phase correlation** — elegant and sub-pixel, but unreliable on this content.
- **ORB/feature matching + homography** — heavier, overkill for 1-D translation,
  and flaky on low-texture UI regions.
