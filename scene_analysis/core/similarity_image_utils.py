from __future__ import annotations

import os


def _imread_bgr(path: str):
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return None
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            data = np.frombuffer(f.read(), dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _center_crop(img_bgr, ratio: float = 0.8):
    if img_bgr is None:
        return None
    h, w = img_bgr.shape[:2]
    if h < 4 or w < 4:
        return img_bgr
    ratio = max(0.3, min(1.0, float(ratio)))
    ch = max(2, int(h * ratio))
    cw = max(2, int(w * ratio))
    y0 = max(0, (h - ch) // 2)
    x0 = max(0, (w - cw) // 2)
    return img_bgr[y0:y0 + ch, x0:x0 + cw]


def _normalize_vec(vec):
    try:
        import numpy as np  # type: ignore
    except Exception:
        return None
    if vec is None:
        return None
    vec = np.asarray(vec, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vec))
    if norm <= 1e-12:
        return None
    return vec / norm


__all__ = ["_imread_bgr", "_center_crop", "_normalize_vec"]
