from __future__ import annotations

from typing import Any, Optional, Tuple
import os

from .media import SIGLIP_BATCH_DEFAULT, _normalize_siglip_batch_size


DEFAULT_SIGLIP2_MODEL_ID = "google/siglip2-base-patch16-224"
SIGLIP_TORCHCODEC_MAX_SHORT_SIDE = 1080
SIGLIP_DECODE_SCALE_ORIGINAL = -1


def _siglip2_default_model_id() -> str:
    return DEFAULT_SIGLIP2_MODEL_ID


def _video_frame_size(path: str) -> Tuple[int, int]:
    if not path or (not os.path.exists(path)):
        return 0, 0
    try:
        import cv2  # type: ignore
    except Exception:
        return 0, 0
    cap = None
    try:
        cap = cv2.VideoCapture(path)
        if cap is None or (not cap.isOpened()):
            return 0, 0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        return max(0, w), max(0, h)
    except Exception:
        return 0, 0
    finally:
        try:
            if cap is not None:
                cap.release()
        except Exception:
            pass


def _normalize_siglip_decode_scale_w(value: Any, default: int = 0) -> int:
    try:
        n = int(value)
    except Exception:
        n = int(default)
    if n == int(SIGLIP_DECODE_SCALE_ORIGINAL):
        return int(SIGLIP_DECODE_SCALE_ORIGINAL)
    if n <= 0:
        return 0
    return max(224, min(1920, int(n)))


def _siglip_decode_scale_signature(value: Any) -> str:
    n = _normalize_siglip_decode_scale_w(value, default=0)
    if n == int(SIGLIP_DECODE_SCALE_ORIGINAL):
        return "original"
    if n <= 0:
        return f"auto-short{int(SIGLIP_TORCHCODEC_MAX_SHORT_SIDE)}"
    return str(int(n))


def _siglip_decode_scale_label(value: Any, compact: bool = False) -> str:
    n = _normalize_siglip_decode_scale_w(value, default=0)
    if n == int(SIGLIP_DECODE_SCALE_ORIGINAL):
        return "원본"
    if n <= 0:
        return f"자동{int(SIGLIP_TORCHCODEC_MAX_SHORT_SIDE)}↓" if bool(compact) else f"자동({int(SIGLIP_TORCHCODEC_MAX_SHORT_SIDE)}초과다운)"
    return str(int(n))


def _clamp_even_positive_dim(value: int) -> int:
    v = max(2, int(value))
    if (v % 2) != 0 and v > 2:
        v -= 1
    return max(2, int(v))


def _siglip_resize_dims_for_width(path: str, target_width: int) -> Optional[Tuple[int, int]]:
    w, h = _video_frame_size(path)
    if int(w) <= 0 or int(h) <= 0:
        return None
    width_limit = _clamp_even_positive_dim(int(target_width))
    if int(w) <= int(width_limit):
        return None
    scale = float(width_limit) / float(w)
    out_w = _clamp_even_positive_dim(int(round(float(w) * scale)))
    out_h = _clamp_even_positive_dim(int(round(float(h) * scale)))
    if out_w >= int(w) and out_h >= int(h):
        return None
    return int(out_h), int(out_w)


def _siglip_torchcodec_resize_dims(path: str, scale_w: int = 0, max_short_side: int = SIGLIP_TORCHCODEC_MAX_SHORT_SIDE) -> Optional[Tuple[int, int]]:
    norm_scale = _normalize_siglip_decode_scale_w(scale_w, default=0)
    if norm_scale == int(SIGLIP_DECODE_SCALE_ORIGINAL):
        return None
    if norm_scale > 0:
        return _siglip_resize_dims_for_width(path, norm_scale)
    w, h = _video_frame_size(path)
    if int(w) <= 0 or int(h) <= 0:
        return None
    limit = max(2, int(max_short_side))
    short_side = min(int(w), int(h))
    if short_side <= limit:
        return None
    scale = float(limit) / float(short_side)
    out_w = _clamp_even_positive_dim(int(round(float(w) * scale)))
    out_h = _clamp_even_positive_dim(int(round(float(h) * scale)))
    if out_w >= int(w) and out_h >= int(h):
        return None
    return int(out_h), int(out_w)


