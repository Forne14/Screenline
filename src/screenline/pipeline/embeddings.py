"""Stage 3 — semantic visual embeddings.

The embedder is pluggable. Two backends:

- ``default`` (zero-ML): a deterministic descriptor built from a normalized
  32x32 structural thumbnail (captures layout) plus an HSV color histogram
  (captures colour scheme / theme). At 32x32 a mouse cursor, hover state, focus
  ring or caret is sub-pixel noise, so "same page + mouse moved" stays the same
  vector. Installs everywhere, fast, debuggable. This is the MVP default.

- ``clip`` (optional, ``pip install screenline[clip]``): OpenCLIP image
  embeddings — conceptually smarter ("same page, different data = same screen"),
  at the cost of a heavy torch install.

All embeddings are L2-normalized so similarity is ``1 - cosine`` and a single
distance threshold applies regardless of backend.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Distance in [0, 2] for L2-normalized vectors (0 = identical)."""
    return float(1.0 - np.dot(a, b))


class DefaultEmbedder:
    """Structural-thumbnail + colour-histogram descriptor. No ML deps."""

    name = "default"

    def __init__(self, thumb: int = 32, struct_weight: float = 1.0, color_weight: float = 0.5):
        self.thumb = thumb
        self.struct_weight = struct_weight
        self.color_weight = color_weight

    def embed_path(self, path: Path) -> np.ndarray:
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            raise IOError(f"Could not read frame: {path}")
        return self.embed(img)

    def embed(self, bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (self.thumb, self.thumb), interpolation=cv2.INTER_AREA)
        struct = small.astype(np.float32).flatten()
        struct = struct - struct.mean()
        struct = _l2(struct) * self.struct_weight

        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [8, 8], [0, 180, 0, 256])
        hist = _l2(hist.flatten().astype(np.float32)) * self.color_weight

        return _l2(np.concatenate([struct, hist]))


class ClipEmbedder:
    """OpenCLIP image embeddings. Lazy-imports torch so the dep stays optional."""

    name = "clip"

    def __init__(self, model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k"):
        try:
            import open_clip  # noqa: F401
            import torch  # noqa: F401
        except ImportError as exc:  # pragma: no cover - exercised only without extra
            raise RuntimeError(
                "The 'clip' embedder requires extra dependencies. "
                "Install with: pip install 'screenline[clip]'"
            ) from exc
        import open_clip
        import torch

        self._torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained
        )
        self.model = self.model.to(self.device).eval()

    def embed_path(self, path: Path) -> np.ndarray:
        from PIL import Image

        img = Image.open(path).convert("RGB")
        return self._embed_pil(img)

    def embed(self, bgr: np.ndarray) -> np.ndarray:
        from PIL import Image

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return self._embed_pil(Image.fromarray(rgb))

    def _embed_pil(self, img) -> np.ndarray:
        torch = self._torch
        tensor = self.preprocess(img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            feats = self.model.encode_image(tensor)
        return _l2(feats.cpu().numpy().astype(np.float32).flatten())


def _l2(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    return v / norm if norm > 1e-8 else v


def get_embedder(name: str):
    if name == "default":
        return DefaultEmbedder()
    if name == "clip":
        return ClipEmbedder()
    raise ValueError(f"Unknown embedder '{name}'. Choose 'default' or 'clip'.")
