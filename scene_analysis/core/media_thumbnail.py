from __future__ import annotations

from typing import Optional
import logging
import os
import queue
import threading

from PyQt6 import QtCore, QtGui

from .media_ffmpeg import _ffmpeg_frame_to_qimage, _ffmpeg_frames_to_qimages


logger = logging.getLogger(__name__)
_CV2_FAILURE_STREAK_LIMIT = 2
_FFMPEG_BATCH_SIZE = 6


class ThumbnailWorker(QtCore.QThread):
    thumbnailReady = QtCore.pyqtSignal(str, QtGui.QImage, int)

    def __init__(self, get_frame_callable=None, parent=None):
        super().__init__(parent)
        self._queue = queue.Queue()
        self._running = True
        self.get_frame_callable = get_frame_callable
        self._queued_keys: set[tuple[str, int]] = set()
        self._cap = None
        self._cap_path: Optional[str] = None
        self._cap_lock = threading.Lock()
        self._release_cap_requested = False
        self._cv2_fail_streaks: dict[str, int] = {}
        self._cv2_disabled_paths: set[str] = set()

    def _release_cap(self):
        with self._cap_lock:
            self._release_cap_locked()

    def _release_cap_locked(self):
        cap = self._cap
        self._cap = None
        self._cap_path = None
        self._release_cap_requested = False
        if cap is not None:
            try:
                cap.release()
            except (AttributeError, RuntimeError):
                logger.debug("thumbnail capture release skipped", exc_info=True)

    def _request_cap_release(self):
        with self._cap_lock:
            self._release_cap_requested = True

    def _flush_cap_release_request(self):
        with self._cap_lock:
            if self._release_cap_requested:
                self._release_cap_locked()

    def request_stop(self, release_capture: bool = True):
        self._running = False
        self.clear_jobs(release_capture=bool(release_capture))
        self._queue.put(None)

    def stop(self, wait_ms: int = 2000):
        self.request_stop(release_capture=True)
        try:
            self.wait(max(0, int(wait_ms)))
        except RuntimeError:
            logger.debug("thumbnail worker wait skipped", exc_info=True)
        self._release_cap()

    def clear_jobs(self, release_capture: bool = False):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._queued_keys.clear()
        if bool(release_capture):
            self._request_cap_release()

    def add_job(self, path: str, ms: int):
        if not self._running:
            return
        key = (path, int(ms))
        if key in self._queued_keys:
            return
        self._queued_keys.add(key)
        self._queue.put(key)

    def add_jobs(self, path: str, ms_list):
        for ms in ms_list:
            self.add_job(path, int(ms))

    def _path_key(self, path: str) -> str:
        return os.path.normcase(os.path.abspath(str(path or "")))

    def _cv2_disabled_for_path(self, path: str) -> bool:
        return self._path_key(path) in self._cv2_disabled_paths

    def _mark_cv2_success(self, path: str) -> None:
        key = self._path_key(path)
        self._cv2_fail_streaks.pop(key, None)

    def _mark_cv2_failure(self, path: str) -> None:
        key = self._path_key(path)
        if not key:
            return
        streak = int(self._cv2_fail_streaks.get(key, 0)) + 1
        self._cv2_fail_streaks[key] = streak
        if streak < _CV2_FAILURE_STREAK_LIMIT or key in self._cv2_disabled_paths:
            return
        self._cv2_disabled_paths.add(key)
        if self._path_key(str(self._cap_path or "")) == key:
            self._request_cap_release()
        logger.info("thumbnail worker switched to ffmpeg-only for %s after %d cv2 failures", path, streak)

    def _get_frame_cv2_cached(self, path: str, ms: int, w: int = 160, h: int = 90):
        try:
            import cv2
        except ImportError:
            return None
        self._flush_cap_release_request()
        if not path or not os.path.exists(path):
            return None
        if self._cv2_disabled_for_path(path):
            return None
        cap = self._ensure_capture(path)
        if cap is None:
            self._mark_cv2_failure(path)
            return None
        ret, frame = self._read_frame(cap, ms, cv2)
        if (not ret) or frame is None:
            cap = self._reopen_capture(path, cv2)
            if cap is None:
                self._mark_cv2_failure(path)
                return None
            ret, frame = self._read_frame(cap, ms, cv2)
            if (not ret) or frame is None:
                self._mark_cv2_failure(path)
                return None
        qimg = _frame_to_qimage(frame, cv2, w=w, h=h)
        if qimg is None or qimg.isNull():
            self._mark_cv2_failure(path)
            return None
        self._mark_cv2_success(path)
        return qimg

    def _ensure_capture(self, path: str):
        try:
            import cv2
        except ImportError:
            return None
        with self._cap_lock:
            if self._release_cap_requested:
                self._release_cap_locked()
            if self._cap is None or self._cap_path != path:
                self._release_cap_locked()
                cap = cv2.VideoCapture(path)
                if not cap.isOpened():
                    try:
                        cap.release()
                    except RuntimeError:
                        logger.debug("thumbnail capture close after open failure skipped", exc_info=True)
                    return None
                self._cap = cap
                self._cap_path = path
            return self._cap

    def _reopen_capture(self, path: str, cv2_module):
        with self._cap_lock:
            self._release_cap_locked()
            cap = cv2_module.VideoCapture(path)
            if not cap.isOpened():
                try:
                    cap.release()
                except RuntimeError:
                    logger.debug("thumbnail capture reopen close skipped", exc_info=True)
                return None
            self._cap = cap
            self._cap_path = path
            return self._cap

    def _read_frame(self, cap, ms: int, cv2_module):
        cap.set(cv2_module.CAP_PROP_POS_MSEC, max(0, int(ms)))
        return cap.read()

    def _get_frame_fast(self, path: str, ms: int, w: int = 160, h: int = 90):
        qimg = self._get_frame_cv2_cached(path, ms, w=w, h=h)
        if qimg and not qimg.isNull():
            return qimg
        return _ffmpeg_frame_to_qimage(path, ms, w=w, h=h)

    def _collect_ffmpeg_batch_ms(self, path: str, first_ms: int) -> list[int]:
        if not self._cv2_disabled_for_path(path):
            return [int(first_ms)]
        path_key = self._path_key(path)
        batch_ms = [int(first_ms)]
        deferred_jobs = []
        while len(batch_ms) < _FFMPEG_BATCH_SIZE:
            try:
                queued = self._queue.get_nowait()
            except queue.Empty:
                break
            if queued is None:
                self._queue.put(None)
                break
            queued_path, queued_ms = queued
            if self._path_key(queued_path) == path_key:
                batch_ms.append(int(queued_ms))
                self._queued_keys.discard((queued_path, int(queued_ms)))
                continue
            deferred_jobs.append(queued)
        for queued in deferred_jobs:
            self._queue.put(queued)
        return batch_ms

    def _emit_ffmpeg_batch(self, path: str, ms_list: list[int], w: int = 160, h: int = 90) -> None:
        batch_images = _ffmpeg_frames_to_qimages(path, ms_list, w=w, h=h) if len(ms_list) > 1 else {}
        for ms in ms_list:
            qimg = batch_images.get(int(ms))
            if qimg is None or qimg.isNull():
                qimg = _ffmpeg_frame_to_qimage(path, int(ms), w=w, h=h)
            if qimg and not qimg.isNull() and self._running:
                self.thumbnailReady.emit(path, qimg, int(ms))

    def run(self):
        while self._running:
            job = self._queue.get()
            if job is None or not self._running:
                break
            path, ms = job
            self._queued_keys.discard((path, ms))
            try:
                if self._cv2_disabled_for_path(path):
                    self._emit_ffmpeg_batch(path, self._collect_ffmpeg_batch_ms(path, int(ms)), w=160, h=90)
                    continue
                qimg = self._get_frame_fast(path, ms, w=160, h=90)
                if qimg and not qimg.isNull() and self._running:
                    self.thumbnailReady.emit(path, qimg, ms)
            except Exception:
                logger.warning("thumbnail generation failed for %s at %dms", path, ms, exc_info=True)
        self._flush_cap_release_request()
        self._release_cap()


