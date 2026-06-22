# 0001 — A JSON manifest is the source of truth, not a database

- Status: Accepted
- Date: 2026-06-22

## Context

Screenline produces structured knowledge (states, occurrences, transitions,
screenshots) that downstream tools — and eventually an LLM layer — must consume.
We need a canonical store. Options: SQLite, an embedded document DB, or plain
files.

## Decision

The canonical store is a single human-readable JSON file,
`.screenline/screenline.json`, modelled with dataclasses (`manifest.py`). Every
other artifact (`timeline.json`, `exports/`, screenshots) is *derived* from it.

## Consequences

- **Good:** A project is a folder you can read, `git diff`, code-review and
  commit. Zero infrastructure; aligns with "local-first". Trivial for an LLM or a
  future TUI to load. The schema documents itself.
- **Good:** Reproducibility — the active `config` is embedded in the manifest, so
  any result is explainable after the fact.
- **Bad / accepted:** No indexed queries or concurrent writers. At MVP scale
  (tens–hundreds of states) in-memory filtering is plenty. If a project ever
  needs thousands of states with rich queries, this is revisitable — but the
  dataclass schema would map cleanly onto a DB then.

## Alternatives considered

- **SQLite** — better for queries, worse for diff/readability/portability;
  premature for the scale.
- **One file per entity** — more diff-friendly per change, but loses the
  single-contract clarity and complicates atomic writes.
