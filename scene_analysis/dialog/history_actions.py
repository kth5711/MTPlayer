import logging

from PyQt6 import QtWidgets, QtCore

from scene_analysis.core.cache import remove_cache_history_entries

from .history_apply_refilter import load_refilter_cache_entry, load_siglip_feature_cache_entry
from .history_apply_scene import load_scene_cache_entry
from .history_refresh import refresh_cache_history_dialog
from .history_shared import cache_history_selected_entries

logger = logging.getLogger(__name__)


def schedule_cache_history_refresh(dialog) -> None:
    if bool(getattr(dialog, "_cache_hist_refresh_scheduled", False)):
        return
    dialog._cache_hist_refresh_scheduled = True
    QtCore.QTimer.singleShot(0, lambda: _run_history_refresh(dialog))


def _run_history_refresh(dialog) -> None:
    dialog._cache_hist_refresh_scheduled = False
    refresh_cache_history_dialog(dialog)


def dispatch_cache_history_entry_load(dialog, ent: dict) -> None:
    ent_type = str(ent.get("type") or "")
    if ent_type == "scene":
        load_scene_cache_entry(dialog, ent)
        return
    if ent_type == "refilter":
        load_refilter_cache_entry(dialog, ent)
        return
    if ent_type == "siglip_feature":
        load_siglip_feature_cache_entry(dialog, ent)
        return
    QtWidgets.QMessageBox.information(dialog, "알림", "지원하지 않는 결과기록 타입입니다.")


def request_cache_history_entry_load(dialog, ent: dict) -> None:
    if not isinstance(ent, dict):
        return
    payload = dict(ent)
    if bool(getattr(dialog, "_cache_hist_loading", False)):
        _queue_pending_history_entry(dialog, payload)
        return
    _load_history_entry(dialog, payload)
    _load_pending_history_entry(dialog)


def _queue_pending_history_entry(dialog, payload: dict) -> None:
    dialog._cache_hist_pending_entry = payload
    dialog.lbl_status.setText("결과기록 로드 대기: 마지막 선택 항목으로 갱신")


def _load_history_entry(dialog, payload: dict) -> None:
    dialog._cache_hist_loading = True
    loaded = False
    try:
        dispatch_cache_history_entry_load(dialog, payload)
        loaded = True
    except Exception as exc:
        logger.warning("cache history entry load failed: %s", payload.get("type"), exc_info=True)
        QtWidgets.QMessageBox.warning(dialog, "오류", f"결과기록 로드 중 오류: {exc}")
    finally:
        dialog._cache_hist_loading = False
        schedule_cache_history_refresh(dialog)
    if loaded:
        _close_history_dialog_after_load_if_needed(dialog)


def _load_pending_history_entry(dialog) -> None:
    pending = dialog._cache_hist_pending_entry
    dialog._cache_hist_pending_entry = None
    if isinstance(pending, dict):
        QtCore.QTimer.singleShot(0, lambda p=dict(pending): request_cache_history_entry_load(dialog, p))


def _close_history_dialog_after_load_if_needed(dialog) -> None:
    chk = getattr(dialog, "_cache_hist_chk_close_after_load", None)
    dlg = getattr(dialog, "_cache_hist_dialog", None)
    try:
        should_close = bool(chk is not None and chk.isChecked())
    except Exception:
        should_close = False
    if not should_close or dlg is None:
        return
    QtCore.QTimer.singleShot(0, dlg.close)


def load_selected_cache_history_entry(dialog) -> None:
    rows = cache_history_selected_entries(dialog)
    if not rows:
        return
    if len(rows) != 1:
        QtWidgets.QMessageBox.information(dialog, "알림", "로드는 1개 기록만 선택할 수 있습니다.")
        return
    request_cache_history_entry_load(dialog, rows[0])


def delete_selected_cache_history_entries(dialog) -> None:
    rows = cache_history_selected_entries(dialog)
    if not rows:
        return
    if _confirm_history_delete(dialog, len(rows)) != _yes_button():
        return
    removed, failed = remove_cache_history_entries(rows)
    dialog.lbl_status.setText(f"결과기록 삭제: {removed}개 완료, {failed}개 실패" if failed > 0 else f"결과기록 삭제: {removed}개 완료")
    refresh_cache_history_dialog(dialog)


def _confirm_history_delete(dialog, count: int):
    return QtWidgets.QMessageBox.question(
        dialog,
        "결과기록 삭제",
        f"선택한 {count}개 기록을 삭제할까요?",
        _yes_button() | _no_button(),
        _no_button(),
    )


def _yes_button():
    return getattr(QtWidgets.QMessageBox, "Yes", QtWidgets.QMessageBox.StandardButton.Yes)


def _no_button():
    return getattr(QtWidgets.QMessageBox, "No", QtWidgets.QMessageBox.StandardButton.No)
