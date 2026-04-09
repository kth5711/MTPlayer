from __future__ import annotations

from typing import Any, Dict, List
import os


def _open_decord_video(path: str, prefer_gpu: bool = False, width: int = 0, height: int = 0, allow_cpu_fallback: bool = True):
    decord = _import_decord()
    if decord is None:
        return None, 0.0, "decord-unavailable"
    if not path or not os.path.exists(path):
        return None, 0.0, "no-path"
    vr, mode = _open_decord_reader(
        decord,
        path,
        _decord_open_kwargs(width, height),
        prefer_gpu,
        allow_cpu_fallback=bool(allow_cpu_fallback),
    )
    if vr is None:
        return None, 0.0, str(mode or "decord-open-failed")
    return vr, _decord_fps(vr), mode


def _decord_frame_bgr_at_ms(vr, fps: float, ms: int, downscale_w: int = 0):
    modules = _import_cv2_numpy()
    if modules is None or vr is None:
        return None
    cv2, np = modules
    frame_count = _safe_vr_length(vr)
    if frame_count <= 0:
        return None
    idx = _frame_index_at_ms(ms, fps, frame_count)
    arr = _frame_array_at_index(vr, idx, np)
    if arr is None:
        return None
    return _rgb_array_to_bgr(arr, downscale_w, cv2)


def _decord_batch_by_ms(vr, fps: float, ms_list: List[int]):
    if vr is None:
        return None, []
    frame_count = _safe_vr_length(vr)
    if frame_count <= 0:
        return None, []
    idxs = _frame_indices_for_ms_list(ms_list, fps, frame_count)
    if not idxs:
        return None, []
    try:
        return vr.get_batch(idxs), idxs
    except (AttributeError, IndexError, RuntimeError, TypeError, ValueError):
        return None, idxs


def _import_decord():
    try:
        import decord  # type: ignore
    except ImportError:
        return None
    return decord


def _import_cv2_numpy():
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return None
    return cv2, np


def _decord_open_kwargs(width: int, height: int) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}
    try:
        w = int(width)
    except (TypeError, ValueError):
        w = 0
    try:
        h = int(height)
    except (TypeError, ValueError):
        h = 0
    if w > 0 and h > 0:
        kwargs["width"] = w
        kwargs["height"] = h
    return kwargs


def _open_decord_reader(decord, path: str, open_kwargs: Dict[str, Any], prefer_gpu: bool, allow_cpu_fallback: bool = True):
    if bool(prefer_gpu):
        try:
            return decord.VideoReader(path, ctx=decord.gpu(0), **open_kwargs), "decord-gpu"
        except Exception:
            if not bool(allow_cpu_fallback):
                return None, "decord-gpu-open-failed"
    try:
        return decord.VideoReader(path, ctx=decord.cpu(0), **open_kwargs), "decord-cpu"
    except Exception:
        return None, "decord-cpu-open-failed"


def _decord_fps(vr) -> float:
    try:
        fps = float(vr.get_avg_fps() or 0.0)
    except (AttributeError, TypeError, ValueError):
        fps = 0.0
    return 30.0 if fps <= 1e-6 else float(fps)


def _safe_vr_length(vr) -> int:
    try:
        return int(len(vr))
    except (TypeError, ValueError):
        return 0


def _frame_index_at_ms(ms: int, fps: float, frame_count: int) -> int:
    try:
        idx = int(round((max(0.0, float(ms)) / 1000.0) * max(1e-6, float(fps))))
    except (TypeError, ValueError):
        idx = 0
    return max(0, min(frame_count - 1, int(idx)))


def _frame_indices_for_ms_list(ms_list: List[int], fps: float, frame_count: int) -> List[int]:
    idxs: List[int] = []
    for t_ms in ms_list or []:
        try:
            idx = int(round((max(0.0, float(t_ms)) / 1000.0) * max(1e-6, float(fps))))
        except (TypeError, ValueError):
            continue
        idxs.append(max(0, min(frame_count - 1, int(idx))))
    return idxs


def _frame_array_at_index(vr, idx: int, np):
    try:
        frame = vr[int(idx)]
        arr = frame.asnumpy() if hasattr(frame, "asnumpy") else np.asarray(frame)
    except (AttributeError, IndexError, RuntimeError, TypeError, ValueError):
        return None
    if arr is None or int(getattr(arr, "ndim", 0)) != 3:
        return None
    return arr


def _rgb_array_to_bgr(arr, downscale_w: int, cv2):
    try:
        img = _resize_rgb_array(arr, downscale_w, cv2)
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    except (AttributeError, IndexError, RuntimeError, TypeError, ValueError, cv2.error):
        return None


def _resize_rgb_array(arr, downscale_w: int, cv2):
    img = arr
    dw = max(0, int(downscale_w))
    if dw > 0 and int(img.shape[1]) > dw:
        nh = max(2, int(round(int(img.shape[0]) * (float(dw) / float(max(1, int(img.shape[1])))))))
        img = cv2.resize(img, (dw, nh), interpolation=cv2.INTER_AREA)
    return img
