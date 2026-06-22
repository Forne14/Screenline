"""The Screenline manifest — the canonical source of truth for a project.

Everything downstream (timeline, exports, a future TUI, the future LLM layer)
reads from :class:`Manifest`. The schema is deliberately explicit and
JSON-serializable; we use dataclasses rather than a DB so a project is a folder
you can read, diff and commit.

Design notes for the *future*:
- `State.occurrences` already models "the same screen seen in many recordings".
- `Transition.from_state` / `to_state` are state ids, so the transition list is
  one `GROUP BY` away from a workflow graph (Dashboard -> Users -> Edit User).
- `Transcript.recording_id` is the hook for future transcript↔state alignment.
None of those future features are implemented; the schema just leaves room.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from screenline import SCHEMA_VERSION
from screenline.config import Config
from screenline.utils import now_iso

MANIFEST_NAME = "screenline.json"
SCREENLINE_DIR = ".screenline"


@dataclass
class VideoMetadata:
    duration: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    codec: str = ""


@dataclass
class Recording:
    id: str
    filename: str
    path: str  # relative to project root when inside it, else absolute
    added_at: str
    status: str = "added"  # added | processed | error
    metadata: VideoMetadata = field(default_factory=VideoMetadata)
    transcript_id: str | None = None
    error: str | None = None


@dataclass
class Transcript:
    id: str
    filename: str
    path: str
    format: str  # txt | md | json | vtt | srt
    bytes: int = 0
    recording_id: str | None = None  # association hook for future alignment


@dataclass
class Occurrence:
    """One appearance of a shared state, inside one recording."""

    recording_id: str
    start: float
    end: float
    start_tc: str
    end_tc: str
    representative_timestamp: float
    confidence: float = 1.0


@dataclass
class State:
    """A screen that conveys meaningfully different information to a viewer.

    A state is *shared* across recordings: its `occurrences` list every time the
    screen was seen, but a single representative screenshot is kept.
    """

    id: str
    label: str  # human/LLM label later; defaults to the id for now
    representative_screenshot: str  # path relative to project root
    kind: str = "screen"  # screen | scroll
    stitched_screenshot: str | None = None  # set for scroll states
    occurrences: list[Occurrence] = field(default_factory=list)


@dataclass
class Screenshot:
    id: str
    state_id: str
    path: str
    type: str  # state | stitched
    recording_id: str
    timestamp: float
    width: int = 0
    height: int = 0


@dataclass
class Transition:
    id: str
    recording_id: str
    from_state: str | None
    to_state: str | None
    at: float
    at_tc: str
    kind: str  # static | scroll | navigation | modal | tab | animation | unknown
    confidence: float = 1.0


@dataclass
class Manifest:
    project: str
    schema_version: str = SCHEMA_VERSION
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    config: Config = field(default_factory=Config)
    recordings: list[Recording] = field(default_factory=list)
    transcripts: list[Transcript] = field(default_factory=list)
    states: list[State] = field(default_factory=list)
    screenshots: list[Screenshot] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)

    # ----- lookups -----
    def recording_by_id(self, rid: str) -> Recording | None:
        return next((r for r in self.recordings if r.id == rid), None)

    def recording_by_filename(self, name: str) -> Recording | None:
        return next((r for r in self.recordings if r.filename == name), None)

    def next_recording_id(self) -> str:
        return f"rec_{len(self.recordings) + 1:02d}"

    def next_transcript_id(self) -> str:
        return f"tr_{len(self.transcripts) + 1:02d}"

    # ----- serialization -----
    def to_dict(self) -> dict:
        d = asdict(self)
        d["config"] = self.config.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        m = cls(project=data["project"])
        m.schema_version = data.get("schema_version", SCHEMA_VERSION)
        m.created_at = data.get("created_at", m.created_at)
        m.updated_at = data.get("updated_at", m.updated_at)
        m.config = Config.from_dict(data.get("config"))
        m.recordings = [_recording_from_dict(r) for r in data.get("recordings", [])]
        m.transcripts = [Transcript(**t) for t in data.get("transcripts", [])]
        m.states = [_state_from_dict(s) for s in data.get("states", [])]
        m.screenshots = [Screenshot(**s) for s in data.get("screenshots", [])]
        m.transitions = [Transition(**t) for t in data.get("transitions", [])]
        return m

    def save(self, project_root: Path) -> Path:
        self.updated_at = now_iso()
        path = project_root / SCREENLINE_DIR / MANIFEST_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, project_root: Path) -> "Manifest":
        path = project_root / SCREENLINE_DIR / MANIFEST_NAME
        if not path.exists():
            raise FileNotFoundError(
                f"No Screenline project found at {project_root} "
                f"(missing {SCREENLINE_DIR}/{MANIFEST_NAME}). Run `screenline init` first."
            )
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _recording_from_dict(d: dict) -> Recording:
    d = dict(d)
    d["metadata"] = VideoMetadata(**d.get("metadata", {}))
    return Recording(**d)


def _state_from_dict(d: dict) -> State:
    d = dict(d)
    d["occurrences"] = [Occurrence(**o) for o in d.get("occurrences", [])]
    return State(**d)


def find_project_root(start: Path) -> Path | None:
    """Walk up from `start` looking for a `.screenline/` directory."""
    start = start.resolve()
    for candidate in [start, *start.parents]:
        if (candidate / SCREENLINE_DIR / MANIFEST_NAME).exists():
            return candidate
    return None
