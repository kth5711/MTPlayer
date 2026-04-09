from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from .media_decord_io import (
    _frame_array_at_index,
    _import_cv2_numpy,
    _open_decord_video,
    _safe_vr_length,
    _resize_rgb_array,
)


def _decord_detect_scenes_scored(
    path: str,
    threshold: float = 0.35,
    downscale_w: int = 320,
    sample_fps: int = 0,
    prefer_gpu: bool = False,
    progress_cb: Optional[Callable[[int], None]] = None,
    cancel_cb: Optional[Callable[[], bool]] = None,
) -> Tuple[List[int], List[tuple[int, float]], bool, str]:
    modules = _import_cv2_numpy()
    if modules is None:
        return [0], [], False, "cv2-or-numpy-unavailable"
    cv2, np = modules
    vr, fps, mode = _open_decord_video(path, prefer_gpu=prefer_gpu)
    frame_count = _safe_vr_length(vr)
    if vr is None:
        return [0], [], False, str(mode or "decord-open-failed")
    if frame_count <= 0:
        return [0], [], False, str(mode or "decord-empty")
    idx_list = _sample_indices(frame_count, fps, sample_fps)
    out_scores = _scan_scene_scores(vr, idx_list, fps, threshold, downscale_w, cv2, np, progress_cb, cancel_cb)
    if out_scores is None:
        return [0], [], False, str(mode or "cancelled")
    pts = sorted(set(int(ms) for ms, _ in out_scores))
    if 0 not in pts:
        pts = [0] + pts
    out_scores = sorted(((int(ms), float(sc)) for ms, sc in out_scores), key=lambda item: item[0])
    return pts, out_scores, True, str(mode or "decord-cpu")


def _sample_indices(frame_count: int, fps: float, sample_fps: int) -> List[int]:
    use_sample_fps = int(sample_fps) if int(sample_fps) > 0 else 5
    step = max(1, int(round(float(fps) / float(max(1, use_sample_fps)))))
    idx_list = list(range(0, frame_count, step))
    if (frame_count - 1) not in idx_list:
        idx_list.append(frame_count - 1)
    return sorted(set(int(idx) for idx in idx_list if int(idx) >= 0))


def _scan_scene_scores(
    vr,
    idx_list: List[int],
    fps: float,
    threshold: float,
    downscale_w: int,
    cv2,
    np,
    progress_cb,
    cancel_cb,
):
    prev_gray = None
    out_scores: List[tuple[int, float]] = []
    thr = max(0.01, min(0.95, float(threshold)))
    dw = max(64, int(downscale_w)) if int(downscale_w) > 0 else 320
    total = max(1, len(idx_list))
    for idx_no, idx in enumerate(idx_list):
        if callable(cancel_cb) and bool(cancel_cb()):
            return None
        gray = _decord_gray_frame(vr, idx, dw, cv2, np)
        if gray is None:
            continue
        if prev_gray is not None:
            score = _gray_diff_score(gray, prev_gray, cv2, np)
            if score >= thr:
                out_scores.append((int(round((float(idx) / float(max(1e-6, fps))) * 1000.0)), float(score)))
        prev_gray = gray
        _emit_progress(progress_cb, idx_no, total)
    return out_scores


def _decord_gray_frame(vr, idx: int, downscale_w: int, cv2, np):
    arr = _frame_array_at_index(vr, idx, np)
    if arr is None:
        return None
    try:
        gray = cv2.cvtColor(_resize_rgb_array(arr, downscale_w, cv2), cv2.COLOR_RGB2GRAY)
        return cv2.GaussianBlur(gray, (5, 5), 0)
    except (AttributeError, IndexError, RuntimeError, TypeError, ValueError, cv2.error):
        return None


def _gray_diff_score(gray, prev_gray, cv2, np) -> float:
    try:
        diff = cv2.absdiff(gray, prev_gray)
        return min(1.0, float(np.mean(diff)) / 255.0 * 4.0)
    except (RuntimeError, TypeError, ValueError, cv2.error):
        return 0.0


def _emit_progress(progress_cb, idx_no: int, total: int) -> None:
    if not callable(progress_cb):
        return
    if idx_no == (total - 1) or (idx_no % max(1, total // 120) == 0):
        progress_cb(max(1, min(98, int(round((float(idx_no + 1) * 98.0) / float(total))))))
