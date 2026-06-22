# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project follows
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-06-22

Initial public release — the MVP visual timeline extraction engine.

### Added
- **Project model**: `init`, `add`, `build`, `status`, `list`, `inspect`,
  `export`, plus single-recording `analyze`.
- **Pipeline** (`ffmpeg` → sample → embed → segment → cluster → transitions →
  outputs).
- **Screen-state extraction** with temporal-hysteresis noise rejection (mouse,
  hover, spinners, toasts do not create states).
- **Cross-recording deduplication** — shared states with per-recording
  occurrences.
- **Scroll detection** via NCC template-matching and **strip-append stitching**
  into tall images.
- **Transition classification** (`navigation`/`static` reliable;
  `modal`/`tab` best-effort; `unknown` fallback).
- **Pluggable embedder**: zero-ML default; optional `clip` extra (OpenCLIP).
- **Transcript ingestion** (associate + register metadata; no alignment yet).
- Canonical **JSON manifest**, `timeline.json`, `processing_report.json`,
  `exports/summary.csv`.
- Documentation: README, architecture, manifest schema, domain glossary, ADRs.
- Synthetic example project + committed example output.
- Test suite for the algorithmic core; GitHub Actions CI.

### Known limitations
- Vertical scroll only; sticky footers may duplicate into stitched strips.
- Fast scrolls at 1 FPS can exceed the registration overlap window — raise
  `--fps` for scroll-heavy content.
- The default embedder dedupes on visual, not conceptual, similarity — use
  `--embedder clip` for "same page, different data".

[0.1.0]: https://github.com/Forne14/Screenline/releases/tag/v0.1.0
