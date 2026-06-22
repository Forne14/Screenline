"""The Screenline processing pipeline.

Stages (each a focused module):
    video        -- Stage 1/2: ffmpeg probe + frame sampling
    embeddings   -- Stage 3: semantic visual embeddings (pluggable backend)
    scroll       -- vertical scroll detection + strip-append stitching
    segmentation -- Stage 4: group frames into per-recording screen states
    clustering   -- Stage 5: cross-recording state deduplication
    transitions  -- transition classification between states
    timeline     -- per-recording timeline generation
    export       -- CSV / human-facing exports
    build        -- the orchestrator that runs the whole thing
"""
