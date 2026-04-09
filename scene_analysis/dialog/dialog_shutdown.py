from typing import Any
import logging
import time

from PyQt6 import QtWidgets

from .batch_dialog import close_scene_batch_dialog

logger = logging.getLogger(__name__)


def wait_for_worker_stopped(worker: Any, timeout_ms: int = 5000) -> bool:
    if worker is None:
        return True
    try:
        if not bool(worker.isRunning()):
            return True
    except Exception:
        return True
    wait_fn = getattr(worker, "wait", None)
    if not callable(wait_fn):
        try:
            return not bool(worker.isRunning())
        except Exception:
            return True
    deadline = time.monotonic() + (max(0, int(timeout_ms)) / 1000.0)
    while _wait_once(wait_fn, deadline):
        pass
    try:
        return not bool(worker.isRunning())
    except Exception:
        return True


def _wait_once(wait_fn, deadline: float) -> bool:
    remain_ms = int(round((deadline - time.monotonic()) * 1000.0))
    if remain_ms <= 0:
        return False
    try:
        if bool(wait_fn(min(100, max(1, remain_ms)))):
            return False
    except TypeError:
        try:
            if bool(wait_fn()):
                return False
        except Exception:
            return False
    except Exception:
        return False
    app = QtWidgets.QApplication.instance()
    if app is not None:
        try:
            app.processEvents()
        except Exception:
            pass
    return True


def cancel_dialog_workers(dialog, *, for_shutdown: bool) -> None:
    worker_specs = [("worker", "cancel", "scan"), ("refilter_worker", "cancel", "refilter"), ("clip_worker", "stop", "clip")]
    for worker_name, method_name, label in worker_specs:
        worker = getattr(dialog, worker_name, None)
        if worker is None:
            continue
        try:
            if worker.isRunning():
                getattr(worker, method_name)()
        except Exception:
            phase = "app shutdown" if for_shutdown else "dialog close"
            logger.warning("scene dialog %s worker %s failed during %s", label, method_name, phase, exc_info=True)


def close_dialog_children(dialog, *, for_shutdown: bool) -> None:
    hd = getattr(dialog, "_cache_hist_dialog", None)
    if hd is not None:
        try:
            hd.close()
        except Exception:
            logger.debug("scene dialog cache history close skipped", exc_info=True)
    try:
        close_scene_batch_dialog(dialog)
    except Exception:
        phase = "app shutdown" if for_shutdown else "scene dialog close"
        logger.warning("scene batch dialog close failed during %s", phase, exc_info=True)


def close_running_scan_workers(dialog) -> None:
    for worker_name in ("worker", "refilter_worker"):
        worker = getattr(dialog, worker_name, None)
        if worker is not None and worker.isRunning():
            worker.cancel()
            wait_fn = getattr(worker, "wait", None)
            if callable(wait_fn):
                wait_fn(2000)
