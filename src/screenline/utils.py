"""Small shared helpers: timecodes, ids, paths."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    """Timezone-aware UTC timestamp, e.g. '2026-06-22T10:30:00Z'."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def seconds_to_timecode(seconds: float) -> str:
    """Format seconds as HH:MM:SS (e.g. 125.0 -> '00:02:05')."""
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def slugify(text: str) -> str:
    """Filesystem- and id-safe slug."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-") or "item"


def short_hash(text: str, length: int = 8) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def relpath_if_inside(path: Path, base: Path) -> str:
    """Return a path relative to `base` when possible, else absolute.

    Keeps a project self-describing when media lives inside it, while still
    supporting recordings referenced from elsewhere on disk.
    """
    path = path.resolve()
    base = base.resolve()
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)
