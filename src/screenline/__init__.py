"""Screenline — visual timeline extraction for screen recordings.

Screenline turns screen recordings (demos, design reviews, prototype
walkthroughs) into a structured set of *screen states*, *transitions* and
*stitched scroll captures* that an LLM (or a human) can consume to understand a
product without watching hours of video.

The public surface most callers want is the manifest schema in
:mod:`screenline.manifest` and the build orchestrator in
:mod:`screenline.pipeline.build`.
"""

__version__ = "0.1.0"
SCHEMA_VERSION = "1.0"
