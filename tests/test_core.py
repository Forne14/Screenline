"""Unit tests for the algorithmic core (no video / ffmpeg required).

These cover the parts that determine output quality and are easy to get subtly
wrong: clustering, scroll-run detection, segmentation noise-rejection, the
vertical stitcher, and manifest round-tripping.
"""

from __future__ import annotations

import numpy as np

from screenline.config import Config
from screenline.manifest import Manifest, Occurrence, State
from screenline.pipeline import clustering
from screenline.pipeline.scroll import (
    ShiftEstimate,
    estimate_shift,
    find_scroll_runs,
    stitch_vertical,
)
from screenline.pipeline.segmentation import segment_recording
from screenline.pipeline.video import Frame
from screenline.utils import seconds_to_timecode, slugify


def _vec(*xs) -> np.ndarray:
    v = np.array(xs, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n else v


# --------------------------------------------------------------------------- #
def test_timecode_and_slug():
    assert seconds_to_timecode(0) == "00:00:00"
    assert seconds_to_timecode(125) == "00:02:05"
    assert seconds_to_timecode(3661) == "01:01:01"
    assert slugify("User Detail / Edit!") == "user-detail-edit"


def test_clustering_dedupes_same_screen_across_recordings():
    a1, a2 = _vec(1, 0, 0), _vec(0.99, 0.01, 0)  # "dashboard" twice
    b = _vec(0, 1, 0)  # "settings"
    labels = clustering.cluster([a1, b, a2], [False, False, False], merge_distance=0.1)
    assert labels[0] == labels[2]  # the two dashboards merge
    assert labels[1] != labels[0]  # settings stays separate


def test_clustering_keeps_scroll_and_static_apart():
    v = _vec(1, 0)
    labels = clustering.cluster([v, v], [False, True], merge_distance=0.5)
    assert labels[0] != labels[1]  # identical vectors, but scroll vs static


def test_find_scroll_runs_requires_consistent_direction_and_length():
    cfg = Config()
    down = ShiftEstimate(dx=0, dy=120, response=0.9)
    up = ShiftEstimate(dx=0, dy=-120, response=0.9)
    flat = ShiftEstimate(dx=0, dy=0, response=0.99)
    runs = find_scroll_runs([down, down, down, flat, up], cfg)
    assert len(runs) == 1
    assert (runs[0].start_index, runs[0].end_index, runs[0].direction) == (0, 3, 1)


def test_segmentation_rejects_transient_noise_and_merges_repeats():
    # A A A  X(blip)  A A A   -> one state (the blip is dropped, repeats merge)
    cfg = Config(min_state_seconds=1.5)
    A, X = _vec(1, 0, 0), _vec(0, 1, 0)
    embs = [A, A, A, X, A, A, A]
    frames = [Frame(i + 1, float(i), None) for i in range(len(embs))]  # 1s apart
    shifts = [ShiftEstimate(0, 0, 0.99)] * (len(embs) - 1)
    segs = segment_recording(frames, embs, shifts, cfg)
    assert len(segs) == 1


def test_segmentation_splits_distinct_screens():
    cfg = Config()
    A, B = _vec(1, 0, 0), _vec(0, 1, 0)
    embs = [A, A, B, B]
    frames = [Frame(i + 1, float(i), None) for i in range(len(embs))]
    shifts = [ShiftEstimate(0, 0, 0.99)] * (len(embs) - 1)
    segs = segment_recording(frames, embs, shifts, cfg)
    assert len(segs) == 2


def test_estimate_shift_recovers_known_scroll():
    rng = np.random.default_rng(0)
    page = rng.integers(0, 255, size=(900, 400), dtype=np.uint8)
    a = page[100:400, :]
    b = page[160:460, :]  # scrolled down by 60px
    est = estimate_shift(a, b)
    assert abs(est.dy - 60) <= 2
    assert est.response > 0.8


def test_stitch_vertical_produces_taller_image():
    rng = np.random.default_rng(1)
    page = rng.integers(0, 255, size=(600, 200, 3), dtype=np.uint8)
    f0, f1, f2 = page[0:300], page[100:400], page[200:500]

    # Use real temp files so cv2 can read them.
    import tempfile
    import cv2
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        paths = []
        for i, fr in enumerate((f0, f1, f2)):
            p = Path(d) / f"{i}.png"
            cv2.imwrite(str(p), fr)
            paths.append(p)
        shifts = [ShiftEstimate(0, 100, 0.99), ShiftEstimate(0, 100, 0.99)]
        out = stitch_vertical(paths, shifts, Config())
    assert out is not None
    assert out.shape[0] > 300  # taller than a single frame


def test_manifest_roundtrip(tmp_path):
    m = Manifest(project="demo")
    m.states.append(
        State(
            id="state_0001",
            label="state_0001",
            representative_screenshot="screenshots/state_0001.png",
            occurrences=[
                Occurrence("rec_01", 0.0, 3.0, "00:00:00", "00:00:03", 1.0, 0.9)
            ],
        )
    )
    m.save(tmp_path)
    loaded = Manifest.load(tmp_path)
    assert loaded.project == "demo"
    assert loaded.states[0].occurrences[0].recording_id == "rec_01"
    assert loaded.config.sample_fps == m.config.sample_fps
