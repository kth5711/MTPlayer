import os
from typing import Dict, List, Optional

from scene_analysis.core.cache import (
    _read_json_dict,
    cache_history_entries,
    load_from_disk,
    scene_cache_get,
    scene_cache_set,
)


def _history_payload_pts(payload: dict) -> List[int]:
    pts: List[int] = []
    for raw in (payload.get("pts") or []):
        try:
            ms = int(raw)
        except (TypeError, ValueError):
            continue
        if ms >= 0:
            pts.append(ms)
    return sorted(set(pts))


def _history_payload_top(payload: dict) -> List[tuple[int, float]]:
    top_list: List[tuple[int, float]] = []
    for row in (payload.get("top") or payload.get("top10") or []):
        try:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                top_list.append((int(row[0]), float(row[1])))
        except (TypeError, ValueError):
            continue
    return top_list


def _apply_scene_user_threshold(pts: List[int], top: List[tuple[int, float]], user_thr: float) -> List[int]:
    base = sorted(set(int(ms) for ms in (pts or [])))
    if 0 not in base:
        base = [0] + base
    if not top:
        return base
    filtered = sorted(set(int(ms) for ms, score in top if float(score) >= float(user_thr)))
    if 0 not in filtered:
        filtered = [0] + filtered
    if len(filtered) <= 1 and len(base) > 1:
        return base
    return filtered


def _filter_scene_points(pts: List[int], top: List[tuple[int, float]], topk: int, mingap: int) -> List[int]:
    top_map = dict(top or [])
    scored_pts: List[tuple[int, float]] = []
    for ms in sorted(set(int(v) for v in (pts or []))):
        scored_pts.append((int(ms), float(top_map.get(int(ms), 0.0))))
    if int(topk) > 0:
        scored_pts.sort(key=lambda x: x[1], reverse=True)
        working = scored_pts[: int(topk)]
        working.sort(key=lambda x: x[0])
    else:
        working = scored_pts
    out: List[int] = []
    if int(mingap) > 0:
        last_ms = -int(mingap)
        for ms, _score in working:
            if (int(ms) - int(last_ms)) >= int(mingap):
                out.append(int(ms))
                last_ms = int(ms)
    else:
        out = [int(ms) for ms, _score in working]
    if 0 not in out:
        out.append(0)
    return sorted(set(int(ms) for ms in out))


def _scene_filtered_points(pts: List[int], top: List[tuple[int, float]], options: Dict[str, object]) -> List[int]:
    base_pts = _apply_scene_user_threshold(pts, top, float(options.get("thr", 0.35)))
    return _filter_scene_points(
        base_pts,
        top,
        int(options.get("scene_topk", 0)),
        int(options.get("scene_mingap", 0)),
    )


def _normalize_scene_source_ms(pts: List[int]) -> List[int]:
    out = sorted(set(int(ms) for ms in (pts or []) if int(ms) >= 0))
    if 0 not in out:
        out = [0] + out
    return out


def _load_scene_cache_payload(path: str, options: Dict[str, object]) -> tuple[Optional[str], List[int], List[tuple[int, float]]]:
    use_ff = bool(options.get("use_ff", True))
    thr = float(options.get("thr", 0.35))
    dw = int(options.get("dw", 320))
    fps = int(options.get("fps", 5))
    ff_hwaccel = bool(options.get("ff_hwaccel", False))
    cached = scene_cache_get(path, use_ff, thr, dw, fps, ff_hwaccel=ff_hwaccel)
    if cached:
        return (
            "메모리",
            [int(ms) for ms in (cached.get("pts") or [])],
            [(int(ms), float(score)) for ms, score in (cached.get("top10") or [])],
        )
    pts_d, top_d = load_from_disk(path, use_ff, thr, dw, fps, ff_hwaccel=ff_hwaccel)
    if pts_d:
        top_list = [(int(ms), float(score)) for ms, score in (top_d or [])]
        scene_cache_set(path, use_ff, thr, dw, fps, pts_d, top_list, ff_hwaccel=ff_hwaccel)
        return ("디스크", [int(ms) for ms in (pts_d or [])], top_list)
    return None, [], []


def _load_recent_scene_history_payload(path: str) -> tuple[Optional[str], List[int], List[tuple[int, float]]]:
    try:
        rows = cache_history_entries(path, current_only=True)
    except Exception:
        return None, [], []
    for ent in rows:
        if str(ent.get("type") or "") != "scene":
            continue
        payload = _read_json_dict(str(ent.get("file_path") or ""))
        if not payload:
            continue
        pts = _history_payload_pts(payload)
        if not pts:
            continue
        return "결과기록", pts, _history_payload_top(payload)
    return None, [], []


def _resolve_refilter_scene_source_payload(
    path: str,
    options: Dict[str, object],
    *,
    prefer_recent_history_only: bool = False,
) -> tuple[Optional[str], List[int], List[tuple[int, float]]]:
    if bool(prefer_recent_history_only):
        return _load_recent_scene_history_payload(path)
    label, pts, top = _load_scene_cache_payload(path, options)
    if label is not None:
        return label, pts, top
    return _load_recent_scene_history_payload(path)


def _video_length_ms(path: str) -> int:
    if not path or not os.path.exists(path):
        return 0
    try:
        import cv2  # type: ignore

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return 0
        try:
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        finally:
            cap.release()
        if fps > 0.0 and frame_count > 0.0:
            return max(0, int(round((frame_count / fps) * 1000.0)))
    except Exception:
        pass
    return 0


def _build_direct_refilter_ms(path: str, interval_sec: int) -> List[int]:
    step_ms = max(1000, int(max(1, int(interval_sec)) * 1000))
    length_ms = _video_length_ms(path)
    if length_ms <= 0:
        return [0]
    starts = list(range(0, max(1, int(length_ms)), step_ms))
    if not starts:
        starts = [0]
    tail = max(0, int(length_ms) - 1)
    if tail - starts[-1] >= (step_ms // 2):
        starts.append(tail)
    return sorted(set(max(0, int(ms)) for ms in starts))
