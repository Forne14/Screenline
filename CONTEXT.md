# Screenline domain language

The ubiquitous language of Screenline. When these words appear in code, CLI
output or docs, they mean what is written here. Getting the terms right keeps the
manifest schema, the pipeline and the (future) LLM layer speaking the same
language.

## Project & inputs

**Project**:
The unit of work. A folder with a `.screenline/` directory. A project spans
*many* recordings, sessions and optional transcripts, building one shared
knowledge base. Screenline is project-centric — never designed around a single
video.
_Avoid_: workspace, session (a session is one recording event, not the project)

**Recording**:
One source video added to a project (a demo, review, walkthrough). Referenced by
path; never copied into the project. Has `metadata` (duration/fps/resolution/
codec) and a processing `status`.
_Avoid_: video (informal ok), clip, file

**Transcript**:
An optional text/caption file (`.txt/.md/.json/.vtt/.srt`) attached to a project
and optionally *associated* with a recording. **Ingested only** in the MVP — its
content is not yet aligned to states. The association is the hook for future
work.
_Avoid_: notes, captions (those are formats, not the concept)

## The visual model

**Frame**:
A single sampled still (default 1 per second). An *internal* unit — Screenline
deliberately does **not** think in frames. Frames live in `cache/` and are
disposable.
_Avoid_: screenshot (a screenshot is a curated output, not a raw frame)

**Screen state** (or **state**):
*A screen that conveys meaningfully different information to a human observer.* A
new page, route, dashboard, modal, report or settings section is a state. A
mouse move, hover, focus ring, spinner, caret blink or toast is **not**. A state
is *shared*: the same Dashboard seen in three recordings is **one** state with
three occurrences.
_Avoid_: frame, scene, page (a state may be finer or coarser than a page)

**Occurrence**:
One appearance of a shared state inside one recording, with start/end timecodes,
a representative timestamp and a confidence. Deduplication keeps one state
definition but every occurrence.
_Avoid_: instance, hit

**Transition**:
Movement from one state to another within a recording, classified as
`static | scroll | navigation | modal | tab | animation | unknown`. The list of
transitions is the seed of a future workflow graph.
_Avoid_: edge (that's the future-graph term), change

## Scroll

**Scroll**:
The same logical page revealing more of itself by vertical movement. Scroll is
**not** navigation and **not** a new state — it collapses into a single state
whose `kind` is `scroll`.
_Avoid_: pan, swipe

**Scroll run**:
A maximal sequence of consecutive frames detected as scrolling in a consistent
direction. The unit that gets stitched.

**Stitched capture** (or **stitched screenshot**):
The single tall image produced from a scroll run — the highest-quality long
image of the whole page. Stored under `stitched/`.
_Avoid_: panorama (reserved for the future 2-D case), long screenshot

## Outputs

**Manifest**:
`.screenline/screenline.json` — the canonical source of truth. Every other
artifact is *derived* from it.
_Avoid_: database, index, config (the config is a *field inside* the manifest)

**Timeline**:
A derived per-recording view: the ordered journey through states with timecodes.
A view, never a source of truth.

**Screenshot**:
A curated representative image of a state (deduped — one per shared state, plus
stitched ones). Distinct from a raw *frame*.

## Backends

**Embedder**:
The pluggable component that turns a frame into a vector for similarity.
`default` = zero-ML structural-thumbnail + colour-histogram descriptor; `clip` =
optional OpenCLIP (heavier, semantically smarter).
_Avoid_: model, encoder (informal ok)
