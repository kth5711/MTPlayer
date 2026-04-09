from __future__ import annotations

from typing import Any, Dict, List

from .refilter_feature_rows import _siglip_feature_row_count, _slice_siglip_feature_rows
from .similarity import (
    _pick_anchor_positions,
    _pick_anchor_times,
    _scene_window_dynamic_sample_count,
    _scene_window_sample_times,
)


def build_scene_similarity_tasks(
    worker,
    scene_ms_sorted: List[int],
    total: int,
    video_len_ms: int,
) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    for index, ms in enumerate(scene_ms_sorted):
        worker._raise_if_cancelled()
        scene_start_ms, scene_end_ms = _scene_bounds(scene_ms_sorted, index, int(ms), total, video_len_ms)
        task = _scene_window_task(worker, scene_start_ms, scene_end_ms)
        tasks.append(task)
    return tasks


def _scene_bounds(scene_ms_sorted: List[int], index: int, scene_start_ms: int, total: int, video_len_ms: int):
    if index + 1 < total:
        scene_end_ms = max(scene_start_ms, int(scene_ms_sorted[index + 1]) - 1)
    elif video_len_ms > scene_start_ms + 1:
        scene_end_ms = max(scene_start_ms, int(video_len_ms) - 1)
    else:
        scene_end_ms = scene_start_ms + 3000
    if scene_end_ms <= scene_start_ms:
        scene_end_ms = scene_start_ms + 1000
    return int(scene_start_ms), int(scene_end_ms)


def _scene_window_task(worker, scene_start_ms: int, scene_end_ms: int) -> Dict[str, Any]:
    if worker.sampling_mode != "scene_window":
        return {
            "scene_start_ms": int(scene_start_ms),
            "scene_end_ms": int(scene_end_ms),
            "t_full": [int(scene_start_ms)],
            "t_coarse": [int(scene_start_ms)],
            "coarse_pos": [0],
        }
    sample_n = _scene_window_dynamic_sample_count(
        scene_start_ms, scene_end_ms, worker.frame_sample_count, worker.frame_profile
    )
    t_full = sorted(set(int(x) for x in _scene_window_sample_times(scene_start_ms, scene_end_ms, sample_n)))
    t_coarse = _pick_anchor_times(t_full, max_count=3) or [int(scene_start_ms)]
    coarse_set = set(int(x) for x in t_coarse)
    coarse_pos = [int(pos) for pos, t in enumerate(t_full) if int(t) in coarse_set] or [0]
    return {
        "scene_start_ms": int(scene_start_ms),
        "scene_end_ms": int(scene_end_ms),
        "t_full": list(t_full),
        "t_coarse": [int(x) for x in t_coarse],
        "coarse_pos": list(coarse_pos),
    }


def derive_coarse_feature_rows(scene_tasks: List[Dict[str, Any]], coarse_feat_map: Dict[int, Any], full_feat_map: Dict[int, Any]):
    dirty = False
    for task in scene_tasks:
        ms = int(task.get("scene_start_ms", 0))
        if ms in coarse_feat_map:
            continue
        coarse_pos = [int(x) for x in (task.get("coarse_pos") or [])]
        if not coarse_pos:
            coarse_pos = _pick_anchor_positions(_siglip_feature_row_count(full_feat_map.get(ms)), max_count=3)
            if coarse_pos:
                task["coarse_pos"] = list(coarse_pos)
        derived = _slice_siglip_feature_rows(full_feat_map.get(ms), coarse_pos)
        if derived is not None:
            coarse_feat_map[ms] = derived
            dirty = True
    return dirty


__all__ = ["build_scene_similarity_tasks", "derive_coarse_feature_rows"]
