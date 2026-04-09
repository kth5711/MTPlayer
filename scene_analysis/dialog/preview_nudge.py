from typing import List, Optional

from PyQt6 import QtWidgets, QtCore

from .preview_items import (
    PREVIEW_ROLE_BASE_MS,
    PREVIEW_ROLE_REL_STEP,
    find_preview_insert_row,
    find_preview_item_by_base_rel,
    find_preview_item_by_ms,
    set_preview_item_rel_text,
)
from .preview_selection import scene_frame_step_ms


def _normalized_nudge_values(step_frames: int, repeat_count: int, jump_step_frames: int) -> Optional[tuple[int, int, int]]:
    try:
        repeat = max(1, min(10, int(repeat_count)))
        jump = max(1, min(10, int(jump_step_frames)))
        step = int(step_frames)
    except Exception:
        return None
    if step == 0:
        return None
    return step, repeat, jump


def _selected_preview_items(dialog) -> List[QtWidgets.QListWidgetItem]:
    items = list(dialog.lst_scene_frame_preview.selectedItems() or [])
    if items:
        return items
    current = dialog.lst_scene_frame_preview.currentItem()
    return [current] if current is not None else []


def _preview_item_context(item: QtWidgets.QListWidgetItem) -> Optional[tuple[int, int, int]]:
    try:
        old_ms = int(item.data(QtCore.Qt.ItemDataRole.UserRole) or -1)
        base_ms = int(item.data(PREVIEW_ROLE_BASE_MS) or old_ms)
        rel_step = int(item.data(PREVIEW_ROLE_REL_STEP) or 0)
    except Exception:
        return None
    if old_ms < 0:
        return None
    return old_ms, base_ms, rel_step


def _create_preview_item(dialog, base_ms: int, new_ms: int, new_rel_step: int) -> QtWidgets.QListWidgetItem:
    item = QtWidgets.QListWidgetItem("")
    item.setData(QtCore.Qt.ItemDataRole.UserRole, int(new_ms))
    item.setData(PREVIEW_ROLE_BASE_MS, int(base_ms))
    item.setData(PREVIEW_ROLE_REL_STEP, int(new_rel_step))
    set_preview_item_rel_text(dialog, item, new_ms, new_rel_step)
    item.setSizeHint(QtCore.QSize(126, 92))
    return item


def _resolve_preview_variant(dialog, base_ms: int, new_rel_step: int, new_ms: int):
    existing = find_preview_item_by_base_rel(dialog, base_ms, new_rel_step)
    if existing is not None:
        return existing, False
    existing = find_preview_item_by_ms(dialog, new_ms)
    if existing is not None:
        return existing, False
    item = _create_preview_item(dialog, base_ms, new_ms, new_rel_step)
    row = max(0, int(find_preview_insert_row(dialog, base_ms, new_rel_step)))
    dialog.lst_scene_frame_preview.insertItem(row, item)
    return item, True


def _queue_preview_jobs(dialog, added_jobs: List[int]) -> None:
    if hasattr(dialog, "_preview_thumb_expected_ms"):
        dialog._preview_thumb_expected_ms.update(int(ms) for ms in added_jobs)
    worker = getattr(dialog, "preview_thumb_worker", None)
    if worker is None or not added_jobs:
        return
    try:
        worker.add_jobs(dialog.current_path, added_jobs)
    except Exception:
        pass


def _select_new_preview_items(dialog, items: List[QtWidgets.QListWidgetItem]) -> None:
    try:
        dialog.lst_scene_frame_preview.clearSelection()
        for item in items:
            item.setSelected(True)
        dialog.lst_scene_frame_preview.scrollToItem(items[-1])
    except Exception:
        pass


def _append_nudged_variants(
    dialog,
    base_ms: int,
    rel_step: int,
    step: int,
    repeat: int,
    jump: int,
    added_items: List[QtWidgets.QListWidgetItem],
    added_jobs: List[int],
) -> int:
    created_count = 0
    for nth in range(1, repeat + 1):
        new_rel_step = int(rel_step + (step * jump * nth))
        new_ms = max(0, int(base_ms + new_rel_step * scene_frame_step_ms(dialog)))
        resolved, created = _resolve_preview_variant(dialog, base_ms, new_rel_step, new_ms)
        added_items.append(resolved)
        if created:
            added_jobs.append(int(new_ms))
            created_count += 1
    return created_count


def nudge_selected_preview_frames(dialog, step_frames: int, repeat_count: int = 1, jump_step_frames: int = 1) -> None:
    values = _normalized_nudge_values(step_frames, repeat_count, jump_step_frames)
    items = _selected_preview_items(dialog) if hasattr(dialog, "lst_scene_frame_preview") else []
    if values is None or not items:
        if not items:
            dialog.lbl_status.setText("프레임셋: 미세조정할 프레임을 선택하세요.")
        return
    step, repeat, jump = values
    added_items: List[QtWidgets.QListWidgetItem] = []
    added_jobs: List[int] = []
    added = 0
    for item in items:
        context = _preview_item_context(item)
        if context is None:
            continue
        old_ms, base_ms, rel_step = context
        item.setData(PREVIEW_ROLE_BASE_MS, int(base_ms))
        set_preview_item_rel_text(dialog, item, old_ms, rel_step)
        added += _append_nudged_variants(dialog, base_ms, rel_step, step, repeat, jump, added_items, added_jobs)
    if added <= 0:
        return
    _queue_preview_jobs(dialog, added_jobs)
    _select_new_preview_items(dialog, added_items)
    dialog.lbl_status.setText(f"프레임 추가: {added}개 ({int(step * jump):+d}f x{int(repeat)}, 기준 0)")
