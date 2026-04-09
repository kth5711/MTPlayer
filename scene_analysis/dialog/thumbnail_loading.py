from typing import List, Optional
import logging

from PyQt6 import QtCore, QtGui, QtWidgets


logger = logging.getLogger(__name__)


def schedule_thumbnail_resume(dialog, debounce_ms: int = 280) -> None:
    timer = getattr(dialog, "_thumbnail_resume_timer", None)
    if timer is None:
        dialog._thumbnail_reload_suppressed = False
        return
    timer.setInterval(max(1, int(debounce_ms)))
    timer.start()


def resume_thumbnail_loading(dialog) -> None:
    if not bool(getattr(dialog, "_thumbnail_reload_suppressed", False)):
        return
    dialog._thumbnail_reload_suppressed = False
    path = str(getattr(dialog, "current_path", "") or "")
    if not path:
        return
    jobs = _list_thumbnail_jobs(dialog)
    if not jobs:
        return
    try:
        dialog.thumb_worker.clear_jobs()
    except RuntimeError:
        logger.debug("thumbnail resume clear_jobs skipped", exc_info=True)
    try:
        dialog.thumb_worker.add_jobs(path, jobs)
    except RuntimeError:
        logger.warning("thumbnail resume add_jobs failed", exc_info=True)
        return
    _reprioritize_current_item(dialog)


def item_has_thumbnail(_dialog, item: Optional[QtWidgets.QListWidgetItem]) -> bool:
    if item is None:
        return False
    try:
        icon = item.icon()
        if icon is None:
            return False
        return not bool(icon.isNull())
    except RuntimeError:
        logger.debug("thumbnail icon probe failed", exc_info=True)
        return False


def reprioritize_thumbnails_from_ms(dialog, start_ms: int) -> None:
    if bool(getattr(dialog, "_thumbnail_reload_suppressed", False)):
        return
    pending = _pending_thumbnail_jobs_from(dialog, start_ms)
    if not pending:
        return
    if not _replace_thumbnail_queue(dialog, pending):
        return
    dialog.lbl_status.setText(f"썸네일 우선 생성: {dialog._format_ms_mmss(start_ms)}부터")


def on_scene_item_clicked(dialog, item: Optional[QtWidgets.QListWidgetItem]) -> None:
    if item is None:
        return
    if dialog._item_has_thumbnail(item):
        return
    try:
        ms = int(item.data(QtCore.Qt.ItemDataRole.UserRole) or -1)
    except (RuntimeError, TypeError, ValueError):
        logger.debug("scene item click timestamp read failed", exc_info=True)
        ms = -1
    if ms < 0:
        return
    dialog._reprioritize_thumbnails_from_ms(ms)


def on_thumbnail_ready(dialog, path: str, image: QtGui.QImage, ms: int) -> None:
    if bool(getattr(dialog, "_thumbnail_reload_suppressed", False)) or bool(getattr(dialog, "_thumb_close_pending", False)):
        return
    if dialog._history_norm_path(path) != dialog._history_norm_path(dialog.current_path):
        return
    pixmap = QtGui.QPixmap.fromImage(image)
    if pixmap.isNull():
        return
    icon = QtGui.QIcon(pixmap)
    _store_scene_thumbnail(dialog, path, int(ms), icon)
    item = dialog._item_by_ms.get(int(ms))
    if item is None:
        return
    item.setIcon(icon)


def on_preview_thumbnail_ready(dialog, path: str, image: QtGui.QImage, ms: int) -> None:
    if bool(getattr(dialog, "_thumb_close_pending", False)):
        return
    if dialog._history_norm_path(path) != dialog._history_norm_path(dialog.current_path):
        return
    try:
        expected = set(getattr(dialog, "_preview_thumb_expected_ms", set()) or set())
    except (TypeError, ValueError):
        logger.debug("preview thumbnail expected-ms set normalization failed", exc_info=True)
        expected = set()
    if expected and int(ms) not in expected:
        return
    item = dialog._find_preview_item_by_ms(int(ms))
    if item is None:
        return
    pixmap = QtGui.QPixmap.fromImage(image)
    if pixmap.isNull():
        return
    pixmap = pixmap.scaled(
        120,
        68,
        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )
    item.setIcon(QtGui.QIcon(pixmap))


def _list_thumbnail_jobs(dialog) -> List[int]:
    jobs: List[int] = []
    try:
        for index in range(int(dialog.listw.count())):
            item = dialog.listw.item(index)
            if item is None:
                continue
            if dialog._item_has_thumbnail(item):
                continue
            ms = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if ms is None:
                continue
            jobs.append(int(ms))
    except (RuntimeError, TypeError, ValueError):
        logger.debug("thumbnail resume job collection failed", exc_info=True)
        jobs = []
    return jobs


def _reprioritize_current_item(dialog) -> None:
    current = dialog.listw.currentItem()
    if current is None:
        return
    try:
        ms = int(current.data(QtCore.Qt.ItemDataRole.UserRole))
        dialog._reprioritize_thumbnails_from_ms(ms)
    except (RuntimeError, TypeError, ValueError):
        logger.debug("thumbnail reprioritize after resume skipped", exc_info=True)


def _pending_thumbnail_jobs_from(dialog, start_ms: int) -> List[int]:
    if not hasattr(dialog, "all_scenes_data"):
        return []
    ordered_ms = [int(ms) for ms, _score in list(dialog.all_scenes_data or [])]
    if not ordered_ms:
        return []
    try:
        index = ordered_ms.index(int(start_ms))
    except ValueError:
        return []
    pending: List[int] = []
    rotated = ordered_ms[index:] + ordered_ms[:index]
    for ms in rotated:
        item = dialog._item_by_ms.get(int(ms))
        if item is None:
            continue
        if dialog._item_has_thumbnail(item):
            continue
        pending.append(int(ms))
    return pending


def _store_scene_thumbnail(dialog, path: str, ms: int, icon) -> None:
    if dialog._history_norm_path(path) != dialog._history_norm_path(dialog.current_path):
        return
    cache_path = str(getattr(dialog, "_scene_thumb_cache_path", "") or "")
    if dialog._history_norm_path(cache_path) != dialog._history_norm_path(dialog.current_path):
        dialog._scene_thumb_cache_path = str(getattr(dialog, "current_path", "") or "")
        dialog._scene_thumb_cache = {}
    cache = getattr(dialog, "_scene_thumb_cache", None)
    if not isinstance(cache, dict):
        dialog._scene_thumb_cache = {}
        cache = dialog._scene_thumb_cache
    cache[int(ms)] = icon


def _replace_thumbnail_queue(dialog, pending: List[int]) -> bool:
    try:
        dialog.thumb_worker.clear_jobs()
        dialog.thumb_worker.add_jobs(dialog.current_path, pending)
        return True
    except RuntimeError:
        logger.warning("thumbnail reprioritize queue rebuild failed", exc_info=True)
        return False
