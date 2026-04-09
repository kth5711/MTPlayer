import logging
import time

from PyQt6 import QtWidgets, QtGui, QtCore

from .dialog_shutdown import (
    cancel_dialog_workers,
    close_dialog_children,
    close_running_scan_workers,
    wait_for_worker_stopped,
)

logger = logging.getLogger(__name__)


def thumbnail_workers_running(dialog) -> bool:
    for name in ("thumb_worker", "preview_thumb_worker"):
        worker = getattr(dialog, name, None)
        try:
            if worker is not None and worker.isRunning():
                return True
        except RuntimeError:
            logger.debug("thumbnail worker running-state check skipped for %s", name, exc_info=True)
    return False


def _stop_dialog_timers(dialog) -> None:
    for timer_name in (
        "_thumbnail_resume_timer",
        "_scene_frame_preview_timer",
        "_load_check_timer",
        "_refilter_reapply_timer",
        "_scan_elapsed_timer",
        "_thumb_close_retry_timer",
    ):
        timer = getattr(dialog, timer_name, None)
        if timer is not None:
            try:
                timer.stop()
            except RuntimeError:
                logger.debug("scene dialog timer stop skipped for %s", timer_name, exc_info=True)


def _disconnect_and_stop_thumbnail_worker(dialog, worker_name: str, slot_name: str) -> None:
    worker = getattr(dialog, worker_name, None)
    slot = getattr(dialog, slot_name, None)
    if worker is None or slot is None:
        return
    try:
        worker.thumbnailReady.disconnect(slot)
    except (RuntimeError, TypeError):
        logger.debug("thumbnailReady disconnect skipped for %s", worker_name, exc_info=True)
    try:
        worker.request_stop(release_capture=True)
    except RuntimeError:
        logger.warning("thumbnail worker request_stop failed for %s; falling back to stop()", worker_name, exc_info=True)
        try:
            worker.stop(0)
        except RuntimeError:
            logger.warning("thumbnail worker stop fallback failed for %s", worker_name, exc_info=True)


def prepare_thumbnail_workers_for_close(dialog) -> None:
    dialog._thumbnail_reload_suppressed = True
    dialog._preview_thumb_expected_ms = set()
    _stop_dialog_timers(dialog)
    try:
        dialog._set_scan_progress_active(False)
    except RuntimeError:
        logger.debug("scene dialog scan progress reset skipped", exc_info=True)
    for worker_name, slot_name in (("thumb_worker", "_on_thumbnail_ready"), ("preview_thumb_worker", "_on_preview_thumbnail_ready")):
        _disconnect_and_stop_thumbnail_worker(dialog, worker_name, slot_name)


def continue_close_after_thumbnail_workers(dialog) -> None:
    if not bool(getattr(dialog, "_thumb_close_pending", False)):
        return
    if thumbnail_workers_running(dialog):
        timer = getattr(dialog, "_thumb_close_retry_timer", None)
        if timer is not None and (not timer.isActive()):
            timer.start()
        return
    timer = getattr(dialog, "_thumb_close_retry_timer", None)
    if timer is not None:
        try:
            timer.stop()
        except RuntimeError:
            logger.debug("scene dialog close retry timer stop skipped", exc_info=True)
    dialog._thumb_close_pending = False
    dialog._force_close_after_thumb = True
    dialog.close()


def begin_async_thumbnail_close(dialog) -> None:
    if bool(getattr(dialog, "_thumb_close_pending", False)):
        return
    dialog._thumb_close_pending = True
    try:
        if getattr(dialog.host, "_sceneDlg", None) is dialog:
            dialog.host._sceneDlg = None
    except (AttributeError, RuntimeError):
        logger.debug("scene dialog host pointer clear skipped", exc_info=True)
    if getattr(dialog, "_thumb_close_retry_timer", None) is None:
        dialog._thumb_close_retry_timer = QtCore.QTimer(dialog)
        dialog._thumb_close_retry_timer.setSingleShot(True)
        dialog._thumb_close_retry_timer.setInterval(40)
        dialog._thumb_close_retry_timer.timeout.connect(dialog._continue_close_after_thumbnail_workers)
    prepare_thumbnail_workers_for_close(dialog)
    for name in ("thumb_worker", "preview_thumb_worker"):
        _reconnect_worker_finished(dialog, name)
    try:
        dialog.hide()
    except RuntimeError:
        logger.debug("scene dialog hide during async close skipped", exc_info=True)
    continue_close_after_thumbnail_workers(dialog)


def _reconnect_worker_finished(dialog, worker_name: str) -> None:
    worker = getattr(dialog, worker_name, None)
    if worker is None:
        return
    try:
        worker.finished.disconnect(dialog._continue_close_after_thumbnail_workers)
    except (RuntimeError, TypeError):
        logger.debug("thumbnail worker finished disconnect skipped for %s", worker_name, exc_info=True)
    try:
        worker.finished.connect(dialog._continue_close_after_thumbnail_workers)
    except RuntimeError:
        logger.warning("thumbnail worker finished connect failed for %s", worker_name, exc_info=True)


def shutdown_for_app_close(dialog, timeout_ms: int = 5000) -> bool:
    deadline = time.monotonic() + (max(0, int(timeout_ms)) / 1000.0)
    timer = getattr(dialog, "_thumb_close_retry_timer", None)
    if timer is not None:
        try:
            timer.stop()
        except RuntimeError:
            logger.debug("scene dialog close retry timer stop skipped during app shutdown", exc_info=True)
    dialog._thumb_close_pending = dialog._force_close_after_thumb = False
    try:
        prepare_thumbnail_workers_for_close(dialog)
    except Exception:
        logger.warning("scene dialog thumbnail shutdown prepare failed", exc_info=True)
    cancel_dialog_workers(dialog, for_shutdown=True)
    close_dialog_children(dialog, for_shutdown=True)
    ok = True
    for worker_name in ("worker", "refilter_worker", "clip_worker", "thumb_worker", "preview_thumb_worker"):
        remain_ms = max(0, int(round((deadline - time.monotonic()) * 1000.0)))
        if not wait_for_worker_stopped(getattr(dialog, worker_name, None), timeout_ms=remain_ms):
            logger.warning("scene dialog worker still running during app shutdown: %s", worker_name)
            ok = False
    return bool(ok)


def close_event(dialog, e: QtGui.QCloseEvent) -> None:
    dialog._force_close_after_thumb = False
    _stop_dialog_timers(dialog)
    close_running_scan_workers(dialog)
    ok = shutdown_for_app_close(dialog, timeout_ms=5000)
    try:
        dialog._set_scan_progress_active(False)
    except RuntimeError:
        logger.debug("scene dialog scan progress reset skipped in closeEvent", exc_info=True)
    if not ok:
        logger.warning("scene dialog close deferred because workers are still running")
        try:
            dialog.hide()
        except RuntimeError:
            logger.debug("scene dialog hide skipped while deferring close", exc_info=True)
        e.ignore()
        return
    super(dialog.__class__, dialog).closeEvent(e)
