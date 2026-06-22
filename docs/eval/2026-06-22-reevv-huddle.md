# Eval — Slack-huddle screen recordings (reevv-realty), 2026-06-22

First dogfood pass (issue **#2 / P0-1**) on *real* recordings, not synthetic
fixtures. Two iPhone screen recordings of a Slack **huddle** where a teammate
("Josh") screen-shared his Mac while walking through the reevv-realty concept.

> **Confidentiality:** the recordings show reevv-realty's product. No frames are
> committed to this (public) repo — only aggregate metrics and findings. The
> actual artifacts live in the private reevv project dir.

## Inputs

| | demo-1 | demo-2 |
|---|---|---|
| Encoded | 1180×2556 HEVC, rotation→ **2556×1180 landscape** | same |
| Duration | ~18.9 min | ~11.9 min |
| Shared content | Excalidraw architecture diagram (panned/zoomed) | a text document (read top-to-bottom) |
| Chrome | iPhone notch + recording dot; Slack huddle header ("Josh / live screen sharing", "Leave"); **auto-hiding huddle control bar**; macOS dock + Chrome tab bar inside the share | same, **plus a live participant-camera thumbnail** that moves every frame |

A deliberately hard case: the share **fills the whole frame** and the Slack/iOS
chrome is **overlaid on content**, not in clean borders.

## Method

```bash
screenline init . && screenline add demo-1 && screenline add demo-2
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
   dark **Excalidraw diagram** discussion and a walkthrough of the **actual
   reevv-realty app screens** (light UI). The app-screen states were segmented
   cleanly and are genuinely useful; scroll **stitching reconstructed a full
   listing-detail page** (unit specs, amenities, day/night views) that's readable
   end-to-end. Mouse movement / caret / the ticking clock created no states.

2. **Continuous pan/zoom over-segments badly.** The Excalidraw walkthrough drove
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

5. **Sticky/floating elements duplicate in stitches.** A floating "AI Guide"
   button was captured 3× down the stitched listing page. → **#28 (P1-10)**,
   extends #8.

6. **Rotation handled correctly.** Both clips carried a 90° display-matrix;
   ffmpeg auto-rotated to landscape consistently in probe, sampling and output —
   no manual `-noautorotate` needed.

## Actions taken / filed

- **Code (this PR, branch `quality/p0-1-dogfood`):** fixed `estimate_shift` to
  downscale frames internally (longest side ≤ 720) and report shifts in
  full-resolution pixels. Full-res `matchTemplate` on 2556×1180 frames was
  prohibitively slow; without this the build would not finish in reasonable time.
  Added a regression test (`test_estimate_shift_downscales_large_frames_and_returns_fullres`).
- **Issues filed:** #25 (P1-7 crop flag), #26 (P1-8 ignore-region masks),
  #27 (P1-9 pan/zoom over-segmentation), #28 (P1-10 sticky/floating stitch
  dedup), #29 (P0-7 faster ingest via downscale/transcode).

## Recommendation for users today

For huddle/whiteboard recordings, until #25–#29 land: pre-transcode to a
downscaled H264 (≈6× faster), expect over-segmentation on panned canvases, and
treat the **app-screen** states + **stitched pages** as the high-value output.
For a quick clean run, raise `--cut-distance` (0.2+) and `--fps` only if scrolls
are fast.
