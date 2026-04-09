from __future__ import annotations

from typing import Callable, Dict, List, Optional
import time

from PyQt6 import QtCore

from .similarity import _robust_renorm_similarity_pairs


class SceneSimilarityParallelRunner(QtCore.QObject):
    progress = QtCore.pyqtSignal(int)
    message = QtCore.pyqtSignal(str)
    finished_ok = QtCore.pyqtSignal(list)
    finished_err = QtCore.pyqtSignal(str)

    def __init__(
        self,
        scene_ms: List[int],
        worker_count: int,
        worker_factory: Callable[[List[int]], object],
        normalize_scores: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.scene_ms = [int(ms) for ms in (scene_ms or []) if int(ms) >= 0]
        self.worker_count = max(1, int(worker_count))
        self.worker_factory = worker_factory
        self.normalize_scores = bool(normalize_scores)
        self._workers: Dict[int, object] = {}
        self._chunks: Dict[int, List[int]] = {}
        self._progress_map: Dict[int, int] = {}
        self._result_map: Dict[int, List[tuple[int, float]]] = {}
        self._done: Dict[int, bool] = {}
        self._running = False
        self._failed_msg: Optional[str] = None
        self._cancelled = False

    def isRunning(self) -> bool:
        return bool(self._running)

    def cancel(self):
        self._cancelled = True
        for w in list(self._workers.values()):
            try:
                w.cancel()
            except Exception:
                pass

    def wait(self, timeout_ms: int = 2000) -> bool:
        timeout = max(0, int(timeout_ms))
        deadline = (time.time() + (float(timeout) / 1000.0)) if timeout > 0 else None
        ok = True
        for w in list(self._workers.values()):
            try:
                if not bool(getattr(w, "isRunning", lambda: False)()):
                    continue
                remain = None if deadline is None else int(max(0.0, (deadline - time.time()) * 1000.0))
                ok = bool(w.wait() if remain is None else w.wait(remain)) and ok
            except Exception:
                ok = False
        return bool(ok)

    def _safe_emit_progress(self, value: int):
        try:
            self.progress.emit(int(value))
        except RuntimeError:
            self._running = False

    def _safe_emit_message(self, text: str):
        try:
            self.message.emit(str(text or ""))
        except RuntimeError:
            self._running = False

    def _safe_emit_finished_ok(self, out: List[tuple[int, float]]):
        try:
            self.finished_ok.emit(list(out or []))
        except RuntimeError:
            self._running = False

    def _safe_emit_finished_err(self, text: str):
        try:
            self.finished_err.emit(str(text or ""))
        except RuntimeError:
            self._running = False

    def start(self):
        if self._running:
            return
        ms_sorted = sorted(set(int(ms) for ms in self.scene_ms if int(ms) >= 0))
        if not ms_sorted:
            self._safe_emit_finished_err("재필터 대상 씬이 없습니다.")
            return
        chunks = self._split_chunks_contiguous(ms_sorted, self.worker_count)
        if not chunks:
            self._safe_emit_finished_err("재필터 분할 작업 생성 실패")
            return
        self._running = True
        self._failed_msg = None
        self._cancelled = False
        self._workers.clear()
        self._chunks = {idx: list(ch) for idx, ch in enumerate(chunks)}
        self._progress_map = {idx: 0 for idx in self._chunks.keys()}
        self._result_map.clear()
        self._done = {idx: False for idx in self._chunks.keys()}
        for idx, chunk in self._chunks.items():
            self._bind_worker(idx, chunk)
        self._safe_emit_message(f"SigLIP2 병렬 워커 시작: {len(self._workers)}개")
        for w in self._workers.values():
            w.start()

    def _bind_worker(self, idx: int, chunk: List[int]):
        w = self.worker_factory(chunk)
        self._workers[idx] = w
        w.progress.connect(lambda p, ii=idx: self._on_worker_progress(ii, int(p)))
        w.message.connect(lambda msg, ii=idx: self._on_worker_message(ii, str(msg)))
        w.finished_ok.connect(lambda out, ii=idx: self._on_worker_ok(ii, out))
        w.finished_err.connect(lambda msg, ii=idx: self._on_worker_err(ii, str(msg)))

    @staticmethod
    def _split_chunks_contiguous(ms_sorted: List[int], worker_count: int) -> List[List[int]]:
        arr = list(ms_sorted or [])
        if not arr:
            return []
        n = max(1, min(int(worker_count), len(arr)))
        base = len(arr) // n
        rem = len(arr) % n
        out: List[List[int]] = []
        s = 0
        for i in range(n):
            take = base + (1 if i < rem else 0)
            e = s + take
            ch = arr[s:e]
            if ch:
                out.append(ch)
            s = e
        return out

    def _emit_progress(self):
        total_weight = max(1, sum(len(ch) for ch in self._chunks.values()))
        acc = 0.0
        for idx, ch in self._chunks.items():
            p = max(0, min(100, int(self._progress_map.get(idx, 0))))
            acc += (float(p) * float(len(ch))) / float(total_weight)
        self._safe_emit_progress(int(round(acc)))

    def _on_worker_progress(self, idx: int, p: int):
        if (not self._running) and bool(self._done):
            return
        self._progress_map[idx] = max(0, min(100, int(p)))
        self._emit_progress()

    def _on_worker_message(self, idx: int, msg: str):
        if (not self._running) and bool(self._done):
            return
        self._safe_emit_message(f"[W{int(idx) + 1}] " + str(msg or ""))

    def _mark_done(self, idx: int):
        self._done[idx] = True
        self._progress_map[idx] = 100
        self._emit_progress()
        if not all(self._done.values()):
            return
        self._running = False
        if self._failed_msg:
            self._safe_emit_finished_err(str(self._failed_msg))
            return
        merged: List[tuple[int, float]] = []
        for out in self._result_map.values():
            merged.extend((int(ms), float(s)) for ms, s in (out or []))
        merged.sort(key=lambda x: x[0])
        if bool(self.normalize_scores):
            merged = _robust_renorm_similarity_pairs(merged)
        self._safe_emit_finished_ok(merged)

    def _on_worker_ok(self, idx: int, out: List[tuple[int, float]]):
        if self._done.get(idx):
            return
        self._result_map[idx] = list(out or [])
        self._mark_done(idx)

    def _on_worker_err(self, idx: int, msg: str):
        if self._done.get(idx):
            return
        text = str(msg or "").strip()
        if text and text != "사용자 취소" and self._failed_msg is None:
            self._failed_msg = text
            self._cancel_other_workers(idx)
        elif text == "사용자 취소" and self._cancelled and self._failed_msg is None:
            self._failed_msg = "사용자 취소"
        self._mark_done(idx)

    def _cancel_other_workers(self, failed_idx: int):
        for idx, w in self._workers.items():
            if idx == failed_idx:
                continue
            try:
                w.cancel()
            except Exception:
                pass


__all__ = ["SceneSimilarityParallelRunner"]
