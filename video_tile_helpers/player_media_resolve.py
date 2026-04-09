import threading
import time
from typing import Any, Dict

from PyQt6 import QtCore, QtWidgets

from i18n import tr
from url_media_resolver import resolve_playback_source

URL_RESOLVE_TIMEOUT_SECONDS = 15.0


def _resolve_playback_source_with_worker(tile, source: str) -> Dict[str, Any]:
    result_box: Dict[str, Any] = {}
    error_box: Dict[str, str] = {}
    done = threading.Event()
    loop = QtCore.QEventLoop()
    app = QtWidgets.QApplication.instance()
    quit_requested = {"value": False}
    timer = _create_poll_timer(loop, done)
    quit_handler = _connect_about_to_quit(app, loop, quit_requested)
    thread = _start_resolver_thread(tile, source, result_box, error_box, done)
    timer.start()
    try:
        _wait_for_resolver(loop, done, quit_requested)
    finally:
        _cleanup_resolver(timer, app, quit_handler)
    thread.join(max(0.0, float(URL_RESOLVE_TIMEOUT_SECONDS) + 1.0))
    return _resolved_value(tile, result_box, error_box)


def _create_poll_timer(loop, done):
    timer = QtCore.QTimer()
    timer.setInterval(25)
    timer.setSingleShot(False)
    timer.timeout.connect(lambda: loop.quit() if done.is_set() else None)
    return timer


def _connect_about_to_quit(app, loop, quit_requested):
    if app is None:
        return None

    def _on_about_to_quit():
        quit_requested["value"] = True
        loop.quit()

    app.aboutToQuit.connect(_on_about_to_quit)
    return _on_about_to_quit


def _start_resolver_thread(tile, source, result_box, error_box, done):
    thread = threading.Thread(
        target=_run_resolver,
        args=(tile, source, result_box, error_box, done),
        name="MultiPlayUrlResolve",
        daemon=True,
    )
    thread.start()
    return thread


def _run_resolver(tile, source, result_box, error_box, done):
    try:
        result_box["value"] = resolve_playback_source(source, timeout_seconds=URL_RESOLVE_TIMEOUT_SECONDS)
    except Exception as exc:
        error_box["value"] = str(exc or tr(tile, "URL 해석에 실패했습니다."))
    finally:
        done.set()


def _wait_for_resolver(loop, done, quit_requested):
    while not done.is_set() and not quit_requested["value"]:
        loop.exec()
        if done.is_set():
            break
        time.sleep(0.005)


def _cleanup_resolver(timer, app, quit_handler):
    timer.stop()
    timer.deleteLater()
    if app is None or quit_handler is None:
        return
    try:
        app.aboutToQuit.disconnect(quit_handler)
    except (TypeError, RuntimeError):
        pass


def _resolved_value(tile, result_box, error_box):
    if "value" in error_box:
        raise RuntimeError(error_box["value"])
    if "value" not in result_box:
        raise RuntimeError(tr(tile, "URL 해석 결과를 받지 못했습니다."))
    return result_box["value"]
