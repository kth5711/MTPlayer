from typing import Callable, Optional
import os

from PyQt6 import QtCore

from scene_analysis.core.cache import cache_history_entries


def open_scene_dialog_with_options(host, scene_dialog_cls, logger) -> None:
    existing = _reusable_scene_dialog(host, logger)
    if existing is not None:
        _show_existing_dialog(existing)
        _schedule_auto_history_load(existing, host, logger)
        return
    dialog = scene_dialog_cls(host, parent=getattr(host, "window", lambda: None)())
    _remember_scene_dialog(host, dialog, logger)
    _bind_scene_dialog_cleanup(host, dialog, logger)
    dialog.show()
    _schedule_layout_sync_if_available(dialog, 0)
    _schedule_layout_sync_if_available(dialog, 140)
    _schedule_auto_history_load(dialog, host, logger)


def scene_cache_clear_for_current(host, scene_cache_clear_for_path: Callable[[str], None], logger) -> None:
    path = _current_media_path(host, "scene cache clear", logger)
    if path:
        scene_cache_clear_for_path(path)


def scene_cache_clear_all_public(scene_cache_clear_all: Callable[[], None]) -> None:
    scene_cache_clear_all()


def refilter_cache_clear_for_current(host, refilter_cache_clear_for_video: Callable[[str], None], logger) -> None:
    path = _current_media_path(host, "refilter cache clear", logger)
    if path:
        refilter_cache_clear_for_video(path)


def refilter_cache_clear_all_public(refilter_cache_clear_all: Callable[[], None]) -> None:
    refilter_cache_clear_all()


def _reusable_scene_dialog(host, logger):
    try:
        existing = getattr(host, "_sceneDlg", None)
        if existing is None:
            return None
        if bool(getattr(existing, "_thumb_close_pending", False)):
            return None
        return existing
    except (AttributeError, RuntimeError):
        logger.debug("existing scene dialog reuse skipped", exc_info=True)
        return None


def _show_existing_dialog(dialog) -> None:
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    _schedule_layout_sync_if_available(dialog, 0)
    _schedule_layout_sync_if_available(dialog, 140)


def _remember_scene_dialog(host, dialog, logger) -> None:
    try:
        host._sceneDlg = dialog
    except (AttributeError, RuntimeError):
        logger.debug("scene dialog host pointer set skipped", exc_info=True)


def _bind_scene_dialog_cleanup(host, dialog, logger) -> None:
    def _clear_scene_dialog(*_args):
        try:
            if getattr(host, "_sceneDlg", None) is dialog:
                host._sceneDlg = None
        except (AttributeError, RuntimeError):
            logger.debug("scene dialog host pointer clear skipped from callback", exc_info=True)

    _connect_dialog_cleanup(dialog, "finished", _clear_scene_dialog, "scene dialog finished signal connect skipped", logger)
    _connect_dialog_cleanup(dialog, "destroyed", _clear_scene_dialog, "scene dialog destroyed signal connect skipped", logger)


def _connect_dialog_cleanup(dialog, signal_name: str, slot, message: str, logger) -> None:
    try:
        getattr(dialog, signal_name).connect(slot)
    except RuntimeError:
        logger.debug(message, exc_info=True)


def _current_media_path(host, action_label: str, logger) -> Optional[str]:
    try:
        return host._current_media_path()
    except (AttributeError, RuntimeError):
        logger.debug("%s current media lookup failed", action_label, exc_info=True)
        return None


def _schedule_auto_history_load(dialog, host, logger) -> None:
    path = _current_media_path(host, "scene dialog auto history load", logger)
    if not path:
        return
    entry = _preferred_history_entry(path)
    if entry is None:
        return

    def _load() -> None:
        try:
            if not _should_auto_history_load(dialog, path):
                return
            if hasattr(dialog, "_request_cache_history_entry_load"):
                dialog._request_cache_history_entry_load(dict(entry))
                _schedule_layout_sync_if_available(dialog, 0)
                _schedule_layout_sync_if_available(dialog, 180)
                _schedule_result_thumbnail_kick(dialog, path)
        except Exception:
            logger.debug("scene dialog auto history load skipped", exc_info=True)

    QtCore.QTimer.singleShot(0, _load)


def _preferred_history_entry(path: str) -> Optional[dict]:
    rows = cache_history_entries(os.path.abspath(str(path or "")), current_only=True)
    for ent_type in ("refilter", "scene"):
        for entry in rows:
            if str(entry.get("type") or "") == ent_type:
                return dict(entry)
    return None


def _should_auto_history_load(dialog, path: str) -> bool:
    target = os.path.abspath(str(path or ""))
    current = os.path.abspath(str(getattr(dialog, "current_path", "") or ""))
    if current != target:
        return True
    try:
        listw = getattr(dialog, "listw", None)
        return bool(listw is not None and int(listw.count()) == 0)
    except Exception:
        return True


def _schedule_result_thumbnail_kick(dialog, path: str) -> None:
    target = os.path.abspath(str(path or ""))

    def _kick() -> None:
        try:
            current = os.path.abspath(str(getattr(dialog, "current_path", "") or ""))
            if current != target:
                return
            listw = getattr(dialog, "listw", None)
            all_rows = list(getattr(dialog, "all_scenes_data", []) or [])
            if listw is None or not all_rows:
                return
            if int(listw.count()) == 0 and hasattr(dialog, "_check_and_load_more"):
                dialog._check_and_load_more()
                return
            current_item = listw.currentItem()
            if current_item is None and int(listw.count()) > 0:
                listw.setCurrentRow(0)
                current_item = listw.currentItem()
            if current_item is None:
                return
            if hasattr(dialog, "_item_has_thumbnail") and dialog._item_has_thumbnail(current_item):
                return
            ms = int(current_item.data(QtCore.Qt.ItemDataRole.UserRole) or -1)
            if ms < 0:
                return
            if hasattr(dialog, "_reprioritize_thumbnails_from_ms"):
                dialog._reprioritize_thumbnails_from_ms(ms)
        except Exception:
            logger.debug("scene dialog auto thumbnail kick skipped", exc_info=True)

    QtCore.QTimer.singleShot(150, _kick)


def _schedule_layout_sync_if_available(dialog, delay_ms: int) -> None:
    try:
        scheduler = getattr(dialog, "_schedule_scene_layout_sync", None)
        if callable(scheduler):
            scheduler(int(delay_ms))
    except Exception:
        pass
