from __future__ import annotations

import time
from typing import Any, List, Optional

from .similarity import _siglip2_features_batch, _siglip2_features_from_rgb_tensor_batch


def siglip_feats_from_rgb_auto(worker, frames_rgb, siglip_bundle, return_tensor: bool = True, pre_resize_w: Optional[int] = None):
    worker._raise_if_cancelled()
    frame_n = _frame_count(frames_rgb)
    base_bs, tries = _siglip_batch_try_levels(worker, max(1, frame_n))
    for one_bs in tries:
        worker._raise_if_cancelled()
        out = _siglip2_features_from_rgb_tensor_batch(
            frames_rgb,
            siglip_bundle,
            batch_size=one_bs,
            pre_resize_w=_pre_resize_width(worker, pre_resize_w),
            return_tensor=bool(return_tensor),
        )
        if out is not None:
            _on_siglip_batch_success(worker, base_bs, one_bs)
            return out
    worker._siglip_batch_auto = max(worker._siglip_batch_min, min(worker._siglip_batch_max, tries[-1]))
    return None if bool(return_tensor) else []


def siglip_feats_from_bgr_auto(worker, frames_bgr: List[Any], siglip_bundle):
    worker._raise_if_cancelled()
    if not frames_bgr:
        return []
    base_bs, tries = _siglip_batch_try_levels(worker, len(frames_bgr))
    for one_bs in tries:
        worker._raise_if_cancelled()
        out = _siglip2_features_batch(frames_bgr, siglip_bundle, batch_size=one_bs)
        if _siglip_feature_batch_valid(out):
            _on_siglip_batch_success(worker, base_bs, one_bs)
            return out
    worker._siglip_batch_auto = max(worker._siglip_batch_min, min(worker._siglip_batch_max, tries[-1]))
    return []


def _frame_count(frames_rgb) -> int:
    try:
        return int(getattr(frames_rgb, "shape", [0])[0])
    except Exception:
        try:
            return len(frames_rgb)
        except Exception:
            return 0


def _siglip_batch_try_levels(worker, sample_count: int):
    bs = worker._effective_siglip_batch_size(None, max(1, int(sample_count)))
    levels = [int(x) for x in worker._siglip_batch_levels]
    if bs not in levels:
        bs = min(levels, key=lambda x: abs(int(x) - int(bs)))
    bs_idx = levels.index(int(bs))
    tries = []
    seen = set()
    for one_bs in reversed(levels[:bs_idx + 1]):
        one_bs = max(worker._siglip_batch_min, min(worker._siglip_batch_max, int(one_bs)))
        if one_bs not in seen:
            seen.add(one_bs)
            tries.append(one_bs)
    return int(bs), tries


def _pre_resize_width(worker, pre_resize_w: Optional[int]) -> int:
    return worker.siglip_ffmpeg_scale_w if pre_resize_w is None else max(0, int(pre_resize_w))


def _siglip_feature_batch_valid(out) -> bool:
    if isinstance(out, (list, tuple)):
        return any(v is not None for v in out)
    return bool(out)


def _on_siglip_batch_success(worker, base_bs: int, one_bs: int):
    if int(one_bs) < int(base_bs):
        now = time.time()
        if (now - float(worker._siglip_batch_msg_ts)) >= 1.2:
            worker.message.emit(f"SigLIP2 배치 과부하 감지: {int(base_bs)}→{int(one_bs)} 하향")
            worker._siglip_batch_msg_ts = float(now)
    worker._siglip_batch_auto = int(one_bs)


__all__ = ["siglip_feats_from_bgr_auto", "siglip_feats_from_rgb_auto"]
