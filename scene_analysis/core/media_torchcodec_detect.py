from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from .media_common import SIGLIP_BATCH_DEFAULT, _first_float, _normalize_siglip_batch_size
from .media_torchcodec_batch import _torchcodec_batch_rgb_by_ms
from .media_torchcodec_open import _open_torchcodec_video
from .media_torchvision import _torchvision_frame_bgr_from_chw


def _torchcodec_import_cv():
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return None, None
    return cv2, np


def _torchcodec_ms_list(decoder, fps: float, duration_sec: float, sample_fps: int):
    use_sample_fps = int(sample_fps) if int(sample_fps) > 0 else 5
    step_sec = 1.0 / float(max(1, use_sample_fps))
    if float(duration_sec) > 0.0:
        total_est = max(1, int(round(float(duration_sec) / float(max(1e-6, step_sec)))))
        return [max(0, int(round(float(i) * float(step_sec) * 1000.0))) for i in range(total_est + 1)]
    try:
        md = getattr(decoder, "metadata", None)
        n_frames = 0 if md is None else int(
            _first_float(
                [getattr(md, "num_frames", 0.0), getattr(md, "num_frames_from_content", 0.0), getattr(md, "num_frames_from_header", 0.0)],
                0.0,
            )
        )
    except (AttributeError, RuntimeError, TypeError, ValueError):
        n_frames = 0
    if n_frames <= 0:
        return []
    step = max(1, int(round(float(max(1e-6, fps)) / float(max(1, use_sample_fps)))))
    return [max(0, int(round((float(idx) / float(max(1e-6, fps))) * 1000.0))) for idx in range(0, int(n_frames), int(step))]


def _torchcodec_chunk_size(prefer_gpu: bool, decode_chunk_size: int) -> int:
    try:
        raw_chunk = int(decode_chunk_size)
    except (TypeError, ValueError):
        raw_chunk = 64
    if not bool(prefer_gpu):
        return max(8, min(512, max(8, raw_chunk)))
    try:
        chunk_sz = _normalize_siglip_batch_size(raw_chunk, default=SIGLIP_BATCH_DEFAULT)
    except (TypeError, ValueError):
        chunk_sz = max(16, raw_chunk)
    return max(8, min(512, int(chunk_sz)))


def _torchcodec_gray_frame(cv2, chw, downscale_w: int):
    bgr = _torchvision_frame_bgr_from_chw(chw, downscale_w=downscale_w)
    if bgr is None:
        return None
    try:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray, (5, 5), 0)
    except (AttributeError, RuntimeError, TypeError, ValueError, cv2.error):
        return None


def _torchcodec_scene_score(cv2, np, gray, prev_gray):
    try:
        diff = cv2.absdiff(gray, prev_gray)
        return min(1.0, float(np.mean(diff)) / 255.0 * 4.0)
    except (RuntimeError, TypeError, ValueError, cv2.error):
        return 0.0


def _torchcodec_scene_ms(pts_list, chunk: List[int], index: int) -> int:
    if isinstance(pts_list, list) and index < len(pts_list):
        return int(round(float(pts_list[index]) * 1000.0))
    return int(chunk[min(index, len(chunk) - 1)])


