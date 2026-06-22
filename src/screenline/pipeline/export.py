"""Human- and tool-facing exports derived from the manifest.

MVP export is a single `exports/summary.csv`: one row per shared state with its
label, kind, occurrence count, total on-screen time and screenshot path. It's
the quickest way for a PM/designer to skim what was reviewed, and trivial to load
into a spreadsheet or feed to an LLM.
"""

from __future__ import annotations

import csv
from pathlib import Path

from screenline.manifest import Manifest, SCREENLINE_DIR


def write_summary_csv(manifest: Manifest, project_root: Path) -> Path:
    out_dir = project_root / SCREENLINE_DIR / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "summary.csv"

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "state_id",
                "label",
                "kind",
                "occurrences",
                "recordings",
                "total_seconds",
                "first_seen",
                "screenshot",
            ]
        )
        for state in manifest.states:
            recs = {o.recording_id for o in state.occurrences}
            total = sum(max(o.end - o.start, 0.0) for o in state.occurrences)
            first = min((o.start_tc for o in state.occurrences), default="")
            screenshot = state.stitched_screenshot or state.representative_screenshot
            writer.writerow(
                [
                    state.id,
                    state.label,
                    state.kind,
                    len(state.occurrences),
                    len(recs),
                    round(total, 1),
                    first,
                    screenshot,
                ]
            )
    return path
