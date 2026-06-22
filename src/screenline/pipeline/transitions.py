"""Transition classification between two consecutive screen states.

Honest scope: ``navigation`` and ``static`` are reliable; ``modal`` and ``tab``
are best-effort heuristics carrying lower confidence (documented as such), and we
fall back to ``unknown`` rather than guessing. Scroll is represented as a *state*
property (``State.kind == 'scroll'``), not as a state-to-state transition, since a
scroll run is collapsed into a single state during segmentation.

The future workflow graph reads `from_state -> to_state` regardless of how good
the `kind` label is, so getting `kind` perfect is not on the MVP critical path.
"""

from __future__ import annotations

import cv2
import numpy as np


def classify_transition(prev_bgr: np.ndarray, next_bgr: np.ndarray) -> tuple[str, float]:
    """Return (kind, confidence) for a state A -> state B boundary."""
    a = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    b = cv2.cvtColor(next_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    if a.shape != b.shape:
        a = cv2.resize(a, (b.shape[1], b.shape[0]))
    h, w = a.shape

    border = _border_similarity(a, b)
    brightness_drop = float(a.mean() - b.mean())

    # Modal: background (border) preserved, screen dims, centre changes.
    if border > 0.85 and brightness_drop > 8.0:
        return "modal", 0.6

    # Tab change: top chrome (header/tab bar) preserved, content area swaps,
    # no global dimming.
    top_sim = _region_similarity(a[: int(h * 0.18)], b[: int(h * 0.18)])
    mid_sim = _region_similarity(a[int(h * 0.25) : int(h * 0.9)], b[int(h * 0.25) : int(h * 0.9)])
    if top_sim > 0.9 and mid_sim < 0.6 and abs(brightness_drop) < 8.0:
        return "tab", 0.5

    return "navigation", 0.7


def _border_similarity(a: np.ndarray, b: np.ndarray, band: float = 0.12) -> float:
    h, w = a.shape
    bh, bw = int(h * band), int(w * band)
    mask = np.ones_like(a, dtype=bool)
    mask[bh : h - bh, bw : w - bw] = False  # interior excluded -> border only
    return _ncc(a[mask], b[mask])


def _region_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return _ncc(a.flatten(), b.flatten())


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    """Normalized cross-correlation in [0, 1] (1 = identical structure)."""
    a = a - a.mean()
    b = b - b.mean()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom < 1e-8:
        return 1.0
    return float(np.clip(np.dot(a, b) / denom, 0.0, 1.0))
