"""Timeline generation — describe the journey through each recording.

The timeline is a *view* derived from the manifest (the source of truth): for
each recording, the ordered sequence of screen states the viewer moved through,
with timecodes. Written to `.screenline/timeline.json`.
"""

from __future__ import annotations

from screenline.manifest import Manifest
from screenline.utils import seconds_to_timecode


def build_timeline(manifest: Manifest) -> dict:
    states_by_id = {s.id: s for s in manifest.states}
    transitions_by_rec: dict[str, list] = {}
    for t in manifest.transitions:
        transitions_by_rec.setdefault(t.recording_id, []).append(t)

    recordings_out = []
    for rec in manifest.recordings:
        events = []
        # Gather this recording's occurrences across all shared states.
        occ_rows = []
        for state in manifest.states:
            for occ in state.occurrences:
                if occ.recording_id == rec.id:
                    occ_rows.append((occ, state))
        occ_rows.sort(key=lambda r: r[0].start)

        for occ, state in occ_rows:
            events.append(
                {
                    "timestamp": occ.start_tc,
                    "seconds": occ.start,
                    "state_id": state.id,
                    "event": state.label,
                    "kind": state.kind,
                    "confidence": round(occ.confidence, 3),
                }
            )

        recordings_out.append(
            {
                "recording_id": rec.id,
                "filename": rec.filename,
                "duration": rec.metadata.duration,
                "duration_tc": seconds_to_timecode(rec.metadata.duration),
                "events": events,
            }
        )

    return {"project": manifest.project, "recordings": recordings_out}
