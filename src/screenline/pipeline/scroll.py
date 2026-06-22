"""Scroll detection and stitching — one of Screenline's core features.

Scrolling is *not* navigation and *not* a new screen: it's the same logical
page revealing more of itself. We must (a) recognise a scroll run so it collapses
into one state instead of many false "cuts", and (b) stitch the run into a single
tall image.

Approach:
  detection  -- estimate the vertical shift between two consecutive frames with
                phase correlation (Hanning-windowed, FFT-based, sub-pixel,
                robust to compression noise). A run of consistent-sign,
                high-confidence, mostly-vertical shifts is a scroll.
  stitching  -- "strip append": start from the first frame, then for each step
                append only the *newly revealed* strip (height = the incremental
                shift). This sidesteps sticky-header ghosting, since each strip
                is taken from the leading edge of motion.

MVP scope: vertical scroll only. Horizontal / 2-D panoramas are future work; a
low-confidence run falls back to a single keyframe.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from screenline.config import Config


@dataclass
class ShiftEstimate:
    dx: float
    dy: float
    response: float  # phase-correlation peak confidence in [0, 1]


def estimate_shift(prev_gray: np.ndarray, cur_gray: np.ndarray) -> ShiftEstimate:
    """Estimate translation of `cur` relative to `prev` (positive dy = scroll down).

    We locate a horizontal band taken from the *middle* of `cur` inside `prev`
    via normalized cross-correlation template matching. This is far more robust
    than phase correlation on UI content (sharp text, repeated rows, large
    inter-frame shifts) and yields a clean confidence peak. The band is taken
    from the centre to avoid sticky headers/footers and corner cursor activity.

    dy > 0 means content moved up between prev->cur, i.e. the user scrolled down.
    """
    if prev_gray.shape != cur_gray.shape or prev_gray.size == 0:
        return ShiftEstimate(0.0, 0.0, 0.0)

    h, w = cur_gray.shape[:2]
    bh = max(40, int(h * 0.18))
    by0 = int(h * 0.40)
    bx0, bw = int(w * 0.15), int(w * 0.70)
    template = cur_gray[by0 : by0 + bh, bx0 : bx0 + bw]
    if template.shape[0] >= h or template.shape[1] >= w:
        return ShiftEstimate(0.0, 0.0, 0.0)

    res = cv2.matchTemplate(prev_gray, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    mx, my = max_loc
    return ShiftEstimate(dx=float(mx - bx0), dy=float(my - by0), response=float(max_val))


def is_scroll(est: ShiftEstimate, cfg: Config) -> bool:
    return (
        est.response >= cfg.scroll_min_response
        and abs(est.dy) >= cfg.scroll_min_shift_px
        and abs(est.dx) <= cfg.scroll_max_horizontal_px
    )


@dataclass
class ScrollRun:
    start_index: int  # index into the frame list (inclusive)
    end_index: int  # inclusive
    direction: int  # +1 scrolling down, -1 scrolling up


def find_scroll_runs(
    shifts: list[ShiftEstimate | None],
    cfg: Config,
    eligible: list[bool] | None = None,
) -> list[ScrollRun]:
    """Group consecutive scroll transitions into runs.

    `shifts[i]` is the transition from frame i to frame i+1 (so len == n-1).
    A run [start..end] of frames covers transitions start..end-1. `eligible`, if
    given, additionally gates each pair (e.g. require real embedding change so a
    repetitive static screen can't masquerade as scrolling).
    """

    def ok(i: int) -> bool:
        est = shifts[i]
        if est is None or not is_scroll(est, cfg):
            return False
        return eligible[i] if eligible is not None else True

    runs: list[ScrollRun] = []
    i = 0
    n = len(shifts)
    while i < n:
        if not ok(i):
            i += 1
            continue
        direction = 1 if shifts[i].dy >= 0 else -1
        j = i
        while j < n and ok(j) and (1 if shifts[j].dy >= 0 else -1) == direction:
            j += 1
        # transitions i..j-1 -> frames i..j
        if (j - i) >= cfg.scroll_min_run:
            runs.append(ScrollRun(start_index=i, end_index=j, direction=direction))
        i = j if j > i else i + 1
    return runs


def stitch_vertical(frame_paths: list[Path], shifts: list[ShiftEstimate], cfg: Config) -> np.ndarray | None:
    """Stitch a vertical scroll run into one tall image (BGR).

    `shifts[k]` is the transition from frame_paths[k] to frame_paths[k+1].
    Returns None if there isn't enough usable motion to stitch.
    """
    if len(frame_paths) < 2:
        return None

    images = [cv2.imread(str(p), cv2.IMREAD_COLOR) for p in frame_paths]
    if any(im is None for im in images):
        return None

    direction = 1 if (sum(s.dy for s in shifts) >= 0) else -1

    # Normalize so we always treat the run as "scrolling down" (new content at
    # the bottom). For an upward scroll we reverse the frame order and stitch the
    # same way, giving a top-to-bottom image either way.
    if direction < 0:
        images = images[::-1]
        shifts = [ShiftEstimate(-s.dx, -s.dy, s.response) for s in reversed(shifts)]

    canvas = images[0]
    h = canvas.shape[0]
    for k in range(len(shifts)):
        dy = int(round(abs(shifts[k].dy)))
        if dy <= 0:
            continue
        dy = min(dy, h)  # never copy more than a frame's worth
        strip = images[k + 1][h - dy : h, :, :]
        canvas = np.vstack([canvas, strip])
        if canvas.shape[0] >= cfg.stitch_max_height_px:
            break
    return canvas
