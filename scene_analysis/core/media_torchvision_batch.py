from __future__ import annotations

from typing import Optional

from .media_torchvision_frame import (
    _torchvision_frame_bgr_from_chw,
    _torchvision_seek_next,
    _torchvision_unpack_frame,
)


def _torchvision_batch_rgb_by_ms(reader, ms_list, seq_state: Optional[dict] = None):
    torch = _import_torch()
    if torch is None or reader is None or not ms_list:
        return None
    if isinstance(seq_state, dict):
        batch = _sequential_torchvision_batch(reader, ms_list, seq_state, torch)
        if batch is not None:
            return batch
    return _stack_torch_frames(torch, _seek_stack_frames(reader, ms_list))


def _torchvision_frame_bgr_at_ms(reader, ms: int, downscale_w: int = 0, seq_state: Optional[dict] = None):
    chw = _torchvision_batch_first_frame(reader, ms, seq_state)
    if chw is None:
        item = _torchvision_seek_next(reader, float(max(0, int(ms))) / 1000.0)
        chw, _pts = _torchvision_unpack_frame(item)
    return _torchvision_frame_bgr_from_chw(chw, downscale_w=downscale_w)


def _import_torch():
    try:
        import torch  # type: ignore
    except ImportError:
        return None
    return torch


def _sequential_torchvision_batch(reader, ms_list, seq_state: dict, torch):
    targets = [max(0, int(ms)) for ms in (ms_list or [])]
    if not targets or not _targets_monotonic(targets):
        return None
    _prepare_seq_state(reader, seq_state, targets[0])
    frames, last_chw, last_pts_sec, frame_idx, eof = _consume_targets(reader, targets, seq_state)
    _store_seq_state(seq_state, targets[-1], last_chw, last_pts_sec, frame_idx)
    if eof and not frames:
        return None
    return _stack_torch_frames(torch, frames)


def _targets_monotonic(targets) -> bool:
    return all(targets[index] >= targets[index - 1] for index in range(1, len(targets)))


def _prepare_seq_state(reader, seq_state: dict, first_target: int) -> None:
    last_target_ms = int(seq_state.get("last_target_ms", -1) or -1)
    if first_target < last_target_ms:
        seq_state["ready"] = False
    fps = float(seq_state.get("fps", 30.0) or 30.0)
    if fps <= 1e-6:
        fps = 30.0
    if bool(seq_state.get("ready", False)):
        return
    try:
        reader.seek(0.0)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    seq_state.update({"ready": True, "frame_idx": 0, "last_pts_sec": -1.0, "last_chw": None, "fps": fps})


def _consume_targets(reader, targets, seq_state: dict):
    last_pts_sec = float(seq_state.get("last_pts_sec", -1.0) or -1.0)
    last_chw = seq_state.get("last_chw", None)
    frame_idx = int(seq_state.get("frame_idx", 0) or 0)
    fps = float(seq_state.get("fps", 30.0) or 30.0)
    frames = []
    eof = False
    for t_ms in targets:
        target_sec = float(t_ms) / 1000.0
        if eof:
            break
        last_chw, last_pts_sec, frame_idx, eof = _advance_to_target(reader, target_sec, last_chw, last_pts_sec, frame_idx, fps)
        if last_chw is not None:
            frames.append(last_chw)
    return frames, last_chw, last_pts_sec, frame_idx, eof


def _advance_to_target(reader, target_sec: float, last_chw, last_pts_sec: float, frame_idx: int, fps: float):
    if last_chw is None:
        last_chw, last_pts_sec, frame_idx = _next_valid_torchvision_frame(reader, fps, frame_idx)
        if last_chw is None:
            return None, last_pts_sec, frame_idx, True
    while (last_pts_sec + 1e-9) < target_sec:
        next_chw, next_pts_sec, frame_idx = _next_valid_torchvision_frame(reader, fps, frame_idx)
        if next_chw is None:
            return last_chw, last_pts_sec, frame_idx, True
        last_chw, last_pts_sec = next_chw, next_pts_sec
    return last_chw, last_pts_sec, frame_idx, False


def _next_valid_torchvision_frame(reader, fps: float, frame_idx: int):
    while True:
        try:
            item = next(reader)
        except (StopIteration, RuntimeError, TypeError, ValueError):
            return None, None, frame_idx
        chw, pts = _torchvision_unpack_frame(item)
        if chw is None:
            continue
        if pts is None:
            pts = float(frame_idx) / float(max(1e-6, fps))
        return chw, float(pts), frame_idx + 1


def _store_seq_state(seq_state: dict, last_target_ms: int, last_chw, last_pts_sec: float, frame_idx: int) -> None:
    seq_state["last_chw"] = last_chw
    seq_state["last_pts_sec"] = last_pts_sec
    seq_state["frame_idx"] = frame_idx
    seq_state["last_target_ms"] = last_target_ms


def _seek_stack_frames(reader, ms_list):
    frames = []
    for ms in ms_list:
        item = _torchvision_seek_next(reader, float(max(0, int(ms))) / 1000.0)
        chw, _pts = _torchvision_unpack_frame(item)
        if chw is not None:
            frames.append(chw)
    return frames


def _stack_torch_frames(torch, frames):
    if not frames:
        return None
    try:
        return torch.stack(frames, dim=0)
    except (RuntimeError, TypeError, ValueError):
        return None


def _torchvision_batch_first_frame(reader, ms: int, seq_state: Optional[dict]):
    if not isinstance(seq_state, dict):
        return None
    batch = _torchvision_batch_rgb_by_ms(reader, [int(ms)], seq_state=seq_state)
    try:
        if batch is not None and int(getattr(batch, "shape", [0])[0]) >= 1:
            return batch[0]
    except (AttributeError, IndexError, TypeError, ValueError):
        return None
    return None
