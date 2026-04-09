from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from .media_torchvision_io import (
    _open_torchvision_video,
    _torchvision_frame_bgr_from_chw,
    _torchvision_unpack_frame,
)


def _torchvision_detect_scenes_scored(
    path: str,
    threshold: float = 0.35,
    downscale_w: int = 320,
    sample_fps: int = 0,
    progress_cb: Optional[Callable[[int], None]] = None,
    cancel_cb: Optional[Callable[[], bool]] = None,
) -> Tuple[List[int], List[tuple[int, float]], bool, str]:
    modules = _import_cv2_numpy()
    if modules is None:
        return [0], [], False, "cv2-or-numpy-unavailable"
    cv2, np = modules
    reader, fps, duration_sec, mode = _open_torchvision_video(path)
    if reader is None:
        return [0], [], False, str(mode or "torchvision-open-failed")
    out_scores = _scan_torchvision_scores(reader, fps, duration_sec, threshold, downscale_w, sample_fps, cv2, np, progress_cb, cancel_cb)
    if out_scores is None:
        return [0], [], False, str(mode or "cancelled")
    pts = sorted(set(int(ms) for ms, _ in out_scores))
    if 0 not in pts:
        pts = [0] + pts
    out_scores = sorted(((int(ms), float(sc)) for ms, sc in out_scores), key=lambda item: item[0])
    return pts, out_scores, True, str(mode or "torchvision-videoreader")


def _import_cv2_numpy():
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return None
    return cv2, np


def _scan_torchvision_scores(
    reader,
    fps: float,
    duration_sec: float,
    threshold: float,
    downscale_w: int,
    sample_fps: int,
    cv2,
    np,
    progress_cb,
    cancel_cb,
):
    sampled_count = 0
    scan_args = _detect_scan_config(threshold, downscale_w, sample_fps, duration_sec)
    return _run_torchvision_scan_loop(reader, fps, cv2, np, progress_cb, cancel_cb, sampled_count, *scan_args)


def _detect_scan_config(threshold: float, downscale_w: int, sample_fps: int, duration_sec: float):
    step_sec = 1.0 / float(max(1, int(sample_fps) if int(sample_fps) > 0 else 5))
    thr = max(0.01, min(0.95, float(threshold)))
    dw = max(64, int(downscale_w)) if int(downscale_w) > 0 else 320
    total_est = int(round(max(0.0, float(duration_sec)) / max(1e-6, step_sec))) if duration_sec > 0.0 else 0
    return step_sec, thr, dw, total_est


def _run_torchvision_scan_loop(reader, fps: float, cv2, np, progress_cb, cancel_cb, sampled_count: int, step_sec: float, thr: float, dw: int, total_est: int):
    prev_gray = None
    out_scores: List[tuple[int, float]] = []
    next_keep_sec = 0.0
    idx = 0
    _seek_reader_start(reader)
    while True:
        scan_state = _next_scan_state(reader, cancel_cb, idx, fps, next_keep_sec, step_sec, dw, cv2)
        if scan_state == "cancelled":
            return None
        if scan_state is None:
            return out_scores
        idx, gray, pts_sec, next_keep_sec = scan_state
        if gray is None:
            continue
        sampled_count += 1
        _append_scene_score(out_scores, gray, prev_gray, pts_sec, thr, cv2, np)
        prev_gray = gray
        _emit_progress(progress_cb, total_est, sampled_count)


def _seek_reader_start(reader) -> None:
    try:
        reader.seek(0.0)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass


def _next_reader_item(reader):
    try:
        return next(reader)
    except (StopIteration, RuntimeError, TypeError, ValueError):
        return None


def _next_scan_state(reader, cancel_cb, idx: int, fps: float, next_keep_sec: float, step_sec: float, downscale_w: int, cv2):
    if callable(cancel_cb) and bool(cancel_cb()):
        return "cancelled"
    item = _next_reader_item(reader)
    if item is None:
        return None
    next_idx = idx + 1
    gray_info = _torchvision_gray_frame(item, next_idx, fps, next_keep_sec, step_sec, downscale_w, cv2)
    if gray_info is None:
        return next_idx, None, None, next_keep_sec
    gray, pts_sec, next_keep = gray_info
    return next_idx, gray, pts_sec, next_keep


def _torchvision_gray_frame(
    item,
    idx: int,
    fps: float,
    next_keep_sec: float,
    step_sec: float,
    downscale_w: int,
    cv2,
):
    chw, pts_sec = _torchvision_unpack_frame(item)
    if chw is None:
        return None
    if pts_sec is None:
        pts_sec = float(idx - 1) / float(max(1e-6, fps))
    if float(pts_sec) + 1e-9 < float(next_keep_sec):
        return None
    bgr = _torchvision_frame_bgr_from_chw(chw, downscale_w=downscale_w)
    if bgr is None:
        return None
    try:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
    except (AttributeError, RuntimeError, TypeError, ValueError, cv2.error):
        return None
    return gray, float(pts_sec), float(pts_sec) + float(step_sec)


def _gray_diff_score(gray, prev_gray, cv2, np) -> float:
    try:
        diff = cv2.absdiff(gray, prev_gray)
        return min(1.0, float(np.mean(diff)) / 255.0 * 4.0)
    except (RuntimeError, TypeError, ValueError, cv2.error):
        return 0.0


def _append_scene_score(out_scores, gray, prev_gray, pts_sec: float, thr: float, cv2, np) -> None:
    if prev_gray is None:
        return
    score = _gray_diff_score(gray, prev_gray, cv2, np)
    if score >= thr:
        out_scores.append((int(round(float(pts_sec) * 1000.0)), float(score)))


def _emit_progress(progress_cb, total_est: int, sampled_count: int) -> None:
    if not callable(progress_cb):
        return
    if total_est > 0:
        progress_cb(max(1, min(98, int(round((float(min(total_est, sampled_count)) * 98.0) / float(total_est))))))
        return
    if (sampled_count % 20) == 0:
        progress_cb(min(98, 5 + sampled_count))
