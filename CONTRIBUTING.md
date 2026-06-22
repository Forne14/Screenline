# Contributing to Screenline

Thanks for helping build Screenline! This is a local-first computer-vision CLI;
keep changes small, transparent and well-tested.

## Read first
- [`CONTEXT.md`](CONTEXT.md) — the domain language. Use these exact terms.
- [`docs/architecture.md`](docs/architecture.md) — the pipeline and the hard
  problems.
- [`docs/adr/`](docs/adr) — *why* the non-obvious decisions were made. A new
  significant decision needs a new ADR.
- [`docs/ROADMAP_BACKLOG.md`](docs/ROADMAP_BACKLOG.md) — the prioritised work.

## Branch & release model (staging/prod split)

```
feature branch ──PR──▶ dev (staging) ──PR/promote──▶ main (prod / releases)
```

- **Always branch from `dev`.** Name branches `<type>/<ticket>`, e.g.
  `quality/p1-1-sticky-footer`, `infra/p0-2-ruff`.
- Open PRs **against `dev`**. CI must be green before merge (`--squash
  --delete-branch`).
- `main` is updated only by **promoting `dev`** (a deliberate `dev → main` PR),
  which is where version bumps, `CHANGELOG.md` and `vX.Y.Z` tags happen. Never
  land features directly on `main`.
- Because `main` is the default branch, a `Closes #N` in a `dev`-targeted PR does
  **not** auto-close the issue — close it by hand on merge.

Agents: the `/next-ticket` slash command runs one backlog ticket through this
whole loop.

## Dev setup

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q          # core tests (no video/ffmpeg needed)
```

Requires **ffmpeg** on your `PATH` for actual video processing (not for the unit
tests).

## Before you push
- `pytest -q` is green.
- If you changed extraction quality, re-run the example and eyeball the output:
  ```bash
  python examples/generate_sample.py
  (cd examples/sample_project && screenline build && screenline list)
  ```
- Docs are in lockstep (backlog row, ADR, `CONTEXT.md`, `README.md`,
  `CHANGELOG.md` as applicable).
- Commit messages end with:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```
  (when an AI agent co-authored the change).

## Conventions
- Keep core deps light; heavy/ML deps go behind extras (`[clip]`).
- Tunables live in `config.py` and are persisted into the manifest.
- Comment the *why* of CV heuristics, not the what. Match surrounding style.
- Don't commit the frame cache (`**/.screenline/cache/` is ignored).
