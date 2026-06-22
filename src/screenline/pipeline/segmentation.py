"""Stage 4 — group a recording's frames into screen states.

This is where noise-robustness lives. We classify each consecutive frame-pair as
``scroll``, ``cut`` or ``static`` (scroll takes precedence — scrolling changes a
lot of pixels but is *not* a boundary), split the recording at cuts, then clean
up:

  1. drop short segments that revert to their neighbour (transient toasts,
     spinners, focus flashes, brief animations);
  2. merge adjacent segments whose representatives are basically the same screen
     (repairs over-splitting from a slow transition).

A scroll run inside a segment is recorded so the build step can stitch it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from screenline.config import Config
from screenline.pipeline.embeddings import cosine_distance
from screenline.pipeline.scroll import ShiftEstimate, find_scroll_runs
from screenline.pipeline.video import Frame


@dataclass
class Segment:
    start_index: int  # inclusive index into the frame list
    end_index: int  # inclusive
    start_time: float
    end_time: float
    representative_index: int
    centroid: np.ndarray
    confidence: float
    is_scroll: bool = False
    scroll_start_index: int | None = None  # frame index range to stitch
    scroll_end_index: int | None = None
    frame_indices: list[int] = field(default_factory=list)


def _scroll_eligible(embeddings, shifts, cfg) -> list[bool]:
    """A pair may be scroll only if it also shows real content change, so a
    repetitive static screen with identical rows isn't read as scrolling."""
    return [
        cosine_distance(embeddings[i], embeddings[i + 1]) >= cfg.scroll_min_embedding_change
        for i in range(len(embeddings) - 1)
    ]


def classify_pairs(
    embeddings: list[np.ndarray],
    scroll_runs: list,
    cfg: Config,
) -> list[str]:
    """Label each consecutive pair: 'scroll' | 'cut' | 'static'."""
    scroll_pairs: set[int] = set()
    for run in scroll_runs:
        scroll_pairs.update(range(run.start_index, run.end_index))

    kinds: list[str] = []
    for i in range(len(embeddings) - 1):
        if i in scroll_pairs:
            kinds.append("scroll")
        elif cosine_distance(embeddings[i], embeddings[i + 1]) > cfg.cut_distance:
            kinds.append("cut")
        else:
            kinds.append("static")
    return kinds


def segment_recording(
    frames: list[Frame],
    embeddings: list[np.ndarray],
    shifts: list[ShiftEstimate | None],
    cfg: Config,
) -> list[Segment]:
    if not frames:
        return []
    if len(frames) == 1:
        return [_make_segment(0, 0, frames, embeddings, cfg)]

    eligible = _scroll_eligible(embeddings, shifts, cfg)
    scroll_runs = find_scroll_runs(shifts, cfg, eligible)
    kinds = classify_pairs(embeddings, scroll_runs, cfg)

    # Split at cuts: a cut between frame i and i+1 ends a segment at i.
    bounds: list[tuple[int, int]] = []
    start = 0
    for i, kind in enumerate(kinds):
        if kind == "cut":
            bounds.append((start, i))
            start = i + 1
    bounds.append((start, len(frames) - 1))

    segments = [_make_segment(s, e, frames, embeddings, cfg) for s, e in bounds]
    segments = _drop_transient(segments, frames, embeddings, cfg)
    segments = _merge_similar_adjacent(segments, frames, embeddings, cfg)
    _annotate_scroll(segments, scroll_runs, cfg)
    return segments


def _make_segment(s: int, e: int, frames, embeddings, cfg) -> Segment:
    idxs = list(range(s, e + 1))
    embs = np.array([embeddings[i] for i in idxs])
    centroid = embs.mean(axis=0)
    norm = np.linalg.norm(centroid)
    if norm > 1e-8:
        centroid = centroid / norm
    # Representative = frame closest to the centroid (most "typical" of the state).
    dists = [cosine_distance(centroid, embeddings[i]) for i in idxs]
    rep_local = int(np.argmin(dists))
    rep_index = idxs[rep_local]
    confidence = float(max(0.0, min(1.0, 1.0 - np.mean(dists))))
    return Segment(
        start_index=s,
        end_index=e,
        start_time=frames[s].timestamp,
        end_time=frames[e].timestamp,
        representative_index=rep_index,
        centroid=centroid,
        confidence=confidence,
        frame_indices=idxs,
    )


def _duration(seg: Segment, frames) -> float:
    # Inclusive of the trailing sample interval so a 1-frame segment isn't 0s.
    if seg.end_index + 1 < len(frames):
        return frames[seg.end_index + 1].timestamp - seg.start_time
    return max(seg.end_time - seg.start_time, frames[-1].timestamp - frames[-2].timestamp if len(frames) > 1 else 1.0)


def _drop_transient(segments: list[Segment], frames, embeddings, cfg) -> list[Segment]:
    """Remove short segments that sit between two similar neighbours (A,X,A)."""
    if len(segments) <= 2:
        return segments
    keep: list[Segment] = [segments[0]]
    for k in range(1, len(segments) - 1):
        seg = segments[k]
        prev, nxt = keep[-1], segments[k + 1]
        short = _duration(seg, frames) < cfg.min_state_seconds
        reverts = cosine_distance(prev.centroid, nxt.centroid) <= cfg.cut_distance
        if short and reverts and not seg.is_scroll:
            continue  # drop: transient toast/spinner/flash
        keep.append(seg)
    keep.append(segments[-1])
    return keep


def _merge_similar_adjacent(segments: list[Segment], frames, embeddings, cfg) -> list[Segment]:
    """Coalesce neighbouring segments that are effectively the same screen."""
    if not segments:
        return segments
    merged: list[Segment] = [segments[0]]
    for seg in segments[1:]:
        prev = merged[-1]
        if cosine_distance(prev.centroid, seg.centroid) <= cfg.merge_distance:
            merged[-1] = _make_segment(
                prev.start_index, seg.end_index, frames, embeddings, cfg
            )
        else:
            merged.append(seg)
    return merged


def _annotate_scroll(segments: list[Segment], scroll_runs, cfg) -> None:
    """Mark segments that contain a scroll run and record its frame range."""
    for seg in segments:
        best = None
        for run in scroll_runs:
            # run covers frames [start_index .. end_index]
            if run.start_index >= seg.start_index and run.end_index <= seg.end_index:
                span = run.end_index - run.start_index
                if best is None or span > (best.end_index - best.start_index):
                    best = run
        if best is not None:
            seg.is_scroll = True
            seg.scroll_start_index = best.start_index
            seg.scroll_end_index = best.end_index
