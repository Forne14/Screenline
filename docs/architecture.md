# Screenline architecture

Screenline is a **local-first CLI** that turns screen recordings into a curated
set of *screen states*, *transitions* and *stitched scroll captures*. It is a
linear, resumable pipeline operating on a **project** (many recordings), with a
single JSON manifest as the source of truth.

## Core philosophy

Screenline does not think in frames. It thinks in **screen states**: "a screen
that conveys meaningfully different information to a human observer." A new page,
route, modal, report or settings section is a state. A mouse move, hover, focus
ring, spinner, caret blink or toast is **not** — the system is built to be robust
against UI noise.

## Pipeline

```
recordings
   │  ffmpeg probe + sample (default 1 FPS)           pipeline/video.py
   ▼
frames ── visual embedding per frame                  pipeline/embeddings.py
   │  (pluggable: 'default' zero-ML | 'clip')
   ▼
classify each consecutive pair: scroll | cut | static pipeline/segmentation.py
   │      scroll = vertical translation (NCC match)   pipeline/scroll.py
   ▼
segment into screen states (+ noise rejection)        pipeline/segmentation.py
   │      stitch scroll runs into one tall image      pipeline/scroll.py
   ▼
cluster segments across recordings (dedup)            pipeline/clustering.py
   │
   ▼
transitions + timeline + manifest + exports           pipeline/{transitions,timeline,export}.py
```

The orchestrator is `pipeline/build.py`.

## The three hard problems (and our answers)

### 1. Noise-robust segmentation
Pixel diffs over-fire on cursors and spinners; raw semantic embeddings can
*under*-fire (a modal over a page is similar). We decide boundaries on a **fused
signal with temporal hysteresis**:

- Each consecutive frame-pair is classified `scroll` / `cut` / `static`.
- Scroll takes precedence over `cut` (scrolling changes many pixels but is *not*
  a boundary).
- A `cut` only becomes a boundary if it persists; short segments that revert to
  their neighbour (`A → X → A`) are dropped (toasts, spinners, flashes), and
  adjacent near-identical segments are merged.

Knobs: `cut_distance`, `min_state_seconds`, `merge_distance` (see `config.py`).

### 2. Scroll detection & stitching
Scrolling must collapse into **one** state and one tall image.

- **Detection:** estimate the vertical shift between frames by template-matching
  a central horizontal band of frame *N+1* inside frame *N*
  (`cv2.matchTemplate`, normalized cross-correlation). This is far more robust on
  UI content than phase correlation (sharp text, repeated rows, large shifts) and
  yields a clean confidence peak. A run of consistent-direction,
  high-confidence, mostly-vertical shifts — *that also shows real embedding
  change* — is a scroll.
- **Stitching:** "strip append" — start from the first frame, then append only
  the *newly revealed* strip (height = the incremental shift). This sidesteps
  sticky-header ghosting because each strip comes from the leading edge of
  motion.

**Scope:** vertical scroll only. Horizontal / 2-D panoramas are future work; a
sticky *footer* may duplicate into strips; a low-confidence run falls back to a
keyframe. These are documented limitations, not bugs.

### 3. Dependency weight vs. local-first
CLIP/torch is heavy and a frequent install failure. So the embedder is
**pluggable with a zero-ML default**: a normalized 32×32 structural thumbnail +
HSV colour histogram. At that scale a cursor/hover/caret is sub-pixel noise, so
"same page + mouse moved" stays the same vector. `pip install screenline[clip]`
swaps in OpenCLIP for conceptually smarter dedup. Clustering is greedy
agglomeration with a cosine threshold — at MVP scale (tens–hundreds of
*segments*, not frames) this is fast and deterministic; **no FAISS**.

## Why a JSON manifest, not a database

A project is a folder you can read, diff and commit. The manifest
(`screenline.json`) is the contract every other artifact and every future
consumer reads from. See [`manifest.md`](manifest.md).

## Designed-for future (not implemented)

The schema deliberately leaves room:

- `State.occurrences` already models "same screen, many recordings".
- `Transition.from_state` / `to_state` are state ids → one `GROUP BY` from a
  **workflow graph**.
- `Transcript.recording_id` is the hook for future **transcript ↔ state
  alignment**, which feeds the eventual LLM layer (docs, specs, tasks).
- `State.label` defaults to the id today; an LLM/OCR labeller can fill it later.

None of these are built. The MVP optimises only the four things that determine
usefulness: state extraction, cross-recording dedup, scroll detection, scroll
stitching.
