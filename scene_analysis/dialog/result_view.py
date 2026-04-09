import os

from PyQt6 import QtCore


def collapse_direct_hits_first_only(step_ms: int, length_ms: int, filtered_data, sim_map, merge_band: float):
    rows = _sorted_rows(filtered_data, sim_map)
    if not rows:
        return [], {}
    same_run_gap_ms = step_ms + max(120, int(step_ms * 0.25))
    return _collapse_runs(rows, step_ms, same_run_gap_ms, length_ms, _score_band_width(merge_band))


def _sorted_rows(filtered_data, sim_map):
    return sorted(
        (
            (int(ms), float(scene_score), float(sim_map.get(int(ms), 0.0)))
            for ms, scene_score in filtered_data
            if int(ms) >= 0
        ),
        key=lambda x: x[0],
    )


def _score_band_width(merge_band: float) -> float:
    try:
        band = max(0.01, min(0.20, float(merge_band)))
    except Exception:
        band = 0.05
    return float(band)


def _collapse_runs(rows, step_ms: int, same_run_gap_ms: int, length_ms: int, score_band_width: float):
    out = []
    clip_map = {}
    run_rows = [rows[0]]
    run_last = int(rows[0][0])
    for ms, scene_score, sim in rows[1:]:
        if (ms - run_last) <= same_run_gap_ms:
            run_rows.append((int(ms), float(scene_score), float(sim)))
            run_last = int(ms)
            continue
        _flush_run_groups(out, clip_map, run_rows, step_ms, length_ms, score_band_width)
        run_rows = [(int(ms), float(scene_score), float(sim))]
        run_last = int(ms)
    _flush_run_groups(out, clip_map, run_rows, step_ms, length_ms, score_band_width)
    return out, clip_map


def _flush_run_groups(out, clip_map, run_rows, step_ms: int, length_ms: int, score_band_width: float):
    if not run_rows:
        return
    group_rows = [run_rows[0]]
    group_sim_min = float(run_rows[0][2])
    group_sim_max = float(run_rows[0][2])
    for row in run_rows[1:]:
        sim = float(row[2])
        next_min = min(group_sim_min, sim)
        next_max = max(group_sim_max, sim)
        if (next_max - next_min) <= float(score_band_width):
            group_rows.append(row)
            group_sim_min = next_min
            group_sim_max = next_max
            continue
        _flush_group_rows(out, clip_map, group_rows, step_ms, length_ms)
        group_rows = [row]
        group_sim_min = sim
        group_sim_max = sim
    _flush_group_rows(out, clip_map, group_rows, step_ms, length_ms)


def _flush_group_rows(out, clip_map, group_rows, step_ms: int, length_ms: int):
    start_ms = int(group_rows[0][0])
    last_ms = int(group_rows[-1][0])
    pick_ms, pick_score, _pick_sim = _best_group_row(group_rows)
    end_ms = max(start_ms, int(last_ms) + step_ms - 1)
    if length_ms > 0:
        end_ms = min(end_ms, max(start_ms + 1, int(length_ms) - 1))
    elif end_ms <= start_ms:
        end_ms = start_ms + 1
    out.append((int(pick_ms), float(pick_score)))
    clip_range = (int(start_ms), int(max(start_ms + 1, end_ms)))
    for member_ms, _scene_score, _sim in group_rows or [(int(pick_ms), float(pick_score), 0.0)]:
        clip_map[int(member_ms)] = clip_range


def _best_group_row(group_rows):
    best_ms, best_score, best_sim = group_rows[0]
    for ms, scene_score, sim in group_rows[1:]:
        if float(sim) > float(best_sim):
            best_ms, best_score, best_sim = int(ms), float(scene_score), float(sim)
    return int(best_ms), float(best_score), float(best_sim)


def populate_from_result(dialog, path: str, pts, top, *, reset_similarity: bool, scene_role_group_end_ms):
    path = os.path.abspath(str(path or ""))
    _stop_pending_timers(dialog)
    _reset_result_widgets(dialog)
    _reset_result_state(dialog, path, reset_similarity)
    scored_pts = _scored_points(pts, top)
    _set_result_sources(dialog, scored_pts, reset_similarity)
    ordered_pts = dialog._sort_scene_rows(scored_pts)
    _populate_with_thumbnails(dialog, ordered_pts)


def _stop_pending_timers(dialog):
    for timer_name in ("_load_check_timer", "_thumbnail_resume_timer"):
        timer = getattr(dialog, timer_name, None)
        if timer is not None and timer.isActive():
            timer.stop()


def _reset_result_widgets(dialog):
    dialog.listw.clear()
    dialog._clear_scene_frame_preview()
    dialog._item_by_ms.clear()
    dialog.thumb_worker.clear_jobs(release_capture=True)


def _reset_result_state(dialog, path: str, reset_similarity: bool):
    _sync_thumbnail_cache_path(dialog, path)
    dialog.current_path = path
    dialog.loaded_count = 0
    dialog.currently_loading = False
    if not reset_similarity:
        return
    dialog._similarity_by_ms.clear()
    dialog._last_refilter_sim_by_ms.clear()
    dialog._refilter_source_data = []
    dialog._refilter_source_override_ms = []
    dialog._direct_group_clip_ranges = {}
    dialog._refilter_active = False
    dialog.btn_refilter_clear.setEnabled(False)


def _sync_thumbnail_cache_path(dialog, path: str) -> None:
    current_cache_path = os.path.abspath(str(getattr(dialog, "_scene_thumb_cache_path", "") or ""))
    if current_cache_path != path:
        dialog._scene_thumb_cache = {}
    dialog._scene_thumb_cache_path = path


def _scored_points(pts, top):
    top_map = dict(top)
    return [(ms, top_map.get(ms, 0.0)) for ms in sorted(set(pts or []))]


def _set_result_sources(dialog, scored_pts, reset_similarity: bool):
    if reset_similarity:
        dialog._refilter_source_data = list(scored_pts)
    dialog._display_source_data = list(scored_pts)


def _populate_with_thumbnails(dialog, ordered_pts):
    dialog.all_scenes_data = ordered_pts
    total_count = len(dialog.all_scenes_data)
    if total_count == 0:
        dialog._update_scene_clip_button_enabled()
        dialog.lbl_status.setText("씬변화 결과 없음.")
        return
    dialog.lbl_status.setText(f"총 {total_count}개 씬 발견. ({dialog._scene_sort_label()})")
    QtCore.QTimer.singleShot(0, lambda: _trigger_first_load(dialog))


def _trigger_first_load(dialog):
    if dialog.listw.count() == 0:
        dialog._check_and_load_more()
    dialog._update_scene_clip_button_enabled()


def on_scene_result_selection_changed(dialog) -> None:
    if dialog._is_scene_frame_preview_enabled():
        dialog._schedule_scene_frame_preview_refresh(90)
    else:
        dialog._refresh_scene_frame_preview_if_enabled()
    dialog._update_scene_clip_button_enabled()
