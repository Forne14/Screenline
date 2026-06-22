"""Stage 1 & 2 — video normalization and frame sampling, via ffmpeg.

We don't decode video in Python. ffmpeg/ffprobe are far faster and handle every
container/codec we care about. We probe metadata with ffprobe, then sample
frames at a fixed rate with ffmpeg, naming each frame by its index so the
timestamp is recoverable (timestamp = index / sample_fps).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from screenline.manifest import VideoMetadata


class FFmpegNotFound(RuntimeError):
    pass


def ensure_ffmpeg() -> None:
    """Fail early with a helpful message if ffmpeg/ffprobe are missing."""
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        raise FFmpegNotFound(
            f"Required system tool(s) not found on PATH: {', '.join(missing)}. "
            "Install ffmpeg (e.g. `brew install ffmpeg` or `apt install ffmpeg`)."
        )


def probe(video_path: Path) -> VideoMetadata:
    """Read duration/fps/resolution/codec with ffprobe."""
    ensure_ffmpeg()
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,codec_name:format=duration",
        "-of", "json", str(video_path),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}

    return VideoMetadata(
        duration=float(fmt.get("duration", 0.0) or 0.0),
        fps=_parse_fraction(stream.get("r_frame_rate", "0/1")),
        width=int(stream.get("width", 0) or 0),
        height=int(stream.get("height", 0) or 0),
        codec=str(stream.get("codec_name", "") or ""),
    )


def _parse_fraction(frac: str) -> float:
    try:
        num, den = frac.split("/")
        den_f = float(den)
        return round(float(num) / den_f, 3) if den_f else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


@dataclass
class Frame:
    index: int
    timestamp: float  # seconds into the recording
    path: Path


def sample_frames(video_path: Path, out_dir: Path, sample_fps: float) -> list[Frame]:
    """Extract frames at `sample_fps` into `out_dir`, returning Frame records.

    Frames are written as zero-padded PNGs (frame_000001.png ...). The 1-based
    ffmpeg index maps to a timestamp of (index - 1) / sample_fps.
    """
    ensure_ffmpeg()
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("frame_*.png"):
        stale.unlink()

    pattern = str(out_dir / "frame_%06d.png")
    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-i", str(video_path),
        "-vf", f"fps={sample_fps}",
        pattern,
    ]
    subprocess.run(cmd, check=True)

    frames: list[Frame] = []
    for path in sorted(out_dir.glob("frame_*.png")):
        idx = int(path.stem.split("_")[1])
        frames.append(Frame(index=idx, timestamp=(idx - 1) / sample_fps, path=path))
    return frames


def load_gray(path: Path) -> np.ndarray:
    """Load a frame as grayscale (for motion/scroll estimation)."""
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise IOError(f"Could not read frame: {path}")
    return img
