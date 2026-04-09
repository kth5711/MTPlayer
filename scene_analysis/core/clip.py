from __future__ import annotations

from typing import List, Optional
import os
import queue
import subprocess
import time

from PyQt6 import QtCore

from process_utils import hidden_subprocess_kwargs
from .media import FFMPEG_BIN, ffmpeg_available, resolve_ffmpeg_bin
from .clip_jobs import export_gif_job, export_merge_job, export_ranges_job, export_tile_clip_job


class ClipExportQueueWorker(QtCore.QThread):
    message = QtCore.pyqtSignal(str)
    busy_changed = QtCore.pyqtSignal(bool)
    job_finished = QtCore.pyqtSignal(dict)
    job_failed = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: "queue.Queue[Optional[dict]]" = queue.Queue()
        self._running = True
        self._busy = False
        self._seq = 0
        self._cancel_current = False
        self._proc: Optional[subprocess.Popen] = None

    def enqueue(self, job: dict) -> int:
        self._seq += 1
        payload = dict(job or {})
        payload["job_id"] = int(self._seq)
        self._queue.put(payload)
        return int(self._seq)

    def isBusy(self) -> bool:
        return bool(self._busy or (not self._queue.empty()))

    def cancel_current(self):
        self._cancel_current = True
        proc = self._proc
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass

    def stop(self):
        self._running = False
        self.cancel_current()
        self._queue.put(None)

    @staticmethod
    def _fmt_ms_tag(ms: int) -> str:
        total = max(0, int(ms))
        sec = total // 1000
        ms3 = total % 1000
        hh = sec // 3600
        mm = (sec % 3600) // 60
        ss = sec % 60
        return f"{hh:02d}-{mm:02d}-{ss:02d}-{ms3:03d}"

    @staticmethod
    def _unique_path(path: str) -> str:
        if not os.path.exists(path):
            return path
        root, ext = os.path.splitext(path)
        idx = 2
        while True:
            cand = f"{root}_{idx}{ext}"
            if not os.path.exists(cand):
                return cand
            idx += 1

    def _run_ffmpeg(self, cmd: List[str]):
        self._cancel_current = False
        ffbin = str(cmd[0] if cmd else "")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **hidden_subprocess_kwargs(),
        )
        self._proc = proc
        try:
            while True:
                if (not self._running) or self._cancel_current:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    raise RuntimeError("사용자 취소")
                rc = proc.poll()
                if rc is not None:
                    break
                time.sleep(0.05)
            out, err = proc.communicate(timeout=1)
            if rc != 0:
                tail = str(err or out or "").strip()
                if tail:
                    tail = tail[-320:]
                    raise RuntimeError(f"ffmpeg 실패(rc={rc}, bin={ffbin}): {tail}")
                raise RuntimeError(f"ffmpeg 실패(rc={rc}, bin={ffbin})")
        finally:
            self._proc = None

    def _export_ranges(self, job: dict) -> dict:
        return export_ranges_job(self, job)

    def _export_merge(self, job: dict) -> dict:
        return export_merge_job(self, job)

    def _export_gif(self, job: dict) -> dict:
        return export_gif_job(self, job)

    def _export_tile_clip(self, job: dict) -> dict:
        return export_tile_clip_job(self, job)

    def _process_job(self, job: dict) -> dict:
        kind = str(job.get("kind") or "ranges").strip().lower()
        if kind == "merge":
            return self._export_merge(job)
        if kind == "gif":
            return self._export_gif(job)
        if kind in {"tile_clip", "tile_audio_clip"}:
            return self._export_tile_clip(job)
        return self._export_ranges(job)

    def run(self):
        while True:
            if not self._running:
                break
            job = self._queue.get()
            if job is None:
                break
            if not isinstance(job, dict):
                continue
            self._busy = True
            self.busy_changed.emit(True)
            try:
                result = self._process_job(job)
                self.job_finished.emit(result)
            except Exception as e:
                payload = {
                    "job_id": int(job.get("job_id") or 0),
                    "kind": str(job.get("kind") or "ranges"),
                    "source": str(job.get("source") or "manual"),
                    "mode_label": str(job.get("mode_label") or "클립"),
                    "ffbin": str(job.get("ffbin") or ""),
                    "out_path": str(job.get("out_path") or ""),
                    "error": str(e),
                }
                self.job_failed.emit(payload)
            finally:
                self._busy = False
                if self._queue.empty():
                    self.busy_changed.emit(False)