def _siglip_effective_pre_resize_width(path: str, scale_w: int = 0) -> int:
    norm_scale = _normalize_siglip_decode_scale_w(scale_w, default=0)
    if norm_scale == int(SIGLIP_DECODE_SCALE_ORIGINAL):
        return 0
    if norm_scale > 0:
        return int(norm_scale)
    dims = _siglip_torchcodec_resize_dims(path, 0)
    if dims is None:
        return 0
    return max(0, int(dims[1]))


def _gpu_decode_chunk_batch_limits(path: str) -> Tuple[int, int, str, int, int]:
    w, h = _video_frame_size(path)
    long_side = max(int(w), int(h))
    short_side = min(int(w), int(h))
    tier, limit = _gpu_decode_tier(long_side, short_side)
    limit = int(_normalize_siglip_batch_size(limit, default=SIGLIP_BATCH_DEFAULT))
    return int(limit), int(limit), str(tier), int(w), int(h)


def _cpu_decode_chunk_batch_limits(path: str) -> Tuple[int, int, str, int, int]:
    w, h = _video_frame_size(path)
    long_side = max(int(w), int(h))
    short_side = min(int(w), int(h))
    cores = _cpu_core_count()
    tier, limit = _cpu_decode_tier(long_side, short_side, cores)
    limit = int(_normalize_siglip_batch_size(limit, default=SIGLIP_BATCH_DEFAULT))
    return int(limit), int(limit), str(tier), int(w), int(h)


def _auto_decode_chunk_batch_limits(path: str, prefer_gpu_decode: bool = True) -> Tuple[int, int, str, int, int]:
    if bool(prefer_gpu_decode):
        return _gpu_decode_chunk_batch_limits(path)
    return _cpu_decode_chunk_batch_limits(path)


def _gpu_decode_tier(long_side: int, short_side: int) -> tuple[str, int]:
    if long_side >= 7680 or short_side >= 4320:
        return "8k", 16
    if long_side >= 3840 or short_side >= 2160:
        return "4k", 32
    if long_side >= 2560 or short_side >= 1440:
        return "qhd", 64
    if long_side >= 1920 or short_side >= 1080:
        return "fhd", 160
    if long_side > 0 and short_side > 0:
        return "hd", 192
    return "unknown", 64


def _cpu_decode_tier(long_side: int, short_side: int, cores: int) -> tuple[str, int]:
    if long_side >= 3840 or short_side >= 2160:
        res_tier, res_limit = "4k", 16
    elif long_side >= 2560 or short_side >= 1440:
        res_tier, res_limit = "qhd", 32
    elif long_side >= 1920 or short_side >= 1080:
        res_tier, res_limit = "fhd", 48
    elif long_side > 0 and short_side > 0:
        res_tier, res_limit = "hd", 96
    else:
        res_tier, res_limit = "unknown", 64
    if int(cores) <= 4:
        core_limit = 32
    elif int(cores) <= 8:
        core_limit = 64
    elif int(cores) <= 12:
        core_limit = 96
    else:
        core_limit = 128
    return f"cpu-{int(cores)}c-{res_tier}", min(int(res_limit), int(core_limit))


def _cpu_core_count() -> int:
    try:
        cores = int(os.cpu_count() or 1)
    except Exception:
        cores = 1
    return max(1, int(cores))


def _cpu_auto_worker_count(max_jobs: int, ratio: float = 0.7) -> Tuple[int, int]:
    cores = _cpu_core_count()
    try:
        cap = int(float(cores) * float(ratio))
    except Exception:
        cap = 1
    cap = max(1, int(cap))
    eff = max(1, min(int(max_jobs), int(cap)))
    return int(eff), int(cores)


__all__ = [
    "DEFAULT_SIGLIP2_MODEL_ID",
    "SIGLIP_TORCHCODEC_MAX_SHORT_SIDE",
    "SIGLIP_DECODE_SCALE_ORIGINAL",
    "_siglip2_default_model_id",
    "_video_frame_size",
    "_normalize_siglip_decode_scale_w",
    "_siglip_decode_scale_signature",
    "_siglip_decode_scale_label",
    "_clamp_even_positive_dim",
    "_siglip_resize_dims_for_width",
    "_siglip_torchcodec_resize_dims",
    "_siglip_effective_pre_resize_width",
    "_gpu_decode_chunk_batch_limits",
    "_cpu_decode_chunk_batch_limits",
    "_auto_decode_chunk_batch_limits",
    "_cpu_auto_worker_count",
]
