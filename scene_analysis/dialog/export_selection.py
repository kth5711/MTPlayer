from typing import List, Optional, Tuple

from PyQt6 import QtCore, QtWidgets

from .preview_items import SCENE_ROLE_GROUP_END_MS, SCENE_ROLE_GROUP_START_MS


def selected_ms_from_items(_dialog, items: List[QtWidgets.QListWidgetItem]) -> List[int]:
    out: List[int] = []
    seen = set()
    for it in (items or []):
        try:
            ms = int(it.data(SCENE_ROLE_GROUP_START_MS) or -1)
            if ms < 0:
                ms = int(it.data(QtCore.Qt.ItemDataRole.UserRole) or -1)
        except Exception:
            ms = -1
        if ms < 0 or ms in seen:
            continue
        seen.add(ms)
        out.append(ms)
    out.sort()
    return out


def _selected_preview_ms(dialog) -> List[int]:
    items = list(dialog.lst_scene_frame_preview.selectedItems() or []) \
        if hasattr(dialog, "lst_scene_frame_preview") else []
    return selected_ms_from_items(dialog, items)


def _selected_scene_ms(dialog) -> List[int]:
    items = list(dialog.listw.selectedItems() or []) if hasattr(dialog, "listw") else []
    return selected_ms_from_items(dialog, items)


def _selected_preview_range_ms(dialog) -> Optional[Tuple[int, int]]:
    preview_ms = _selected_preview_ms(dialog)
    if len(preview_ms) < 2:
        return None
    return int(preview_ms[0]), int(preview_ms[-1])


def selected_clip_range_ms(dialog) -> Optional[Tuple[int, int]]:
    preview_range = _selected_preview_range_ms(dialog)
    if preview_range is not None:
        return preview_range
    preview_ms = _selected_preview_ms(dialog)
    scene_ms = _selected_scene_ms(dialog)
    if not scene_ms:
        cur = dialog._selected_scene_ms()
        if cur is not None:
            scene_ms = [int(cur)]
    merged = sorted(set(preview_ms + scene_ms))
    if len(merged) < 2:
        return None
    return int(merged[0]), int(merged[-1])


def _selected_exact_manual_range_ms(dialog) -> Optional[Tuple[int, int]]:
    merged = sorted(set(_selected_preview_ms(dialog) + _selected_scene_ms(dialog)))
    if len(merged) != 2:
        return None
    start_ms, end_ms = int(merged[0]), int(merged[1])
    if end_ms <= start_ms:
        return None
    return start_ms, end_ms


def selected_grouped_scene_clip_ranges(dialog) -> List[Tuple[int, int]]:
    items = list(dialog.listw.selectedItems() or []) if hasattr(dialog, "listw") else []
    if not items and hasattr(dialog, "listw"):
        cur = dialog.listw.currentItem()
        if cur is not None:
            items = [cur]
    out: List[Tuple[int, int]] = []
    seen = set()
    for it in items:
        try:
            start_ms = int(it.data(SCENE_ROLE_GROUP_START_MS) or -1)
            if start_ms < 0:
                start_ms = int(it.data(QtCore.Qt.ItemDataRole.UserRole) or -1)
            end_ms = int(it.data(SCENE_ROLE_GROUP_END_MS) or -1)
        except Exception:
            continue
        if start_ms < 0 or end_ms <= start_ms:
            continue
        key = (start_ms, end_ms)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    out.sort(key=lambda x: (int(x[0]), int(x[1])))
    return out


def selected_clip_ranges_for_save(dialog) -> List[Tuple[int, int]]:
    preview_range = _selected_preview_range_ms(dialog)
    if preview_range is not None:
        start_ms, end_ms = int(preview_range[0]), int(preview_range[1])
        if end_ms > start_ms:
            return [(start_ms, end_ms)]
    grouped = selected_grouped_scene_clip_ranges(dialog)
    if grouped:
        return grouped
    pair = selected_clip_range_ms(dialog)
    if pair is None:
        return []
    start_ms, end_ms = int(pair[0]), int(pair[1])
    if end_ms <= start_ms:
        return []
    return [(start_ms, end_ms)]


def _selected_scene_ab_range_ms(dialog) -> Optional[Tuple[int, int]]:
    manual_range = _selected_preview_range_ms(dialog)
    if manual_range is not None:
        start_ms, end_ms = int(manual_range[0]), int(manual_range[1])
        if end_ms > start_ms:
            return start_ms, end_ms
    grouped_ranges = selected_grouped_scene_clip_ranges(dialog)
    if len(grouped_ranges) == 1:
        st, ed = grouped_ranges[0]
        if int(ed) > int(st):
            return int(st), int(ed)
    pair = selected_clip_range_ms(dialog)
    if pair is None:
        return None
    start_ms, end_ms = int(pair[0]), int(pair[1])
    if end_ms <= start_ms:
        return None
    return start_ms, end_ms


def _get_single_selected_scene_gif_range(dialog) -> Optional[Tuple[int, int]]:
    manual_range = _selected_preview_range_ms(dialog)
    if manual_range is not None:
        start_ms, end_ms = int(manual_range[0]), int(manual_range[1])
        if end_ms > start_ms:
            return start_ms, end_ms
    grouped_ranges = selected_grouped_scene_clip_ranges(dialog)
    if len(grouped_ranges) == 1:
        st, ed = grouped_ranges[0]
        if int(ed) > int(st):
            return int(st), int(ed)
    if len(grouped_ranges) >= 2:
        return None
    return _selected_exact_manual_range_ms(dialog)


def selected_scene_ms_list_for_save(dialog) -> List[int]:
    preview_ms = _selected_preview_ms(dialog)
    if preview_ms:
        return preview_ms
    items = list(dialog.listw.selectedItems() or [])
    if not items:
        it = dialog.listw.currentItem()
        if it is not None:
            items = [it]
    return selected_ms_from_items(dialog, items)
