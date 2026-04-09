from __future__ import annotations

import os


def _open_torchvision_video(path: str):
    try:
        from torchvision.io import VideoReader  # type: ignore
    except ImportError:
        return None, 0.0, 0.0, "torchvision-unavailable"
    if not path or not os.path.exists(path):
        return None, 0.0, 0.0, "no-path"
    try:
        reader = VideoReader(path, "video")
    except Exception:
        return None, 0.0, 0.0, "torchvision-open-failed"
    fps, dur = _torchvision_reader_metadata(reader)
    return reader, float(fps), float(max(0.0, dur)), "torchvision-videoreader"


def _torchvision_unpack_frame(item):
    frame, pts_sec = _torchvision_item_parts(item)
    if frame is None:
        return None, None
    tensor = _frame_as_torch_tensor(frame)
    if tensor is None:
        return None, None
    return _normalize_torchvision_frame(tensor), _normalized_pts(pts_sec)


def _torchvision_seek_next(reader, sec: float):
    if reader is None:
        return None
    try:
        out = reader.seek(max(0.0, float(sec)))
    except (AttributeError, RuntimeError, TypeError, ValueError):
        out = None
    try:
        if out is not None:
            return next(out)
    except (StopIteration, TypeError, RuntimeError):
        pass
    try:
        return next(reader)
    except (StopIteration, TypeError, RuntimeError):
        return None


def _torchvision_frame_bgr_from_chw(chw, downscale_w: int = 0):
    modules = _import_cv2_numpy()
    if modules is None or chw is None:
        return None
    cv2, np = modules
    rgb = _chw_to_rgb_numpy(chw)
    if rgb is None:
        return None
    rgb = _normalize_rgb_dtype(rgb, np)
    if rgb is None:
        return None
    rgb = _resize_rgb_for_width(rgb, downscale_w, cv2)
    try:
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    except (AttributeError, TypeError, ValueError, cv2.error):
        return None


def _torchvision_reader_metadata(reader) -> tuple[float, float]:
    try:
        meta = reader.get_metadata() if hasattr(reader, "get_metadata") else {}
        vmeta = (meta or {}).get("video") or {}
        fps = _first_float(vmeta.get("fps"), 0.0)
        dur = _first_float(vmeta.get("duration"), 0.0)
    except (AttributeError, TypeError, ValueError):
        fps = 0.0
        dur = 0.0
    return (30.0 if fps <= 1e-6 else float(fps)), float(dur)


def _torchvision_item_parts(item):
    if isinstance(item, dict):
        return item.get("data", None), item.get("pts", item.get("pts_sec", item.get("pts_seconds", None)))
    if isinstance(item, (list, tuple)):
        return (item[0] if len(item) >= 1 else None), (item[1] if len(item) >= 2 else None)
    return None, None


def _frame_as_torch_tensor(frame):
    try:
        import torch  # type: ignore

        return frame if isinstance(frame, torch.Tensor) else torch.as_tensor(frame)
    except (ImportError, TypeError, RuntimeError):
        return None


def _normalize_torchvision_frame(frame):
    if int(getattr(frame, "ndim", 0)) != 3:
        return None
    if int(frame.shape[0]) in (1, 3, 4):
        chw = frame
    elif int(frame.shape[-1]) in (1, 3, 4):
        chw = frame.permute(2, 0, 1).contiguous()
    else:
        return None
    if int(chw.shape[0]) == 1:
        return chw.repeat(3, 1, 1)
    return chw[:3] if int(chw.shape[0]) >= 3 else chw


def _normalized_pts(pts_sec):
    try:
        return float(pts_sec) if pts_sec is not None else None
    except (TypeError, ValueError):
        return None


def _import_cv2_numpy():
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return None
    return cv2, np


def _chw_to_rgb_numpy(chw):
    try:
        rgb = chw.permute(1, 2, 0).contiguous().cpu().numpy()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    return rgb if int(getattr(rgb, "ndim", 0)) == 3 else None


def _normalize_rgb_dtype(rgb, np):
    if rgb.dtype == np.uint8:
        return rgb
    try:
        if float(np.max(rgb)) <= 1.5:
            rgb = np.clip(rgb, 0.0, 1.0) * 255.0
        return np.clip(rgb, 0.0, 255.0).astype(np.uint8)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None


def _resize_rgb_for_width(rgb, downscale_w: int, cv2):
    dw = int(downscale_w)
    if dw > 0 and int(rgb.shape[1]) > dw:
        nh = max(2, int(round(int(rgb.shape[0]) * (float(dw) / float(max(1, int(rgb.shape[1])))))))
        return cv2.resize(rgb, (dw, nh), interpolation=cv2.INTER_AREA)
    return rgb


def _first_float(value, default: float = 0.0) -> float:
    if isinstance(value, (list, tuple)):
        for item in value:
            try:
                return float(item)
            except (TypeError, ValueError):
                continue
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)
