from __future__ import annotations

from typing import List

from .media_torchvision import _torchvision_frame_bgr_from_chw


def _torchcodec_extract_payload(batch_obj):
    frames = None
    pts = None
    try:
        if isinstance(batch_obj, dict):
            frames = batch_obj.get("data")
            pts = batch_obj.get("pts_seconds", batch_obj.get("pts"))
        else:
            frames = getattr(batch_obj, "data", None)
            pts = getattr(batch_obj, "pts_seconds", None)
            if frames is None:
                frames = batch_obj
    except (AttributeError, TypeError):
        return None, None
    return frames, pts


def _torchcodec_frames_to_chw(frames, torch):
    try:
        tensor = frames if isinstance(frames, torch.Tensor) else torch.as_tensor(frames)
    except (TypeError, RuntimeError):
        return None
    if int(getattr(tensor, "ndim", 0)) == 3:
        tensor = tensor.unsqueeze(0)
    if int(getattr(tensor, "ndim", 0)) != 4:
        return None
    try:
        if int(tensor.shape[1]) in (1, 3, 4):
            chw = tensor
        elif int(tensor.shape[-1]) in (1, 3, 4):
            chw = tensor.permute(0, 3, 1, 2).contiguous()
        else:
            return None
        if int(chw.shape[1]) == 1:
            chw = chw.repeat(1, 3, 1, 1)
        elif int(chw.shape[1]) >= 3:
            chw = chw[:, :3]
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    return chw


def _torchcodec_pts_to_list(pts, torch):
    if pts is None:
        return None
    try:
        if isinstance(pts, torch.Tensor):
            return [float(x) for x in pts.detach().cpu().flatten().tolist()]
        if isinstance(pts, (list, tuple)):
            return [float(x) for x in pts]
        return [float(pts)]
    except (TypeError, ValueError, RuntimeError):
        return None


def _torchcodec_unpack_batch(batch_obj):
    try:
        import torch  # type: ignore
    except ImportError:
        return None, None
    if batch_obj is None:
        return None, None
    frames, pts = _torchcodec_extract_payload(batch_obj)
    if frames is None:
        return None, None
    chw = _torchcodec_frames_to_chw(frames, torch)
    if chw is None:
        return None, None
    return chw, _torchcodec_pts_to_list(pts, torch)


def _torchcodec_batch_rgb_by_ms(decoder, ms_list: List[int]):
    if decoder is None or (not ms_list):
        return None, None
    secs = [max(0, int(ms)) / 1000.0 for ms in (ms_list or [])]
    if not secs:
        return None, None

    batch = None
    try:
        batch = decoder.get_frames_played_at(seconds=secs)
    except TypeError:
        try:
            batch = decoder.get_frames_played_at(secs)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            batch = None
    except (AttributeError, RuntimeError, TypeError, ValueError):
        batch = None
    if batch is None:
        return None, None
    return _torchcodec_unpack_batch(batch)


def _torchcodec_frame_bgr_at_ms(decoder, ms: int, downscale_w: int = 0):
    chw_batch, _pts = _torchcodec_batch_rgb_by_ms(decoder, [int(ms)])
    if chw_batch is None:
        return None
    try:
        if int(getattr(chw_batch, "shape", [0])[0]) < 1:
            return None
        chw = chw_batch[0]
    except (AttributeError, TypeError, ValueError):
        return None
    return _torchvision_frame_bgr_from_chw(chw, downscale_w=downscale_w)


__all__ = [
    "_torchcodec_batch_rgb_by_ms",
    "_torchcodec_frame_bgr_at_ms",
    "_torchcodec_unpack_batch",
]
