import os
import queue
from typing import Optional

from PyQt6 import QtCore

from video_tile_helpers.support import is_image_file_path


class PlaylistDurationWorker(QtCore.QThread):
    durationReady = QtCore.pyqtSignal(str, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: "queue.Queue[Optional[tuple[str, tuple[int, int]]]]" = queue.Queue()
        self._running = True
        self._queued: set[tuple[str, tuple[int, int]]] = set()

    def stop(self):
        self._running = False
        self._queue.put(None)
        self.wait(2000)

    def add_job(self, path: str, sig: tuple[int, int]):
        key = (str(path or ""), (int(sig[0]), int(sig[1])))
        if not key[0] or key in self._queued:
            return
        self._queued.add(key)
        self._queue.put(key)

    def run(self):
        while self._running:
            job = self._queue.get()
            if job is None or not self._running:
                break
            path, sig = job
            self._queued.discard(job)
            duration_ms = _probe_duration_ms_sync(path)
            if self._running:
                self.durationReady.emit(path, sig, duration_ms)


def _probe_duration_ms_sync(path: str) -> Optional[int]:
    if not path or not os.path.exists(path) or is_image_file_path(path):
        return None
    try:
        import cv2  # type: ignore
    except Exception:
        return None
    cap = None
    try:
        cap = cv2.VideoCapture(path)
        if not cap or not cap.isOpened():
            return None
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        if fps > 1e-6 and frame_count > 0.0:
            return max(0, int(round((frame_count / fps) * 1000.0)))
    except Exception:
        return None
    finally:
        try:
            if cap is not None:
                cap.release()
        except Exception:
            pass
    return None
