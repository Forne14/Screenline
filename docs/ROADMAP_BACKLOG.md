# Screenline — Roadmap & Issue Backlog

Derived from the MVP (`0.1.0`), the ADRs in [`docs/adr/`](adr), and the README
roadmap. Each issue is a self-contained unit of work an agent or contributor can
execute end-to-end. Mirrored as GitHub issues (see the labels `phase:*`,
`type:*`).

> **The MVP has not yet been validated on real recordings.** `P0-1` (dogfood
> pass) comes first and may re-prioritise everything below.

## How to use this backlog

1. Pick an issue whose **Depends-on** are all done.
2. **Read the referenced ADR** (`docs/adr/`) before touching code — it carries
   the *why*. Use [`CONTEXT.md`](../CONTEXT.md) for domain terms.
3. Implement **Scope**, satisfy **every Acceptance criterion**, respect
   **Out-of-scope**.
4. **Keep docs in lockstep**: update this backlog row + any ADR/`CONTEXT.md` in
   the same branch, so landed work and docs never disagree. New significant
   decisions get a new ADR.
5. One branch + PR per issue, off `dev` (see the workflow in `CONTRIBUTING.md`
   and `/next-ticket`).

## Branch & release model

`feature branch → PR → dev (staging) → PR → main (prod/release)`. We always
branch from `dev`; `main` is only updated by promoting `dev`. See
`CONTRIBUTING.md`.

## Dependency-ordered index

| ID | Title | Phase | Depends on | Type | ADR |
|----|-------|-------|------------|------|-----|
| P0-1 | Dogfood pass on real recordings + tune defaults | P0 | — | quality | 0006 |
| P0-2 | `ruff` lint + format + pre-commit | P0 | — | infra | — |
| P0-3 | `screenline doctor` (env/ffmpeg preflight) | P0 | — | dx | — |
| P0-4 | Release workflow (tag → GitHub Release → PyPI) | P0 | P0-2 | infra | — |
| P0-5 | Expand test coverage (segmentation/transitions/clustering) | P0 | — | infra | 0006 |
| P0-6 | Progress reporting for long videos | P0 | — | dx | — |
| P1-1 | Fix sticky-footer duplication in stitching | P1 | P0-1 | quality | 0004 |
| P1-2 | Robust fast-scroll: multi-scale / adaptive sampling | P1 | P0-1 | quality | 0003 |
| P1-3 | Embedding + shift cache for resumable builds | P1 | — | quality | 0001 |
| P1-4 | Validate/upgrade modal & tab transition classification | P1 | P0-1,P0-5 | quality | — |
| P1-5 | CLIP backend evaluation harness + benchmark | P1 | P0-1 | quality | 0002 |
| P1-6 | Confidence calibration for occurrences & transitions | P1 | P0-5 | quality | 0006 |
| P2-1 | Config file support (`screenline.toml`) | P2 | — | dx | 0001 |
| P2-2 | JSON Schema for the manifest + `validate` command | P2 | — | dx | 0001 |
| P2-3 | HTML report export (state gallery + timeline) | P2 | — | dx | 0001 |
| P2-4 | `export --graph` mermaid/DOT workflow graph | P2 | — | dx | 0005 |
| P3-1 | OCR/LLM-assisted state labels | P3 | P1-5 | feature | 0001 |
| P3-2 | Transcript ↔ screen-state alignment | P3 | — | feature | 0001 |
| P3-3 | LLM analysis layer (docs/specs/tasks from manifest) | P3 | P3-2 | feature | — |
| P3-4 | Workflow graph viewer | P3 | P2-4 | feature | 0005 |
| P3-5 | TUI (project / timeline / screenshot explorer) | P3 | P2-3 | feature | — |
| P3-6 | Linear / Jira export | P3 | P3-3 | feature | — |
| P3-7 | Horizontal & 2-D panorama stitching | P3 | P1-1 | feature | 0004 |

---

## P0 — Foundation & validation

### P0-1 — Dogfood pass on real recordings + tune defaults
- **Type:** quality · **ADR:** 0006
- **Scope:** Run Screenline on a handful of real recordings (a demo, a docs
  scroll, a design review). Record results vs the README quality targets (10–30
  screenshots / 20 min, <5% dupes, 0 from mouse). Tune `cut_distance`,
  `merge_distance`, `min_state_seconds`, scroll thresholds; capture findings.
