from typing import List

from PyQt6 import QtCore, QtWidgets

from .preview_items import SCENE_ROLE_GROUP_END_MS, SCENE_ROLE_GROUP_START_MS


def check_and_load_more(dialog) -> None:
    if dialog.currently_loading:
        return
    if not hasattr(dialog, "all_scenes_data"):
        return
    if dialog.loaded_count >= len(dialog.all_scenes_data):
        return

    scrollbar = dialog.listw.verticalScrollBar()
    is_scrollbar_visible = scrollbar.maximum() > scrollbar.minimum()
    if not is_scrollbar_visible:
        is_near_bottom = True
    else:
        is_near_bottom = scrollbar.value() >= int(scrollbar.maximum() * 0.9)

    if is_near_bottom:
        dialog._load_next_batch()


def load_next_batch(dialog) -> None:
    if dialog.currently_loading:
        return
    if not hasattr(dialog, "all_scenes_data") or dialog.loaded_count >= len(dialog.all_scenes_data):
        return

    dialog.currently_loading = True
    try:
        path, batch, end_index = _next_batch_payload(dialog)
        if not batch:
            return
        thumb_jobs = _append_batch_items(dialog, batch)
        _finalize_batch_load(dialog, path, thumb_jobs, end_index)
    finally:
        dialog.currently_loading = False

    _schedule_followup_batch_load(dialog)


def _next_batch_payload(dialog):
    path = dialog.current_path
    dialog.batch_size = dialog.spn_batch.value()
    start_index = dialog.loaded_count
    end_index = min(start_index + dialog.batch_size, len(dialog.all_scenes_data))
    if start_index >= end_index:
        return path, [], end_index
    return path, dialog.all_scenes_data[start_index:end_index], end_index


def _append_batch_items(dialog, batch) -> List[int]:
    thumb_jobs: List[int] = []
    clip_map = dict(getattr(dialog, "_direct_group_clip_ranges", {}) or {})
    dialog.listw.setUpdatesEnabled(False)
    try:
        for ms, score in batch:
            item = _build_scene_item(dialog, ms, score, clip_map)
            dialog.listw.addItem(item)
            dialog._item_by_ms[int(ms)] = item
            clip_range = clip_map.get(int(ms))
            if clip_range is not None and int(clip_range[0]) >= 0:
                dialog._item_by_ms[int(clip_range[0])] = item
            if not _apply_cached_scene_thumbnail(dialog, item, int(ms)):
                thumb_jobs.append(int(ms))
    finally:
        dialog.listw.setUpdatesEnabled(True)
    return thumb_jobs


def _build_scene_item(dialog, ms: int, score: float, clip_map: dict[int, tuple[int, int]]):
    item = QtWidgets.QListWidgetItem(dialog._scene_item_text(ms, score))
    item.setData(QtCore.Qt.ItemDataRole.UserRole, ms)
    clip_range = clip_map.get(int(ms))
    if clip_range is not None and int(clip_range[1]) > int(clip_range[0]):
        item.setData(SCENE_ROLE_GROUP_START_MS, int(clip_range[0]))
        item.setData(SCENE_ROLE_GROUP_END_MS, int(clip_range[1]))
    else:
        item.setData(SCENE_ROLE_GROUP_START_MS, -1)
        item.setData(SCENE_ROLE_GROUP_END_MS, -1)
    item.setSizeHint(QtCore.QSize(170, 115))
    return item


def _finalize_batch_load(dialog, path: str, thumb_jobs: List[int], end_index: int) -> None:
    dialog.loaded_count = end_index
    total_count = len(dialog.all_scenes_data)
    dialog.lbl_status.setText(f"컷 {dialog.loaded_count} / {total_count}개 표시 ({dialog._scene_sort_label()})")
    if dialog.listw.count() > 0 and dialog.listw.currentItem() is None:
        dialog.listw.setCurrentRow(0)
    _enqueue_batch_thumbnails(dialog, path, thumb_jobs)
    dialog._update_scene_clip_button_enabled()


def _enqueue_batch_thumbnails(dialog, path: str, thumb_jobs: List[int]) -> None:
    if not thumb_jobs or bool(getattr(dialog, "_thumbnail_reload_suppressed", False)):
        return
    dialog.thumb_worker.add_jobs(path, thumb_jobs)


def _schedule_followup_batch_load(dialog) -> None:
    if dialog.loaded_count >= len(dialog.all_scenes_data):
        return
    scrollbar = dialog.listw.verticalScrollBar()
    if scrollbar.maximum() <= scrollbar.minimum() or scrollbar.value() >= int(scrollbar.maximum() * 0.9):
        dialog._schedule_load_check()


def _apply_cached_scene_thumbnail(dialog, item, ms: int) -> bool:
    cache_path = str(getattr(dialog, "_scene_thumb_cache_path", "") or "")
    if dialog._history_norm_path(cache_path) != dialog._history_norm_path(dialog.current_path):
        return False
    cache = getattr(dialog, "_scene_thumb_cache", None)
    if not isinstance(cache, dict):
        return False
    icon = cache.get(int(ms))
    if icon is None:
        return False
    try:
        item.setIcon(icon)
    except RuntimeError:
        return False
    return True
