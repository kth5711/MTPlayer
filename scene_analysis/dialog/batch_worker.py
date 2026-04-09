from typing import Dict, List

from PyQt6 import QtCore

from .batch_worker_context import (
    _emit_scene_batch_item_start,
    _new_scene_batch_item_state,
    _scene_batch_base_name,
    _scene_batch_result,
    _scene_batch_worker_options,
)
from .batch_worker_refilter import _run_refilter_batch_stage
from .batch_worker_scene import _run_scene_batch_stage


class SceneBatchWorker(QtCore.QThread):
    message = QtCore.pyqtSignal(str)
    current_progress = QtCore.pyqtSignal(int)
    overall_progress = QtCore.pyqtSignal(int)
    item_started = QtCore.pyqtSignal(str)
    item_finished = QtCore.pyqtSignal(str, str, str, bool)
    finished_summary = QtCore.pyqtSignal(dict)

    def __init__(self, dialog, paths: List[str], options: Dict[str, object], parent=None):
        super().__init__(parent)
        self.dialog = dialog
        self.paths = [str(p) for p in (paths or []) if str(p or "").strip()]
        self.options = dict(options or {})
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def _raise_if_cancelled(self):
        if bool(self._cancel):
            raise RuntimeError("사용자 취소")

    @staticmethod
    def _map_stage_progress(stage_start: int, stage_end: int, raw_value: int) -> int:
        start = max(0, min(100, int(stage_start)))
        end = max(start, min(100, int(stage_end)))
        raw = max(0, min(100, int(raw_value)))
        return int(round(float(start) + ((float(end - start) * float(raw)) / 100.0)))

    def _process_item(self, path: str, idx: int, total: int, config: Dict[str, object]) -> tuple[str, Dict[str, object]]:
        base = _scene_batch_base_name(path)
        _emit_scene_batch_item_start(self, path, idx, total, base)
        self._raise_if_cancelled()
        state = _new_scene_batch_item_state()
        _run_scene_batch_stage(self, path, idx, total, base, config, state)
        _run_refilter_batch_stage(self, path, idx, total, base, config, state)
        return base, _scene_batch_result(config, state)

    @staticmethod
    def _summary_dict(total: int) -> Dict[str, object]:
        return {
            "total": total,
            "completed": 0,
            "failed": 0,
            "cached": 0,
            "canceled": False,
        }

    def _record_success(
        self, summary: Dict[str, object], path: str, idx: int, total: int, base: str, result: Dict[str, object]
    ) -> None:
        summary["completed"] += 1
        if bool(result["item_cache_only"]):
            summary["cached"] += 1
        self.current_progress.emit(100)
        self.overall_progress.emit(int(((idx + 1) / max(1, total)) * 100))
        self.item_finished.emit(
            path,
            str(result["status"]),
            str(result["count_text"]),
            bool(result["item_cache_only"]),
        )
        self.message.emit(f"[{idx + 1}/{total}] {base} {result['message']}")

    def _record_failure(
        self, summary: Dict[str, object], path: str, idx: int, total: int, base: str, error: Exception
    ) -> bool:
        if str(error) == "사용자 취소":
            summary["canceled"] = True
            return True
        summary["failed"] += 1
        self.item_finished.emit(path, f"실패: {error}", "-", False)
        self.message.emit(f"[{idx + 1}/{total}] {base} 실패: {error}")
        return False

    def run(self):
        total = len(self.paths)
        summary = self._summary_dict(total)
        if total <= 0:
            self.finished_summary.emit(summary)
            return
        config = _scene_batch_worker_options(self.options)
        for idx, path in enumerate(self.paths):
            if self._cancel:
                summary["canceled"] = True
                break
            try:
                base, result = self._process_item(path, idx, total, config)
                self._record_success(summary, path, idx, total, base, result)
            except Exception as e:
                if self._record_failure(summary, path, idx, total, _scene_batch_base_name(path), e):
                    break
        self.finished_summary.emit(summary)