- **Acceptance:** A short `docs/eval/` report with inputs, outputs, metrics and
  any default changes. At least one regression fixture added to `tests/`.
- **Out-of-scope:** Algorithm rewrites (file follow-up issues instead).

### P0-2 — `ruff` lint + format + pre-commit
- **Type:** infra
- **Scope:** Add `ruff` (lint + format) config to `pyproject.toml`, a
  `.pre-commit-config.yaml`, and a `lint` job in CI.
- **Acceptance:** `ruff check` and `ruff format --check` pass in CI on `dev`/PRs;
  pre-commit documented in `CONTRIBUTING.md`.
- **Out-of-scope:** Type-checking (could be a follow-up with mypy).

### P0-3 — `screenline doctor`
- **Type:** dx
- **Scope:** A `doctor` command that checks Python version, ffmpeg/ffprobe
  presence + version, optional `clip` extra availability, and writability of the
  project dir; prints actionable fixes.
- **Acceptance:** Exits non-zero with a clear message when ffmpeg is missing;
  green summary when all good. Covered by a test (mocked).

### P0-4 — Release workflow (tag → GitHub Release → PyPI)
- **Type:** infra · **Depends-on:** P0-2
- **Scope:** A `release.yml` triggered on `v*` tags that builds the wheel/sdist,
  creates a GitHub Release from `CHANGELOG.md`, and publishes to PyPI (trusted
  publishing). Document the cut process.
- **Acceptance:** Tagging `v0.1.1` on `main` produces a release + PyPI artifact
  (or a dry-run to TestPyPI until ready).
- **Out-of-scope:** Conda packaging.

### P0-5 — Expand test coverage
- **Type:** infra · **ADR:** 0006
- **Scope:** Add tests for segmentation edge cases (hysteresis boundaries,
  scroll-into-cut), transition classification heuristics, clustering order
  sensitivity, and timeline derivation.
- **Acceptance:** Coverage on `pipeline/` meaningfully up; CI green.

### P0-6 — Progress reporting for long videos
- **Type:** dx
- **Scope:** `rich.progress` bars for sampling/embedding/segmentation so a
  2-hour recording shows live progress; respect `--quiet`.
- **Acceptance:** Progress visible on a multi-minute build; no change to
  non-TTY/log output beyond current behaviour.

## P1 — Core quality (the four things that matter)

### P1-1 — Fix sticky-footer duplication in stitching
- **Type:** quality · **ADR:** 0004
- **Scope:** Detect a static bottom band across a scroll run (a sticky footer)
  and exclude it from appended strips, so it isn't repeated down the stitched
  image.
- **Acceptance:** A fixture with a sticky footer stitches without repetition;
  existing sticky-header behaviour unchanged. Update ADR-0004 consequences.

### P1-2 — Robust fast-scroll
- **Type:** quality · **ADR:** 0003
- **Scope:** Handle scrolls whose per-frame shift exceeds the overlap window at 1
  FPS — e.g. detect "scroll-like but unmatched" regions and locally re-sample at
  higher FPS, or multi-scale template search.
- **Acceptance:** A fast-scroll fixture (currently missed) is detected and
  stitched; documented in ADR-0003.

### P1-3 — Embedding + shift cache
- **Type:** quality · **ADR:** 0001
- **Scope:** Cache per-frame embeddings and pairwise shifts under
  `.screenline/cache/` keyed by recording id + sample_fps + embedder, so
  incremental builds and `reuse` don't recompute.
- **Acceptance:** Second `build` of an unchanged project is markedly faster;
  cache invalidates on config change.

### P1-4 — Validate/upgrade modal & tab classification
- **Type:** quality · **Depends-on:** P0-1, P0-5
- **Scope:** Build fixtures with real modals/tab switches; measure the current
  heuristics' precision; improve or down-rank confidence accordingly.
- **Acceptance:** Documented precision per `kind`; no confident-but-wrong labels
  on the fixtures.

### P1-5 — CLIP backend evaluation harness
- **Type:** quality · **ADR:** 0002
- **Scope:** A reproducible benchmark comparing `default` vs `clip` on labelled
  fixtures (dedup precision/recall, "same page different data"). Document when to
  use which.
