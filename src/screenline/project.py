"""High-level project operations backing the CLI verbs.

A project is just a folder with a `.screenline/` directory holding the manifest
and generated artifacts. Recordings and transcripts are *referenced* by path
(relative when inside the project, absolute otherwise) — we never copy multi-GB
video into the project.
"""

from __future__ import annotations

from pathlib import Path

from screenline.config import (
    SUPPORTED_TRANSCRIPT_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
    Config,
)
from screenline.manifest import (
    Manifest,
    Recording,
    SCREENLINE_DIR,
    Transcript,
)
from screenline.utils import now_iso, relpath_if_inside


class ProjectError(RuntimeError):
    pass


def init_project(root: Path, name: str | None = None, config: Config | None = None) -> Manifest:
    root = root.resolve()
    if (root / SCREENLINE_DIR / "screenline.json").exists():
        raise ProjectError(f"A Screenline project already exists at {root}")
    root.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(project=name or root.name, config=config or Config())
    manifest.save(root)
    return manifest


def add_file(root: Path, file_path: Path, recording_for: str | None = None) -> tuple[str, str]:
    """Add a recording or transcript. Returns (kind, id).

    `recording_for` associates a transcript with a recording (id or filename).
    """
    manifest = Manifest.load(root)
    file_path = file_path.expanduser()
    if not file_path.exists():
        raise ProjectError(f"File not found: {file_path}")

    ext = file_path.suffix.lower()
    if ext in SUPPORTED_VIDEO_EXTENSIONS:
        kind, ident = _add_recording(manifest, root, file_path)
    elif ext in SUPPORTED_TRANSCRIPT_EXTENSIONS:
        kind, ident = _add_transcript(manifest, root, file_path, recording_for)
    else:
        raise ProjectError(
            f"Unsupported file type '{ext}'. "
            f"Video: {sorted(SUPPORTED_VIDEO_EXTENSIONS)}; "
            f"Transcript: {sorted(SUPPORTED_TRANSCRIPT_EXTENSIONS)}"
        )
    manifest.save(root)
    return kind, ident


def _add_recording(manifest: Manifest, root: Path, file_path: Path) -> tuple[str, str]:
    if manifest.recording_by_filename(file_path.name):
        raise ProjectError(f"Recording already added: {file_path.name}")
    rid = manifest.next_recording_id()
    manifest.recordings.append(
        Recording(
            id=rid,
            filename=file_path.name,
            path=relpath_if_inside(file_path, root),
            added_at=now_iso(),
        )
    )
    return "recording", rid


def _add_transcript(manifest, root, file_path, recording_for) -> tuple[str, str]:
    rec_id = None
    if recording_for:
        rec = manifest.recording_by_id(recording_for) or manifest.recording_by_filename(recording_for)
        if not rec:
            raise ProjectError(f"No recording matches '{recording_for}' to associate transcript.")
        rec_id = rec.id

    tid = manifest.next_transcript_id()
    manifest.transcripts.append(
        Transcript(
            id=tid,
            filename=file_path.name,
            path=relpath_if_inside(file_path, root),
            format=file_path.suffix.lower().lstrip("."),
            bytes=file_path.stat().st_size,
            recording_id=rec_id,
        )
    )
    if rec_id:
        manifest.recording_by_id(rec_id).transcript_id = tid
    return "transcript", tid
