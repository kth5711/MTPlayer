import os
from typing import List

from PyQt6 import QtWidgets, QtCore

from .preview_items import PREVIEW_ROLE_BASE_MS, PREVIEW_ROLE_REL_STEP
from .preview_ranges import scene_frame_times_for_ms, scene_frame_times_for_range
from .preview_runtime import clear_scene_frame_preview
from .preview_selection import scene_group_end_ms, selected_scene_ms_list
from .ui_results import SCENE_FRAME_PREVIEW_ITEM_SIZE


def _preview_selection_context(dialog):
    scene_ms_list = selected_scene_ms_list(dialog)
    if not scene_ms_list:
        return None, "프레임셋: 결과 컷을 먼저 선택하세요."
    if not dialog.current_path or not os.path.exists(dialog.current_path):
        return None, "프레임셋: 현재 영상 경로를 찾을 수 없습니다."
    duration_sec = int(dialog.spn_scene_frame_secs.value() if hasattr(dialog, "spn_scene_frame_secs") else 3)
    include_prev = bool(dialog.chk_scene_frame_prev.isChecked() if hasattr(dialog, "chk_scene_frame_prev") else False)
    return (scene_ms_list, duration_sec, include_prev), None


def _preview_time_list(dialog, scene_ms_list: List[int], duration_sec: int, include_prev: bool):
    multi_mode = len(scene_ms_list) >= 2
    single_group_mode = False
    if multi_mode:
        first_ms = int(scene_ms_list[0])
        last_ms = int(scene_ms_list[-1])
        last_end_ms = scene_group_end_ms(dialog, last_ms)
        if last_end_ms is None:
            last_end_ms = dialog._scene_end_ms(last_ms, fallback_sec=duration_sec)
        return scene_frame_times_for_range(first_ms, last_end_ms, duration_sec, include_prev=include_prev), multi_mode, single_group_mode
    scene_ms = int(scene_ms_list[0])
    group_end_ms = scene_group_end_ms(dialog, scene_ms)
    if group_end_ms is not None:
        single_group_mode = True
        return scene_frame_times_for_range(scene_ms, group_end_ms, duration_sec, include_prev=include_prev), multi_mode, single_group_mode
    return scene_frame_times_for_ms(scene_ms, duration_sec, include_prev=include_prev), multi_mode, single_group_mode


def _preview_item_title(dialog, t_ms: int, scene_ms_list: List[int], include_prev: bool, multi_mode: bool):
    base_label = dialog._format_ms_mmss(t_ms)
    if multi_mode:
        return base_label, f"{base_label} | {t_ms}ms"
    delta_ms = int(t_ms) - int(scene_ms_list[0])
    rel = f"{delta_ms / 1000.0:+.1f}s"
    if include_prev and delta_ms == 0:
        return f"{base_label} [기준]", f"{base_label} | 기준대비 {rel} | {t_ms}ms"
    return f"{base_label} ({rel})", f"{base_label} | 기준대비 {rel} | {t_ms}ms"


def _add_preview_items(dialog, times_ms: List[int], scene_ms_list: List[int], include_prev: bool, multi_mode: bool) -> List[int]:
    preview_jobs: List[int] = []
    for t_ms in times_ms:
        title, tooltip = _preview_item_title(dialog, t_ms, scene_ms_list, include_prev, multi_mode)
        item = QtWidgets.QListWidgetItem(title)
        item.setToolTip(tooltip)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, int(t_ms))
        item.setData(PREVIEW_ROLE_BASE_MS, int(t_ms))
        item.setData(PREVIEW_ROLE_REL_STEP, 0)
        item.setSizeHint(SCENE_FRAME_PREVIEW_ITEM_SIZE)
        dialog.lst_scene_frame_preview.addItem(item)
        preview_jobs.append(int(t_ms))
    return preview_jobs


def _queue_preview_jobs(dialog, preview_jobs: List[int]) -> None:
    if hasattr(dialog, "_preview_thumb_expected_ms"):
        dialog._preview_thumb_expected_ms = set(int(ms) for ms in preview_jobs)
    worker = getattr(dialog, "preview_thumb_worker", None)
    if worker is None or not preview_jobs:
        return
    try:
        worker.clear_jobs()
    except Exception:
        pass
    try:
        worker.add_jobs(dialog.current_path, preview_jobs)
    except Exception:
        pass


def _preview_status_text(times_ms: List[int], duration_sec: int, include_prev: bool, multi_mode: bool, single_group_mode: bool, scene_count: int) -> str:
    if multi_mode:
        mode_text = "앞/구간/뒤+채움" if include_prev else "시작/중간/끝+채움"
        return f"선택컷 프레임셋: {len(times_ms)}장 ({duration_sec}s, 다중 {scene_count}컷, {mode_text})"
    if single_group_mode:
        mode_text = "앞/묶음구간/뒤(시작/중간/끝+채움)" if include_prev else "묶음구간(시작/중간/끝+채움)"
    else:
        mode_text = "앞/뒤(시작/중간/끝+채움)" if include_prev else "기본(시작/중간/끝+채움)"
    return f"선택컷 프레임셋: {len(times_ms)}장 ({duration_sec}s, {mode_text})"


def show_selected_scene_frame_set(dialog) -> None:
    clear_scene_frame_preview(dialog)
    context, error_text = _preview_selection_context(dialog)
    if context is None:
        dialog.lbl_status.setText(str(error_text or "프레임셋: 결과 컷을 먼저 선택하세요."))
        return
    scene_ms_list, duration_sec, include_prev = context
    times_ms, multi_mode, single_group_mode = _preview_time_list(dialog, scene_ms_list, duration_sec, include_prev)
    preview_jobs = _add_preview_items(dialog, times_ms, scene_ms_list, include_prev, multi_mode)
    _queue_preview_jobs(dialog, preview_jobs)
    dialog.lbl_status.setText(
        _preview_status_text(times_ms, duration_sec, include_prev, multi_mode, single_group_mode, len(scene_ms_list))
    )
