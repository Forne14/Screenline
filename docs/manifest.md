# The Screenline manifest

`.screenline/screenline.json` is the **canonical source of truth** for a
project. Everything else (`timeline.json`, `exports/`, a future TUI, the future
LLM layer) is derived from it. It is plain JSON — readable, diffable, committable.

Top-level shape:

```jsonc
{
  "project": "my-project",
  "schema_version": "1.0",
  "created_at": "2026-06-22T10:00:00Z",
  "updated_at": "2026-06-22T10:05:00Z",
  "config": { "sample_fps": 1.0, "embedder": "default", "cut_distance": 0.18, ... },
  "recordings":  [ ... ],
  "transcripts": [ ... ],
  "states":      [ ... ],
  "screenshots": [ ... ],
  "transitions": [ ... ]
}
```

### `recordings[]`
A source video, referenced by path (relative when inside the project).

```jsonc
{
  "id": "rec_01",
  "filename": "meeting_01.mp4",
  "path": "meeting_01.mp4",
  "added_at": "2026-06-22T10:00:00Z",
  "status": "processed",                  // added | processed | error
  "metadata": { "duration": 18.0, "fps": 30.0, "width": 1280, "height": 720, "codec": "h264" },
  "transcript_id": "tr_01",
  "error": null
}
```

### `transcripts[]`
Ingested and *associated* only — no transcript intelligence yet (future work).

```jsonc
{ "id": "tr_01", "filename": "transcript.md", "path": "transcript.md",
  "format": "md", "bytes": 64, "recording_id": "rec_01" }
```

### `states[]`
A shared screen state. One representative screenshot, many `occurrences` (the key
to **cross-recording deduplication**).

```jsonc
{
  "id": "state_0001",
  "label": "state_0001",                  // human/LLM label later
  "kind": "screen",                       // screen | scroll
  "representative_screenshot": ".screenline/screenshots/state_0001.png",
  "stitched_screenshot": null,            // set when kind == "scroll"
  "occurrences": [
    { "recording_id": "rec_01", "start": 0.0, "end": 3.0,
      "start_tc": "00:00:00", "end_tc": "00:00:03",
      "representative_timestamp": 0.0, "confidence": 1.0 },
    { "recording_id": "rec_02", "start": 0.0, "end": 2.0, "...": "..." }
  ]
}
```

### `screenshots[]`
One record per saved image (deduped — one per shared state, plus stitched ones).

```jsonc
{ "id": "shot_0001", "state_id": "state_0001",
  "path": ".screenline/screenshots/state_0001.png", "type": "state",
  "recording_id": "rec_01", "timestamp": 0.0, "width": 1280, "height": 720 }
```

### `transitions[]`
State-to-state movement within a recording. `from_state`/`to_state` are state ids
— this list is one `GROUP BY` away from a workflow graph.

```jsonc
{ "id": "trans_0001", "recording_id": "rec_01",
  "from_state": "state_0001", "to_state": "state_0002",
  "at": 4.0, "at_tc": "00:00:04",
  "kind": "navigation",                   // static|scroll|navigation|modal|tab|animation|unknown
  "confidence": 0.7 }
```

> `navigation` and `static` are reliable; `modal`/`tab` are best-effort
> heuristics carrying lower confidence; `unknown` is the honest fallback. Scroll
> is represented as a *state* (`kind: "scroll"`), not a state-to-state
> transition, because a scroll run collapses into a single state.

## Other artifacts

- `timeline.json` — per-recording ordered journey through states (derived).
- `processing_report.json` — counts, dedup ratio, warnings, timing.
- `exports/summary.csv` — one row per state (label, kind, occurrences, time).
- `cache/` — sampled frames; safe to delete, regenerated on build.