- **Acceptance:** A `docs/eval/embedders.md` with numbers; CI optionally runs the
  default-only subset.

### P1-6 — Confidence calibration
- **Type:** quality · **ADR:** 0006
- **Scope:** Make occurrence/transition confidence meaningful (e.g. map to
  observed correctness on fixtures) instead of ad-hoc distances.
- **Acceptance:** Confidence correlates with correctness on the fixture set;
  documented.

## P2 — Outputs & DX

### P2-1 — Config file support (`screenline.toml`)
- **Type:** dx · **ADR:** 0001
- **Scope:** Load defaults from a project `screenline.toml` (CLI flags override);
  `init` can scaffold it. Still persisted into the manifest.
- **Acceptance:** A project builds with no flags using its toml; precedence
  documented.

### P2-2 — Manifest JSON Schema + `validate`
- **Type:** dx · **ADR:** 0001
- **Scope:** Publish a JSON Schema for `screenline.json`; add `screenline
  validate` to check a manifest against it.
- **Acceptance:** Schema in `docs/`, `validate` passes on example output and
  fails on a corrupted manifest.

### P2-3 — HTML report export
- **Type:** dx · **ADR:** 0001
- **Scope:** `export --html` producing a self-contained gallery: states (with
  screenshots/stitched), per-recording timeline, transitions.
- **Acceptance:** Opening the HTML shows the example project's states and
  timeline with no server.
- **Out-of-scope:** Interactive editing (that's the TUI/viewer).

### P2-4 — `export --graph`
- **Type:** dx · **ADR:** 0005
- **Scope:** Emit the transition graph as mermaid and/or DOT from the manifest.
- **Acceptance:** Generated mermaid renders the example's Dashboard→…→Reports
  flow; matches `transitions`.

## P3 — Future features (designed-for)

### P3-1 — OCR/LLM-assisted state labels
- **Type:** feature · **Depends-on:** P1-5 · **ADR:** 0001
- **Scope:** Replace `label == id` with a human-readable label derived from
  on-screen text (OCR) or an LLM caption; keep it optional/offline-friendly.
- **Acceptance:** States get sensible labels ("Dashboard", "Billing"); manifest
  schema unchanged (label field already exists).

### P3-2 — Transcript ↔ screen-state alignment
- **Type:** feature · **ADR:** 0001
- **Scope:** Align transcript segments (timestamps) to state occurrences; store
  the linkage in the manifest (the `recording_id` hook already exists).
- **Acceptance:** For a recording+transcript, each state lists the spoken text
  during its occurrences.
- **Out-of-scope:** Summarisation (that's P3-3).

### P3-3 — LLM analysis layer
- **Type:** feature · **Depends-on:** P3-2
- **Scope:** Consume the manifest (+aligned transcript) to generate
  documentation/specs/tasks via a pluggable LLM provider; keep Screenline's core
  provider-agnostic.
- **Acceptance:** From the example project, generate a markdown product overview
  grounded in states + (optional) transcript.

### P3-4 — Workflow graph viewer
- **Type:** feature · **Depends-on:** P2-4 · **ADR:** 0005
- **Scope:** Interactive view of the state graph (states as nodes with
  thumbnails, transitions as edges).
- **Acceptance:** Navigate the example's graph; click a node → screenshot.

### P3-5 — TUI
- **Type:** feature · **Depends-on:** P2-3
- **Scope:** Terminal UI: project browser, timeline viewer, screenshot/state
  explorer, build progress. Architecture already manifest-driven.
- **Acceptance:** Browse a built project without leaving the terminal.

### P3-6 — Linear / Jira export
- **Type:** feature · **Depends-on:** P3-3
- **Scope:** Turn LLM-generated tasks into Linear/Jira issues via their APIs.
- **Acceptance:** Dry-run prints issues; real run creates them with auth.

### P3-7 — Horizontal & 2-D panorama stitching
- **Type:** feature · **Depends-on:** P1-1 · **ADR:** 0004
- **Scope:** Extend stitching beyond vertical scroll to horizontal and 2-D
  panning (e.g. large canvases / design boards).
- **Acceptance:** A horizontally-scrolled fixture stitches correctly; vertical
  path unchanged.
