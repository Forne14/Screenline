# Eval — Slack-huddle screen recordings, 2026-06-22

First dogfood pass (issue **#2 / P0-1**) on *real* recordings, not synthetic
fixtures. Two iPhone screen recordings of a Slack **huddle** in which a teammate
screen-shared a Mac while walking through an early-stage product.

> **Confidentiality:** the recordings show a third party's unreleased product. No
> frames and no product specifics are recorded here — only aggregate metrics and
> Screenline behaviour. The raw artifacts stay in a private, non-tracked folder.

## Inputs

| | clip A | clip B |
|---|---|---|
| Encoded | 1180×2556 HEVC, rotation→ **2556×1180 landscape** | same |
| Duration | ~18.9 min | ~11.9 min |
| Shared content | a whiteboard / diagramming canvas (panned & zoomed) | a long text document (read top-to-bottom) |
| Chrome | iPhone notch + recording dot; Slack huddle header + "Leave"; **auto-hiding huddle control bar**; macOS dock + browser tab bar inside the share | same, **plus a live participant-camera thumbnail** that moves every frame |

A deliberately hard case: the share **fills the whole frame** and the Slack/iOS
chrome is **overlaid on content**, not in clean borders.

## Method

```bash
screenline init . && screenline add clipA && screenline add clipB
screenline build --cut-distance 0.11    # lower than default 0.18 for shared chrome
```

- **Pass 1** — recordings as-is (full frame, HEVC).
- **Pass 2** — `ffmpeg crop=2360:1010:170:60,scale=1280:-2` (drop iPhone notch +
  macOS dock, halve resolution), then the same build.
- **Pass 2b** — Pass 2's cropped frames rebuilt with `--cut-distance 0.20` to
  test whether crop needs re-tuning.

## Results

| | Pass 1 (full, HEVC) | Pass 2 (crop+½res, H264) | Pass 2b (crop, cut 0.20) |
|---|---|---|---|
| frames sampled | 1850 | 1850 | 1850 (reused) |
| segments → **states** | 95 → **71** | 128 → **108** | 94+ → **93** |
| stitched scroll states | 8 | 14 | 14 |
| transitions | 91 | 124 | 103 |
| dedup ratio | 25% | 16% | 11% |
| wall time | **842 s** | **145 s** | ~154 s (reused frames) |

Target for ~30 min of video would be roughly 15–45 screenshots. All passes
**over-produced** states.

## Findings

1. **It works — and the useful output is real.** The recording has two phases: a
   diagram discussion and a walkthrough of **actual app screens**. The app-screen
   states were segmented cleanly and are genuinely useful; scroll **stitching
   reconstructed a long content-detail page** that reads end-to-end. Mouse
   movement / caret / the ticking clock created no states.

2. **Continuous pan/zoom over-segments badly.** The whiteboard walkthrough drove
   ~83–116 of the segments — every pan/zoom view is "meaningfully different", so
   the discrete-screen model explodes. This is the single biggest quality issue
   here. → **#27 (P1-9)**.

3. **Cropping made it *worse*, not better (at the same threshold).** Removing the
   static Slack/iOS chrome let the continuously-varying canvas dominate the
   embedding, so more frame-pairs crossed `cut_distance=0.11` (108 vs 71 states).
   The chrome was acting as a *stabilizer*. Re-tuning the cropped run to
   `cut_distance=0.20` (Pass 2b) only recovered 108 → 93 states — better, but
   still far over target, because the **root cause is pan/zoom (finding 2), not
   the threshold**. **Lesson:** a crop must be paired with a higher `cut_distance`,
   a static rectangle can't remove overlays anyway, and neither addresses
   continuous-canvas over-segmentation. → **#25 (crop flag, with the re-tune
   caveat)**, **#26 (ignore-region masks for the overlaid huddle controls + camera
   PiP)**.

4. **Downscale/transcode is a huge speed win.** Cropped + 1280-wide **H264** ran
   **5.8× faster** than full-res **HEVC** (145 s vs 842 s) with no loss of useful
   states — HEVC software decode dominated Pass 1. → **#29 (P0-7)**.

5. **Sticky/floating elements duplicate in stitches.** A floating on-page button
   was captured 3× down a stitched page. → **#28 (P1-10)**, extends #8.

6. **Rotation handled correctly.** Both clips carried a 90° display-matrix;
   ffmpeg auto-rotated to landscape consistently in probe, sampling and output —
   no manual `-noautorotate` needed.

7. **Stale frame cache on `--fps` change.** Rebuilding with a different `--fps`
   reuses the old frames with wrong timestamps. → **#31 (P0-8)**; clear
   `.screenline/cache/` until fixed.

## Actions taken / filed

- **Code (PR #30):** fixed `estimate_shift` to downscale frames internally
  (longest side ≤ 720) and report shifts in full-resolution pixels. Full-res
  `matchTemplate` on 2556×1180 frames was prohibitively slow; without this the
  build would not finish in reasonable time. Added a regression test.
- **Issues filed:** #25 (crop flag), #26 (ignore-region masks), #27 (pan/zoom
  over-segmentation), #28 (sticky/floating stitch dedup), #29 (faster ingest),
  #31 (frame-cache `--fps` staleness).

## Recommendation for users today

For huddle/whiteboard recordings, until #25–#29 land: pre-transcode to a
downscaled H264 (≈6× faster), expect over-segmentation on panned canvases, and
treat the **app-screen** states + **stitched pages** as the high-value output.
For a quick clean run, raise `--cut-distance` (0.2+); raise `--fps` only if
scrolls are fast (and clear the cache first — #31).
