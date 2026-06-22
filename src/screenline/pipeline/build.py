"""The build orchestrator — runs the full pipeline over a project.

Flow:
  per recording:  probe -> sample -> embed -> estimate shifts -> segment
  globally:       cluster segments into shared states (dedup)
  per state:      save one representative screenshot (+ stitched scroll image)
  per recording:  classify state-to-state transitions
  finally:        write manifest, timeline.json, summary.csv, processing_report.json

Idempotent-ish: re-running reuses already-extracted frames unless `force=True`.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from screenline.config import Config
from screenline.manifest import (
    Manifest,
    Occurrence,
    SCREENLINE_DIR,
    Screenshot,
    State,
    Transition,
)
from screenline.pipeline import clustering, transitions
from screenline.pipeline.embeddings import get_embedder
from screenline.pipeline.export import write_summary_csv
from screenline.pipeline.scroll import estimate_shift, stitch_vertical
from screenline.pipeline.segmentation import Segment, segment_recording
from screenline.pipeline.timeline import build_timeline
from screenline.pipeline.video import Frame, load_gray, probe, sample_frames
from screenline.utils import now_iso, seconds_to_timecode

Logger = Callable[[str], None]


@dataclass
class _RecResult:
    rec_id: str
    frames: list[Frame]
    segments: list[Segment]


def build(
    project_root: Path,
    manifest: Manifest,
    force: bool = False,
    log: Logger = print,
) -> dict:
    cfg = manifest.config
    started = time.time()
    cache = project_root / SCREENLINE_DIR / "cache"
    embedder = get_embedder(cfg.embedder)
    log(f"Embedder: {embedder.name}")

    warnings: list[str] = []
    rec_results: list[_RecResult] = []

    targets = [r for r in manifest.recordings if force or r.status != "processed"]
    if not targets:
        log("No recordings to process (all up to date). Use --force to rebuild.")
    for rec in targets:
        try:
            res = _process_recording(rec, project_root, cache, cfg, embedder, log)
            rec_results.append(res)
            rec.status = "processed"
            rec.error = None
        except Exception as exc:  # keep going; record the failure
            rec.status = "error"
            rec.error = str(exc)
            warnings.append(f"{rec.filename}: {exc}")
            log(f"  ! error processing {rec.filename}: {exc}")

    # Also reuse previously-processed recordings on incremental builds, so
    # clustering sees the whole project. (Re-segment from cached frames.)
    if not force:
        for rec in manifest.recordings:
            if rec.status == "processed" and rec.id not in {r.rec_id for r in rec_results}:
                try:
                    res = _process_recording(rec, project_root, cache, cfg, embedder, log, reuse=True)
                    rec_results.append(res)
                except Exception as exc:
                    warnings.append(f"re-reading {rec.filename}: {exc}")

    # --- Global clustering: segments -> shared states ---
    flat: list[tuple[str, Segment]] = []
    for res in rec_results:
        for seg in res.segments:
            flat.append((res.rec_id, seg))

    labels = clustering.cluster(
        [seg.centroid for _, seg in flat],
        [seg.is_scroll for _, seg in flat],
        cfg.merge_distance,
    )

    frames_by_rec = {res.rec_id: res.frames for res in rec_results}
    manifest.states = []
    manifest.screenshots = []
    manifest.transitions = []
    _shot_dir(project_root)

    seg_to_state: dict[int, str] = {}  # flat index -> state id
    n_clusters = (max(labels) + 1) if labels else 0
    stitched_count = 0

    for cid in range(n_clusters):
        members = [i for i, lbl in enumerate(labels) if lbl == cid]
        state_id = f"state_{cid + 1:04d}"
        # Canonical occurrence = highest-confidence member.
        canon_i = max(members, key=lambda i: flat[i][1].confidence)
        canon_rec, canon_seg = flat[canon_i]

        rep_path = _save_state_screenshot(
            frames_by_rec[canon_rec][canon_seg.representative_index].path,
            state_id,
            project_root,
        )
        stitched_rel = None
        kind = "screen"
        if canon_seg.is_scroll and canon_seg.scroll_start_index is not None:
            stitched_rel = _save_stitched(
                frames_by_rec[canon_rec], canon_seg, state_id, project_root, cfg, warnings
            )
            if stitched_rel:
                kind = "scroll"
                stitched_count += 1

        occurrences = []
        for i in members:
            rec_id, seg = flat[i]
            rep_ts = frames_by_rec[rec_id][seg.representative_index].timestamp
            occurrences.append(
                Occurrence(
                    recording_id=rec_id,
                    start=round(seg.start_time, 2),
                    end=round(seg.end_time, 2),
                    start_tc=seconds_to_timecode(seg.start_time),
                    end_tc=seconds_to_timecode(seg.end_time),
                    representative_timestamp=round(rep_ts, 2),
                    confidence=round(seg.confidence, 3),
                )
            )
            seg_to_state[i] = state_id
        occurrences.sort(key=lambda o: (o.recording_id, o.start))

        img = cv2.imread(str(project_root / rep_path))
        h, w = (img.shape[0], img.shape[1]) if img is not None else (0, 0)
        manifest.screenshots.append(
            Screenshot(
                id=f"shot_{cid + 1:04d}",
                state_id=state_id,
                path=rep_path,
                type="state",
                recording_id=canon_rec,
                timestamp=round(frames_by_rec[canon_rec][canon_seg.representative_index].timestamp, 2),
                width=w,
                height=h,
            )
        )
        manifest.states.append(
            State(
                id=state_id,
                label=state_id,  # human/LLM labelling is future work
                representative_screenshot=rep_path,
                kind=kind,
                stitched_screenshot=stitched_rel,
                occurrences=occurrences,
            )
        )

    # --- Transitions per recording (state -> state in time order) ---
    flat_by_rec: dict[str, list[int]] = {}
    for i, (rec_id, _seg) in enumerate(flat):
        flat_by_rec.setdefault(rec_id, []).append(i)

    tnum = 0
    for rec_id, idxs in flat_by_rec.items():
        idxs_sorted = sorted(idxs, key=lambda i: flat[i][1].start_time)
        frames = frames_by_rec[rec_id]
        for a, b in zip(idxs_sorted, idxs_sorted[1:]):
            seg_a, seg_b = flat[a][1], flat[b][1]
            from_state, to_state = seg_to_state[a], seg_to_state[b]
            if from_state == to_state:
                continue  # same screen revisited adjacently; not a transition
            kind, conf = _classify_boundary(frames, seg_a, seg_b)
            tnum += 1
            manifest.transitions.append(
                Transition(
                    id=f"trans_{tnum:04d}",
                    recording_id=rec_id,
                    from_state=from_state,
                    to_state=to_state,
                    at=round(seg_b.start_time, 2),
                    at_tc=seconds_to_timecode(seg_b.start_time),
                    kind=kind,
                    confidence=round(conf, 3),
                )
            )

    # --- Derived outputs ---
    timeline = build_timeline(manifest)
    (project_root / SCREENLINE_DIR / "timeline.json").write_text(
        json.dumps(timeline, indent=2), encoding="utf-8"
    )
    write_summary_csv(manifest, project_root)

    total_segments = len(flat)
    report = {
        "generated_at": now_iso(),
        "project": manifest.project,
        "config": cfg.to_dict(),
        "totals": {
            "recordings_processed": len(rec_results),
            "frames_sampled": sum(len(r.frames) for r in rec_results),
            "segments": total_segments,
            "states": len(manifest.states),
            "scroll_states": stitched_count,
            "transitions": len(manifest.transitions),
            "dedup_ratio": round(1 - (len(manifest.states) / total_segments), 3) if total_segments else 0.0,
        },
        "recordings": [
            {
                "id": r.rec_id,
                "frames_sampled": len(r.frames),
                "segments": len(r.segments),
            }
            for r in rec_results
        ],
        "warnings": warnings,
        "elapsed_seconds": round(time.time() - started, 2),
    }
    (project_root / SCREENLINE_DIR / "processing_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    manifest.save(project_root)
    return report


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _process_recording(rec, project_root, cache, cfg, embedder, log, reuse=False) -> _RecResult:
    video_path = _resolve(rec.path, project_root)
    frames_dir = cache / "frames" / rec.id

    if not reuse:
        log(f"Processing {rec.filename} ...")
        rec.metadata = probe(video_path)
        existing = sorted(frames_dir.glob("frame_*.png")) if frames_dir.exists() else []
        if existing:
            frames = [
                Frame(int(p.stem.split("_")[1]), (int(p.stem.split("_")[1]) - 1) / cfg.sample_fps, p)
                for p in existing
            ]
            log(f"  reusing {len(frames)} cached frames")
        else:
            frames = sample_frames(video_path, frames_dir, cfg.sample_fps)
            log(f"  sampled {len(frames)} frames @ {cfg.sample_fps} fps")
    else:
        existing = sorted(frames_dir.glob("frame_*.png"))
        frames = [
            Frame(int(p.stem.split("_")[1]), (int(p.stem.split("_")[1]) - 1) / cfg.sample_fps, p)
            for p in existing
        ]

    if not frames:
        raise RuntimeError("no frames extracted (empty or unreadable video)")

    embeddings = [embedder.embed_path(f.path) for f in frames]
    # shifts[i] is the transition from frames[i] to frames[i+1] (len == n-1).
    shifts = []
    prev_gray = load_gray(frames[0].path)
    for f in frames[1:]:
        cur_gray = load_gray(f.path)
        shifts.append(estimate_shift(prev_gray, cur_gray))
        prev_gray = cur_gray

    segments = segment_recording(frames, embeddings, shifts, cfg)
    if not reuse:
        log(f"  {len(segments)} segment(s)")
    return _RecResult(rec_id=rec.id, frames=frames, segments=segments)


def _classify_boundary(frames, seg_a: Segment, seg_b: Segment):
    a = cv2.imread(str(frames[seg_a.representative_index].path))
    b = cv2.imread(str(frames[seg_b.representative_index].path))
    if a is None or b is None:
        return "unknown", 0.3
    return transitions.classify_transition(a, b)


def _shot_dir(project_root: Path) -> None:
    (project_root / SCREENLINE_DIR / "screenshots").mkdir(parents=True, exist_ok=True)
    (project_root / SCREENLINE_DIR / "stitched").mkdir(parents=True, exist_ok=True)


def _save_state_screenshot(src: Path, state_id: str, project_root: Path) -> str:
    dst = project_root / SCREENLINE_DIR / "screenshots" / f"{state_id}.png"
    img = cv2.imread(str(src))
    if img is None:
        raise IOError(f"could not read representative frame {src}")
    cv2.imwrite(str(dst), img)
    return str(dst.relative_to(project_root))


def _save_stitched(frames, seg: Segment, state_id, project_root, cfg, warnings) -> str | None:
    s, e = seg.scroll_start_index, seg.scroll_end_index
    paths = [frames[k].path for k in range(s, e + 1)]
    # shifts for the run were not retained; recompute on the run only.
    grays = [load_gray(p) for p in paths]
    from screenline.pipeline.scroll import estimate_shift as _es

    run_shifts = [_es(grays[k], grays[k + 1]) for k in range(len(grays) - 1)]
    stitched = stitch_vertical(paths, run_shifts, cfg)
    if stitched is None:
        warnings.append(f"{state_id}: scroll run could not be stitched; kept keyframe")
        return None
    dst = project_root / SCREENLINE_DIR / "stitched" / f"{state_id}.png"
    cv2.imwrite(str(dst), stitched)
    return str(dst.relative_to(project_root))


def _resolve(path_str: str, project_root: Path) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (project_root / p)
