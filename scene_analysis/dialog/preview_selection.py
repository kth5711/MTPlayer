from typing import List, Optional

from PyQt6 import QtCore

from .preview_items import SCENE_ROLE_GROUP_END_MS, SCENE_ROLE_GROUP_START_MS


def is_scene_frame_preview_enabled(dialog) -> bool:
    if not hasattr(dialog, "chk_scene_frame_preview"):
        return False
    return bool(dialog.chk_scene_frame_preview.isChecked())


def scene_frame_step_ms(dialog) -> int:
    fps = 0.0
    try:
        if hasattr(dialog.host, "mediaplayer") and hasattr(dialog.host.mediaplayer, "get_fps"):
            fps = float(dialog.host.mediaplayer.get_fps() or 0.0)
    except Exception:
        fps = 0.0
    if fps > 1e-6:
        return max(1, int(round(1000.0 / fps)))
    return 33


def selected_scene_ms(dialog) -> Optional[int]:
    item = dialog.listw.currentItem() if hasattr(dialog, "listw") else None
    if item is None:
        return None
    ms = _scene_anchor_ms(item)
    return ms if ms >= 0 else None


def selected_scene_ms_list(dialog) -> List[int]:
    items = list(dialog.listw.selectedItems() or []) if hasattr(dialog, "listw") else []
    out = _scene_anchor_ms_list(items)
    if out:
        return out
    current = selected_scene_ms(dialog)
    return [int(current)] if current is not None else []


def scene_group_end_ms(dialog, scene_start_ms: int) -> Optional[int]:
    start_ms = int(scene_start_ms)
    item = dialog._item_by_ms.get(start_ms) if hasattr(dialog, "_item_by_ms") else None
    if item is None and hasattr(dialog, "listw"):
        current = dialog.listw.currentItem()
        if current is not None and _scene_anchor_ms(current) == start_ms:
            item = current
    if item is None:
        return None
    try:
        end_ms = int(item.data(SCENE_ROLE_GROUP_END_MS) or -1)
    except Exception:
        end_ms = -1
    return int(end_ms) if end_ms > start_ms else None


def _scene_anchor_ms(item) -> int:
    try:
        ms = int(item.data(SCENE_ROLE_GROUP_START_MS) or -1)
        if ms >= 0:
            return ms
        return int(item.data(QtCore.Qt.ItemDataRole.UserRole) or -1)
    except Exception:
        return -1


def _scene_anchor_ms_list(items) -> List[int]:
    out: List[int] = []
    seen = set()
    for item in items or []:
        ms = _scene_anchor_ms(item)
        if ms < 0 or ms in seen:
            continue
        seen.add(ms)
        out.append(int(ms))
    out.sort()
    return out
