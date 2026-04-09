from typing import Optional

from PyQt6 import QtWidgets, QtCore

from .preview_selection import is_scene_frame_preview_enabled, selected_scene_ms


def _stop_preview_refresh_timer(dialog) -> None:
    timer = getattr(dialog, "_scene_frame_preview_timer", None)
    if timer is None:
        return
    try:
        if timer.isActive():
            timer.stop()
    except Exception:
        pass


def _clear_preview_worker_jobs(dialog) -> None:
    worker = getattr(dialog, "preview_thumb_worker", None)
    if worker is None:
        return
    try:
        worker.clear_jobs()
    except Exception:
        pass


def clear_scene_frame_preview(dialog) -> None:
    if not hasattr(dialog, "lst_scene_frame_preview"):
        return
    _stop_preview_refresh_timer(dialog)
    if hasattr(dialog, "_preview_thumb_expected_ms"):
        dialog._preview_thumb_expected_ms = set()
    _clear_preview_worker_jobs(dialog)
    dialog.lst_scene_frame_preview.clear()
    dialog._update_scene_clip_button_enabled()


def refresh_scene_frame_preview_if_enabled(dialog) -> None:
    if is_scene_frame_preview_enabled(dialog):
        from .preview_display import show_selected_scene_frame_set

        show_selected_scene_frame_set(dialog)
        return
    clear_scene_frame_preview(dialog)
    if selected_scene_ms(dialog) is None:
        dialog.lbl_status.setText("프레임셋: 결과 컷을 먼저 선택하세요.")
    else:
        dialog.lbl_status.setText("프레임셋: [프레임셋 보기] 체크 시 자동 생성됩니다.")


def on_scene_frame_preview_toggled(dialog, _state: int) -> None:
    refresh_scene_frame_preview_if_enabled(dialog)


def disable_scene_frame_preview_on_keyboard_nav(dialog) -> None:
    if not is_scene_frame_preview_enabled(dialog):
        return
    blocker = QtCore.QSignalBlocker(dialog.chk_scene_frame_preview)
    dialog.chk_scene_frame_preview.setChecked(False)
    del blocker
    clear_scene_frame_preview(dialog)
    dialog.lbl_status.setText("프레임셋: 키보드 이동 감지로 자동 보기 해제")


def go_scene_frame_from_preview(dialog, item: Optional[QtWidgets.QListWidgetItem] = None) -> None:
    if item is None:
        item = dialog.lst_scene_frame_preview.currentItem()
    if item is None:
        return
    try:
        target_ms = int(item.data(QtCore.Qt.ItemDataRole.UserRole) or 0)
    except Exception:
        target_ms = 0
    try:
        playing = False
        if hasattr(dialog.host, "mediaplayer") and hasattr(dialog.host.mediaplayer, "is_playing"):
            playing = dialog.host.mediaplayer.is_playing()
        dialog.host.seek_ms(max(0, int(target_ms)), play=playing)
    except Exception:
        try:
            dialog.host.seek_ms(max(0, int(target_ms)), play=True)
        except Exception:
            pass