def _frame_to_qimage(frame, cv2_module, w: int, h: int):
    qimg = _qimage_from_bgr_frame(frame)
    if qimg is None:
        qimg = _qimage_from_rgb_frame(frame, cv2_module)
    if qimg.isNull():
        return None
    return qimg.scaled(
        w,
        h,
        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )


def _qimage_from_bgr_frame(frame):
    height, width, channels = frame.shape
    fmt_container = getattr(QtGui.QImage, "Format", None)
    if fmt_container is not None and hasattr(fmt_container, "Format_BGR888"):
        return QtGui.QImage(frame.data, width, height, channels * width, fmt_container.Format_BGR888).copy()
    if hasattr(QtGui.QImage, "Format_BGR888"):
        return QtGui.QImage(frame.data, width, height, channels * width, QtGui.QImage.Format_BGR888).copy()
    return None


def _qimage_from_rgb_frame(frame, cv2_module):
    frame_rgb = cv2_module.cvtColor(frame, cv2_module.COLOR_BGR2RGB)
    height, width, channels = frame_rgb.shape
    fmt_container = getattr(QtGui.QImage, "Format", None)
    if fmt_container is not None and hasattr(fmt_container, "Format_RGB888"):
        fmt = fmt_container.Format_RGB888
    else:
        fmt = QtGui.QImage.Format_RGB888
    return QtGui.QImage(frame_rgb.data, width, height, channels * width, fmt).copy()
