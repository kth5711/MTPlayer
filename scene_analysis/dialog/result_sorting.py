from typing import List


def _format_time_label(ms: int) -> str:
    total_seconds = max(0, int(ms)) // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def _scene_time_label(dialog, ms: int) -> str:
    clip_map = dict(getattr(dialog, "_direct_group_clip_ranges", {}) or {})
    clip_range = clip_map.get(int(ms))
    if clip_range is None:
        return _format_time_label(ms)
    start_ms, end_ms = int(clip_range[0]), int(clip_range[1])
    if end_ms <= start_ms:
        return _format_time_label(ms)
    return f"{_format_time_label(start_ms)}~{_format_time_label(end_ms)}"


def scene_item_text(dialog, ms: int, score: float) -> str:
    time_label = _scene_time_label(dialog, ms)
    sim = dialog._similarity_by_ms.get(int(ms))
    if sim is None:
        return f"{time_label} (S: {score:.2f})"
    return f"{time_label} (S: {score:.2f} | U: {sim:.2f})"


def current_scene_sort_mode(dialog) -> str:
    mode = "time"
    if hasattr(dialog, "cmb_scene_sort"):
        mode = str(dialog.cmb_scene_sort.currentData() or "time").strip().lower()
    return "score" if mode == "score" else "time"


def scene_sort_label(dialog) -> str:
    return "점수순" if dialog._current_scene_sort_mode() == "score" else "시간순"


def scene_sort_score(dialog, ms: int, score: float) -> float:
    sim = dialog._similarity_by_ms.get(int(ms))
    if sim is not None:
        return float(sim)
    return float(score)


def _scene_sort_time_key(dialog, ms: int) -> int:
    clip_map = dict(getattr(dialog, "_direct_group_clip_ranges", {}) or {})
    clip_range = clip_map.get(int(ms))
    if clip_range is None:
        return int(ms)
    return int(clip_range[0])


def sort_scene_rows(dialog, rows: List[tuple[int, float]]) -> List[tuple[int, float]]:
    ordered = [(int(ms), float(score)) for ms, score in (rows or [])]
    if dialog._current_scene_sort_mode() == "score":
        ordered.sort(key=lambda row: (-dialog._scene_sort_score(int(row[0]), float(row[1])), int(row[0])))
    else:
        ordered.sort(key=lambda row: (_scene_sort_time_key(dialog, int(row[0])), int(row[0])))
    return ordered


def on_scene_sort_changed(dialog, *_args) -> None:
    source = list(getattr(dialog, "_display_source_data", []) or [])
    if not source or not dialog.current_path:
        return
    points = [int(ms) for ms, _score in source]
    dialog._populate_from_result(dialog.current_path, points, source, reset_similarity=False)
