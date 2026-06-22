# CLAUDE.md

Screenline — a local-first CLI that turns screen recordings into a structured
visual timeline (screen states, transitions, stitched scroll captures) for LLMs
and humans. Python, OpenCV, ffmpeg.

## Read these first
- `CONTEXT.md` — the domain language. Use these exact terms in code and docs.
- `docs/architecture.md` — the pipeline and the three hard problems.
- `docs/manifest.md` — the manifest schema (the source of truth).

## Mental model
The pipeline thinks in **screen states**, not frames, and is built to ignore UI
noise (cursor, hover, spinners, toasts). A **project** spans many recordings;
the same screen across recordings is one shared state with many occurrences.
The four things that matter, in order: state extraction, cross-recording dedup,
scroll detection, scroll stitching. Optimise those; don't gold-plate the rest.

## Layout
```
src/screenline/
  cli.py            argparse CLI (init/add/build/status/list/inspect/export/analyze)
  config.py         every tunable knob (persisted into the manifest)
  manifest.py       dataclass schema + JSON load/save (source of truth)
  project.py        init / add operations
  pipeline/
    video.py        ffmpeg probe + frame sampling
    embeddings.py   pluggable embedder (default zero-ML | clip)
    scroll.py       vertical shift estimation + strip-append stitching
    segmentation.py per-recording state detection (noise-robust)
    clustering.py   cross-recording dedup
    transitions.py  transition classification
    timeline.py     derived timeline
    export.py       summary.csv
    build.py        orchestrator
```

## Conventions
- Keep core deps light (numpy, opencv-python-headless, pillow, rich). ffmpeg is a
  **system** dep, probed at runtime. Heavy/ML deps go behind extras (`[clip]`).
- No DB, no web app, no plugin framework, no DI. A project is a folder.
- Tunables live in `config.py` and are written into the manifest — behaviour must
  be explainable after the fact.
- Match the surrounding style; comment the *why* (the CV heuristics), not the what.

## Dev
```bash
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q              # core tests (no video needed)
.venv/bin/python examples/generate_sample.py   # synthetic recordings
cd examples/sample_project && screenline init . && screenline add meeting_01.mp4 && screenline build
```

## Not in scope (designed-for, not built)
Transcript↔state alignment, LLM doc/spec/task generation, workflow graph, TUI,
Linear/Jira. The schema leaves room (see architecture.md); don't implement them
unless asked.
