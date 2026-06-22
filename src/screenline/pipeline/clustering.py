"""Stage 5 — cross-recording state deduplication.

The same screen (e.g. the Dashboard) shows up in many recordings and many times
within one recording. We cluster *segments* (not frames — there are only tens to
low-hundreds of them) by their centroid embedding, so each cluster becomes one
shared :class:`State` with many occurrences.

Greedy single-pass agglomeration with a cosine threshold. At MVP scale this is
fast and deterministic; no FAISS / approximate NN required. Scroll segments are
kept apart from static ones even when visually close, since a stitched page and a
single viewport are different artifacts.
"""

from __future__ import annotations

import numpy as np

from screenline.pipeline.embeddings import cosine_distance


def cluster(centroids: list[np.ndarray], is_scroll: list[bool], merge_distance: float) -> list[int]:
    """Assign each item a cluster id (0-based, in order of first appearance).

    Returns a list `labels` where labels[i] is the cluster index of item i.
    """
    cluster_centroids: list[np.ndarray] = []
    cluster_scroll: list[bool] = []
    labels: list[int] = []

    for i, vec in enumerate(centroids):
        best_idx, best_dist = -1, float("inf")
        for c_idx, c_vec in enumerate(cluster_centroids):
            if cluster_scroll[c_idx] != is_scroll[i]:
                continue  # don't merge a scroll page with a static viewport
            d = cosine_distance(vec, c_vec)
            if d < best_dist:
                best_idx, best_dist = c_idx, d

        if best_idx >= 0 and best_dist <= merge_distance:
            labels.append(best_idx)
            # Running mean keeps the cluster centroid representative as it grows.
            merged = cluster_centroids[best_idx] + vec
            norm = np.linalg.norm(merged)
            cluster_centroids[best_idx] = merged / norm if norm > 1e-8 else merged
        else:
            labels.append(len(cluster_centroids))
            cluster_centroids.append(vec.copy())
            cluster_scroll.append(is_scroll[i])

    return labels
