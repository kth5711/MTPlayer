import os
from typing import List

from PyQt6 import QtWidgets

from scene_analysis.core.cache import _normalize_sample_paths, _normalize_sample_texts

from .batch_options import _scene_batch_option_snapshot, _scene_batch_option_text
from .batch_runtime_paths import _scene_batch_item
from .batch_worker import SceneBatchWorker


def _set_scene_batch_running(dialog, running: bool) -> None:
    on = bool(running)
    for name in (
        "_scene_batch_btn_add_files",
        "_scene_batch_btn_add_folder",
        "_scene_batch_btn_remove",
        "_scene_batch_btn_clear",
        "_scene_batch_btn_run",
    ):
        btn = getattr(dialog, name, None)
        if btn is not None:
            btn.setEnabled(not on)
    for name in ("_scene_batch_chk_scene", "_scene_batch_chk_refilter"):
        chk = getattr(dialog, name, None)
        if chk is not None:
            chk.setEnabled(not on)
    btn_cancel = getattr(dialog, "_scene_batch_btn_cancel", None)
    if btn_cancel is not None:
        btn_cancel.setEnabled(on)


def _scene_batch_running_block_reason(dialog) -> str:
    if getattr(dialog, "worker", None) is not None:
        return "씬변화가 실행 중입니다."
    rw = getattr(dialog, "refilter_worker", None)
    if rw is not None and rw.isRunning():
        return "유사씬 탐색이 실행 중입니다."
    return ""


def _scene_batch_collect_paths(dialog) -> List[str]:
    tw = getattr(dialog, "_scene_batch_tree", None)
    if tw is None:
        return []
    paths: List[str] = []
    for row in range(tw.topLevelItemCount()):
        it = tw.topLevelItem(row)
        path = os.path.abspath(str(it.data(0, 32) or "")) if hasattr(it, "data") else ""
        if path and os.path.exists(path):
            paths.append(path)
            it.setText(0, "대기")
            it.setText(3, "-")
    return paths


def _scene_batch_validate(dialog, opts, paths: List[str]) -> str:
    tw = getattr(dialog, "_scene_batch_tree", None)
    if tw is None or tw.topLevelItemCount() <= 0:
        return "작업할 파일이나 폴더를 먼저 추가하세요."
    if not paths:
        return "유효한 작업 항목이 없습니다."
    if (not bool(opts.get("run_scene", True))) and (not bool(opts.get("run_refilter", False))):
        return "실행할 작업을 하나 이상 체크하세요."
    if not bool(opts.get("run_refilter", False)):
        return ""
    sample_paths = [p for p in _normalize_sample_paths(opts.get("sample_image_paths") or []) if os.path.exists(p)]
    sample_texts = _normalize_sample_texts(opts.get("sample_texts") or [])
    if sample_paths or sample_texts:
        return ""
    return "유사씬 탐색을 실행하려면 샘플 이미지 또는 텍스트가 필요합니다."


def _prepare_scene_batch_ui(dialog, opts) -> None:
    lbl_opts = getattr(dialog, "_scene_batch_lbl_opts", None)
    if lbl_opts is not None:
        lbl_opts.setText(_scene_batch_option_text(opts))
    progress = getattr(dialog, "_scene_batch_progress", None)
    if progress is not None:
        progress.setValue(0)
    progress_all = getattr(dialog, "_scene_batch_progress_all", None)
    if progress_all is not None:
        progress_all.setValue(0)


def _scene_batch_summary_message(summary: dict) -> str:
    total = int(summary.get("total", 0))
    completed = int(summary.get("completed", 0))
    failed = int(summary.get("failed", 0))
    cached = int(summary.get("cached", 0))
    canceled = bool(summary.get("canceled", False))
    msg = f"순차 작업 완료: {completed}/{total}"
    if cached > 0:
        msg += f", 캐시 {cached}"
    if failed > 0:
        msg += f", 실패 {failed}"
    if canceled:
        msg += ", 중단됨"
    return msg


def _connect_scene_batch_worker(dialog, worker) -> None:
    def _on_started(path: str):
        it = _scene_batch_item(dialog, path)
        if it is not None:
            it.setText(0, "실행 중")

    def _on_finished(path: str, status: str, count_text: str, _cached: bool):
        it = _scene_batch_item(dialog, path)
        if it is not None:
            it.setText(0, status)
            it.setText(3, str(count_text or "-"))

    def _on_summary(summary: dict):
        _set_scene_batch_running(dialog, False)
        dialog._scene_batch_worker = None
        msg = _scene_batch_summary_message(summary)
        dialog._scene_batch_status.setText(msg)
        try:
            dialog.lbl_status.setText(msg)
        except Exception:
            pass
        try:
            dialog._schedule_cache_history_refresh()
        except Exception:
            pass

    worker.item_started.connect(_on_started)
    worker.item_finished.connect(_on_finished)
    worker.current_progress.connect(dialog._scene_batch_progress.setValue)
    worker.overall_progress.connect(dialog._scene_batch_progress_all.setValue)
    worker.message.connect(dialog._scene_batch_status.setText)
    worker.finished_summary.connect(_on_summary)


def _start_scene_batch(dialog) -> None:
    blocked = _scene_batch_running_block_reason(dialog)
    if blocked:
        QtWidgets.QMessageBox.information(dialog, "알림", blocked)
        return
    paths = _scene_batch_collect_paths(dialog)
    opts = _scene_batch_option_snapshot(dialog)
    error = _scene_batch_validate(dialog, opts, paths)
    if error:
        QtWidgets.QMessageBox.information(dialog, "알림", error)
        return
    _prepare_scene_batch_ui(dialog, opts)
    worker = SceneBatchWorker(dialog, paths, opts, parent=dialog._scene_batch_dialog)
    dialog._scene_batch_worker = worker
    _set_scene_batch_running(dialog, True)
    _connect_scene_batch_worker(dialog, worker)
    worker.start()
