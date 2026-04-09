from typing import Optional

from PyQt6 import QtWidgets, QtCore


PREVIEW_ROLE_BASE_MS = int(QtCore.Qt.ItemDataRole.UserRole) + 100
PREVIEW_ROLE_REL_STEP = int(QtCore.Qt.ItemDataRole.UserRole) + 101
SCENE_ROLE_GROUP_END_MS = int(QtCore.Qt.ItemDataRole.UserRole) + 102
SCENE_ROLE_GROUP_START_MS = int(QtCore.Qt.ItemDataRole.UserRole) + 103


def preview_rel_text(rel_step: int) -> str:
    value = float(rel_step) / 10.0
    if abs(value) < 1e-9:
        return "0"
    return f"{value:.1f}"


def set_preview_item_rel_text(dialog, it: QtWidgets.QListWidgetItem, ms: int, rel_step: int) -> None:
    base_label = dialog._format_ms_mmss(ms)
    rel_txt = preview_rel_text(rel_step)
    it.setText(f"{base_label} ({rel_txt})")
    it.setToolTip(f"{base_label} | {ms}ms | 상대 {rel_txt}")
    it.setData(PREVIEW_ROLE_REL_STEP, int(rel_step))


def _preview_list_count(dialog) -> int:
    if not hasattr(dialog, "lst_scene_frame_preview"):
        return 0
    return int(dialog.lst_scene_frame_preview.count())


def find_preview_item_by_base_rel(dialog, base_ms: int, rel_step: int) -> Optional[QtWidgets.QListWidgetItem]:
    for index in range(_preview_list_count(dialog)):
        item = dialog.lst_scene_frame_preview.item(index)
        if item is None:
            continue
        try:
            base = int(item.data(PREVIEW_ROLE_BASE_MS) or -1)
            rel = int(item.data(PREVIEW_ROLE_REL_STEP) or 0)
        except Exception:
            continue
        if base == int(base_ms) and rel == int(rel_step):
            return item
    return None


def find_preview_item_by_ms(dialog, ms: int) -> Optional[QtWidgets.QListWidgetItem]:
    for index in range(_preview_list_count(dialog)):
        item = dialog.lst_scene_frame_preview.item(index)
        if item is None:
            continue
        try:
            item_ms = int(item.data(QtCore.Qt.ItemDataRole.UserRole) or -1)
        except Exception:
            item_ms = -1
        if item_ms == int(ms):
            return item
    return None


def find_preview_insert_row(dialog, base_ms: int, rel_step: int) -> int:
    first_same = None
    last_same = None
    for index in range(_preview_list_count(dialog)):
        item = dialog.lst_scene_frame_preview.item(index)
        if item is None:
            continue
        try:
            base = int(item.data(PREVIEW_ROLE_BASE_MS) or -1)
            rel = int(item.data(PREVIEW_ROLE_REL_STEP) or 0)
        except Exception:
            continue
        if base != int(base_ms):
            continue
        first_same = index if first_same is None else first_same
        last_same = index
        if rel > int(rel_step):
            return index
    if last_same is not None:
        return int(last_same) + 1
    if first_same is not None:
        return int(first_same)
    return _preview_list_count(dialog)
