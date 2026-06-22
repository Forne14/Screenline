"""Tunable parameters for the Screenline pipeline.

Every knob that affects *what* gets extracted lives here so the behaviour is
transparent and reproducible. The active config is persisted into the manifest
so a build can always be explained ("why did it cut here?") after the fact.

Defaults are tuned for typical 1080p screen recordings sampled at 1 FPS.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Config:
    # --- Stage 2: frame sampling ---
    sample_fps: float = 1.0
    """Frames sampled per second of video. Lower = faster, coarser."""

    # --- Stage 3: embeddings ---
    embedder: str = "default"
    """Embedding backend: 'default' (zero-ML descriptor) or 'clip'."""

    # --- Stage 4/5: state segmentation & clustering ---
    cut_distance: float = 0.18
    """Cosine distance above which a frame is considered a different screen."""

    sustain_frames: int = 2
    """A cut must persist this many sampled frames to become a state boundary.
    Rejects transient toasts / spinners / single-frame glitches (hysteresis)."""

    min_state_seconds: float = 1.5
    """Segments shorter than this that revert to their neighbour are dropped."""

    merge_distance: float = 0.14
    """Cross-recording: segments closer than this cluster into one shared state.
    Slightly tighter than `cut_distance` so dedup is conservative."""

    # --- Critical: scroll detection ---
    scroll_min_shift_px: float = 6.0
    """Minimum vertical pixel shift between frames to count as scrolling."""

    scroll_max_horizontal_px: float = 4.0
    """Above this horizontal shift, motion is not treated as vertical scroll."""

    scroll_min_response: float = 0.5
    """Template-match (NCC) peak confidence required to trust a shift estimate."""

    scroll_min_run: int = 2
    """Minimum consecutive scroll transitions to form a stitchable run."""

    scroll_min_embedding_change: float = 0.05
    """A scroll pair must also show this much embedding change, so a repetitive
    *static* screen (identical rows) can't be mistaken for scrolling."""

    # --- Stitching ---
    stitch_max_height_px: int = 20000
    """Safety cap on a stitched image height (runaway scroll protection)."""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Config":
        if not data:
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
SUPPORTED_TRANSCRIPT_EXTENSIONS = {".txt", ".md", ".json", ".vtt", ".srt"}
