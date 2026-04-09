from typing import Optional, Tuple

from PyQt6 import QtWidgets

from .export_common import _existing_scene_path, _show_scene_busy_message
from .export_selection import (
    _selected_scene_ab_range_ms,
    _selected_exact_manual_range_ms,
    selected_clip_range_ms,
    selected_grouped_scene_clip_ranges,
    selected_scene_ms_list_for_save,
)


def _bookmark_action_enabled(dialog) -> bool:
    if getattr(dialog, "worker", None) is not None:
        return False
    if bool(getattr(dialog, "_clip_worker_busy", False)):
        return False
    rw = getattr(dialog, "refilter_worker", None)
    if rw is not None and rw.isRunning():
        return False
    return bool(selected_scene_ms_list_for_save(dialog))


def _apply_scene_tooltips(dialog, grouped_ranges) -> None:
    if not grouped_ranges:
        if hasattr(dialog, "btn_scene_set_ab"):
            dialog.btn_scene_set_ab.setToolTip(dialog._scene_ab_tooltip_manual)
        dialog.btn_scene_clip_save.setToolTip(dialog._scene_clip_tooltip_manual)
        if hasattr(dialog, "btn_scene_gif_save"):
            dialog.btn_scene_gif_save.setToolTip(dialog._scene_gif_tooltip_manual)
        return
    if hasattr(dialog, "btn_scene_set_ab"):
        dialog.btn_scene_set_ab.setToolTip(dialog._scene_ab_tooltip_group)
    dialog.btn_scene_clip_save.setToolTip(dialog._scene_clip_tooltip_group)
    if hasattr(dialog, "btn_scene_gif_save"):
        tooltip = dialog._scene_gif_tooltip_single if len(grouped_ranges) == 1 else dialog._scene_gif_tooltip_multi
        dialog.btn_scene_gif_save.setToolTip(tooltip)


def _set_scene_merge_state(dialog, enabled: bool, grouped_ranges) -> None:
    if not hasattr(dialog, "chk_scene_clip_merge"):
        return
    can_merge_group = enabled and len(grouped_ranges) >= 2
    dialog.chk_scene_clip_merge.setEnabled(can_merge_group)
    if not can_merge_group:
        dialog.chk_scene_clip_merge.setChecked(False)


def update_scene_clip_button_enabled(dialog) -> None:
    if not hasattr(dialog, "btn_scene_clip_save"):
        return
    grouped_ranges = selected_grouped_scene_clip_ranges(dialog)
    enabled = bool(grouped_ranges or (selected_clip_range_ms(dialog) is not None))
    enabled = enabled and (not _show_scene_busy_message_state(dialog))
    dialog.btn_scene_clip_save.setEnabled(enabled)
    ab_range = _selected_scene_ab_range_ms(dialog)
    if hasattr(dialog, "btn_scene_set_ab"):
        dialog.btn_scene_set_ab.setEnabled(bool(enabled and (ab_range is not None)))
    if hasattr(dialog, "btn_scene_gif_save"):
        gif_enabled = bool(enabled and ((_selected_exact_manual_range_ms(dialog) is not None) or (len(grouped_ranges) == 1)))
        dialog.btn_scene_gif_save.setEnabled(gif_enabled)
    _set_scene_merge_state(dialog, enabled, grouped_ranges)
    if hasattr(dialog, "btn_scene_bookmark_add"):
        dialog.btn_scene_bookmark_add.setEnabled(_bookmark_action_enabled(dialog))
    _apply_scene_tooltips(dialog, grouped_ranges)


def _show_scene_busy_message_state(dialog) -> bool:
    if getattr(dialog, "worker", None) is not None:
        return True
    rw = getattr(dialog, "refilter_worker", None)
    if rw is not None and rw.isRunning():
        return True
    return bool(getattr(dialog, "_clip_worker_busy", False))


def on_clip_worker_busy_changed(dialog, busy: bool) -> None:
    dialog._clip_worker_busy = bool(busy)
    if not bool(busy):
        update_scene_clip_button_enabled(dialog)
        return
    for name in ("btn_scene_set_ab", "btn_scene_clip_save", "btn_scene_gif_save", "chk_scene_clip_merge"):
        widget = getattr(dialog, name, None)
        if widget is not None:
            widget.setEnabled(False)


def _selected_ab_range_or_warn(dialog) -> Optional[Tuple[int, int]]:
    clip_range = _selected_scene_ab_range_ms(dialog)
    if clip_range is not None:
        return clip_range
    QtWidgets.QMessageBox.information(
        dialog,
        "알림",
        "A/B로 잡을 구간을 선택하세요.\n- 구간묶음 씬 1개 선택\n- 또는 프레임셋/씬 결과에서 서로 다른 2개 시점 선택",
    )
    return None


def _apply_ab_range_to_host(dialog, start_ms: int, end_ms: int) -> bool:
    host = getattr(dialog, "host", None)
    if host is None or not hasattr(host, "set_ab_range_ms"):
        QtWidgets.QMessageBox.warning(dialog, "오류", "현재 타일이 A/B 구간 설정을 지원하지 않습니다.")
        return False
    try:
        ok = bool(host.set_ab_range_ms(start_ms, end_ms, seek_to_start=True))
    except Exception as e:
        QtWidgets.QMessageBox.warning(dialog, "실패", f"A/B 구간 설정 실패: {e}")
        return False
    if ok:
        return True
    QtWidgets.QMessageBox.warning(dialog, "실패", "타일 A/B 구간을 설정하지 못했습니다.")
    return False


def set_selected_scene_range_ab(dialog) -> None:
    if _show_scene_busy_message(dialog):
        return
    path = _existing_scene_path(dialog, allow_host_fallback=True)
    if not path:
        QtWidgets.QMessageBox.warning(dialog, "오류", "현재 영상 경로를 찾을 수 없습니다.")
        return
    if hasattr(dialog, "_ensure_history_video_loaded"):
        try:
            if not dialog._ensure_history_video_loaded(path):
                return
        except Exception:
            pass
    clip_range = _selected_ab_range_or_warn(dialog)
    if clip_range is None:
        return
    start_ms, end_ms = int(clip_range[0]), int(clip_range[1])
    if not _apply_ab_range_to_host(dialog, start_ms, end_ms):
        return
    try:
        start_txt = dialog.host._ms_to_hms(start_ms)
        end_txt = dialog.host._ms_to_hms(end_ms)
    except Exception:
        start_txt = str(start_ms)
        end_txt = str(end_ms)
    dialog.lbl_status.setText(f"타일 A/B 설정: {start_txt} ~ {end_txt}")
