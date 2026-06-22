---
description: Run one Screenline backlog ticket end-to-end (branch → PR → CI → merge → close → sync)
---

Execute a single Screenline ticket using the established per-ticket workflow.
Ticket / area to work: $ARGUMENTS

## Workflow (one branch + PR per ticket; never push to `dev` or `main` directly)

1. **Read the spec first.** Find the ticket in `docs/ROADMAP_BACKLOG.md` (and the
   ADR it cites in `docs/adr/`, plus `CONTEXT.md` for glossary terms). Don't
   spelunk for files already named in the doc. Confirm its **Depends-on** are all
   merged before starting.
2. **Branch off `dev`:** `git checkout dev && git pull --ff-only && git checkout -b <type>/<ticket>`
   (e.g. `quality/p1-1-sticky-footer`, `infra/p0-2-ruff`).
3. **Implement to spec.** Match surrounding code's idioms (see `CLAUDE.md`). Keep
   changes scoped to the ticket; don't fold in unrelated cleanup. Comment the
   *why* for CV heuristics, not the what.
4. **Verify locally before pushing** (CI runs these, but don't outsource your
   confidence to CI):
   ```bash
   .venv/bin/python -m pytest -q
   # if the change affects extraction quality, re-run the example and eyeball it:
   .venv/bin/python examples/generate_sample.py
   (cd examples/sample_project && ../../.venv/bin/screenline build && ../../.venv/bin/screenline list)
   ```
   Regenerate `docs/assets/` previews if the example output materially changed,
   and re-commit the example's `.screenline/` artifacts (cache stays ignored).
5. **Keep docs in lockstep** (standing requirement): update the ticket's
   row/section in `docs/ROADMAP_BACKLOG.md`, plus any ADR / `CONTEXT.md` /
   `README.md` / `CHANGELOG.md` touched — in the SAME branch, so landed work and
   docs never disagree. A new significant decision gets a new ADR (next number).
6. **Commit** (end the message with the Claude Code co-author trailer):
   ```
   Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
   ```
   **Push**, open the PR with `gh pr create --base dev` (PR body ends with the
   Claude Code footer and references the issue, e.g. `Closes #N`).
7. **Watch CI until it settles** (workflow `CI`; jobs are the `test` matrix +
   smoke build):
   ```bash
   until [ "$(gh pr checks <N> --json state --jq '[.[].state] | map(select(. != "SUCCESS" and . != "SKIPPED" and . != "NEUTRAL")) | length')" = "0" ]; do sleep 10; done
   gh pr checks <N>
   ```
8. **Merge + close + sync** — only after CI is green:
   `gh pr merge <N> --squash --delete-branch` →
   `gh issue close <#> --reason completed --comment "..."` (a `dev` merge won't
   auto-close a `Closes #N` because `main` is the default branch — close by hand)
   → `git checkout dev && git fetch origin dev && git pull --ff-only`.

## Promotion to prod (`main`) — separate, deliberate, not per-ticket

When `dev` is good (a batch of tickets landed, CI green), promote:
`git checkout main && git pull --ff-only && gh pr create --base main --head dev`
(or merge `dev → main`), bump the version + `CHANGELOG.md`, tag `vX.Y.Z`, which
triggers the release workflow once P0-4 lands. Never land features straight on
`main`.

## Hard constraints (every session)

- **Branch from `dev`, PR into `dev`.** `main` is prod/release only.
- **Keep core deps light** (numpy, opencv-python-headless, pillow, rich). ffmpeg
  is a *system* dep, probed at runtime. Heavy/ML deps stay behind extras
  (`[clip]`). Don't add a dependency a ticket doesn't require.
- **No DB, web app, plugin framework, or DI.** A project is a folder; the
  manifest is the source of truth (ADR-0001).
- **Tunables live in `config.py`** and are persisted into the manifest — behaviour
  must stay explainable after the fact.
- **Don't commit the frame cache.** `**/.screenline/cache/` is ignored on
  purpose; commit only curated example artifacts.