def _torchcodec_emit_progress(progress_cb, done: int, total: int):
    if not callable(progress_cb):
        return
    if done == total or (done % max(1, total // 120) == 0):
        progress_cb(max(1, min(98, int(round((float(done) * 98.0) / float(total))))))


def _torchcodec_cancelled(cancel_cb, mode: str):
    return callable(cancel_cb) and bool(cancel_cb()), str(mode or "cancelled")


def _torchcodec_scan_frame(chw_batch, index: int, prev_gray, out_scores, downscale_w, thr, pts_list, chunk, cv2, np):
    try:
        chw = chw_batch[index]
    except (AttributeError, IndexError, RuntimeError, TypeError, ValueError):
        return prev_gray
    gray = _torchcodec_gray_frame(cv2, chw, downscale_w)
    if gray is None:
        return prev_gray
    if prev_gray is not None:
        score = _torchcodec_scene_score(cv2, np, gray, prev_gray)
        if score >= thr:
            out_scores.append((_torchcodec_scene_ms(pts_list, chunk, index), float(score)))
    return gray


def _torchcodec_scan_chunk(
    decoder,
    chunk: List[int],
    prev_gray,
    out_scores: List[tuple[int, float]],
    downscale_w: int,
    thr: float,
    done: int,
    total: int,
    progress_cb,
    cancel_cb,
    mode: str,
    cv2,
    np,
):
    chw_batch, pts_list = _torchcodec_batch_rgb_by_ms(decoder, chunk)
    if chw_batch is None:
        return prev_gray, done, None
    n = int(getattr(chw_batch, "shape", [0])[0]) if hasattr(chw_batch, "shape") else 0
    for j in range(n):
        is_cancelled, cancelled_mode = _torchcodec_cancelled(cancel_cb, mode)
        if is_cancelled:
            return prev_gray, done, cancelled_mode
        prev_gray = _torchcodec_scan_frame(
            chw_batch, j, prev_gray, out_scores, downscale_w, thr, pts_list, chunk, cv2, np
        )
        done += 1
        _torchcodec_emit_progress(progress_cb, done, total)
    return prev_gray, done, None


def _torchcodec_finalize_scores(out_scores: List[tuple[int, float]]):
    pts = sorted(set(int(ms) for ms, _sc in out_scores))
    if 0 not in pts:
        pts = [0] + pts
    scores = sorted(((int(ms), float(sc)) for ms, sc in out_scores), key=lambda x: x[0])
    return pts, scores


def _torchcodec_detect_setup(path: str, prefer_gpu: bool, threshold: float, sample_fps: int):
    decoder, fps, duration_sec, mode = _open_torchcodec_video(path, prefer_gpu=prefer_gpu)
    if decoder is None:
        return None, None, None, [0], [], False, str(mode or "torchcodec-open-failed")
    ms_list = _torchcodec_ms_list(decoder, fps, duration_sec, sample_fps)
    if not ms_list:
        return None, None, None, [0], [], False, "torchcodec-no-duration"
    ms_list = sorted(set(int(v) for v in ms_list if int(v) >= 0))
    if not ms_list:
        return None, None, None, [0], [], False, str(mode or "torchcodec-empty")
    return decoder, mode, max(0.01, min(0.95, float(threshold))), ms_list, [], True, None


def _torchcodec_run_scan(decoder, ms_list, chunk_sz, downscale_w, thr, progress_cb, cancel_cb, mode, cv2, np):
    prev_gray = None
    out_scores: List[tuple[int, float]] = []
    total = max(1, len(ms_list))
    done = 0
    for i in range(0, len(ms_list), chunk_sz):
        prev_gray, done, cancelled = _torchcodec_scan_chunk(
            decoder,
            ms_list[i:i + chunk_sz],
            prev_gray,
            out_scores,
            downscale_w,
            thr,
            done,
            total,
            progress_cb,
            cancel_cb,
            mode,
            cv2,
            np,
        )
        if cancelled is not None:
            return [0], [], False, cancelled
    pts, scores = _torchcodec_finalize_scores(out_scores)
    return pts, scores, True, str(mode or "torchcodec-cpu")


def _torchcodec_detect_scenes_scored(
    path: str,
    threshold: float = 0.35,
    downscale_w: int = 320,
    sample_fps: int = 0,
    prefer_gpu: bool = False,
    decode_chunk_size: int = 64,
    progress_cb: Optional[Callable[[int], None]] = None,
    cancel_cb: Optional[Callable[[], bool]] = None,
) -> Tuple[List[int], List[tuple[int, float]], bool, str]:
    cv2, np = _torchcodec_import_cv()
    if cv2 is None or np is None:
        return [0], [], False, "cv2-or-numpy-unavailable"
    decoder, mode, thr, ms_list, _unused_scores, ok, error = _torchcodec_detect_setup(
        path, prefer_gpu, threshold, sample_fps
    )
    if not ok:
        return [0], [], False, str(error or "torchcodec-setup-failed")
    chunk_sz = _torchcodec_chunk_size(prefer_gpu, decode_chunk_size)
    return _torchcodec_run_scan(
        decoder, ms_list, chunk_sz, downscale_w, thr, progress_cb, cancel_cb, mode, cv2, np
    )


__all__ = ["_torchcodec_detect_scenes_scored"]
