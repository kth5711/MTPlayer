from typing import List
import logging

from PyQt6 import QtWidgets

from scene_analysis.core.cache import refilter_cache_set
from scene_analysis.core.refilter import SceneSimilarityParallelRunner, SceneSimilarityWorker

from .refilter_worker_setup import prepare_similarity_refilter


logger = logging.getLogger(__name__)


def run_similarity_refilter(dialog) -> None:
    prepared = prepare_similarity_refilter(dialog)
    if not prepared:
        return
    if prepared["cached_pairs"] is not None:
        dialog.progress.setValue(100)
        dialog._apply_refilter_pairs(
            prepared["source"],
            prepared["cached_pairs"],
            prepared["mode"],
            cache_hit=True,
        )
        return

    dialog.progress.setValue(0)
    dialog._set_refilter_running(True)
    worker = _build_refilter_worker(dialog, prepared)
    dialog.refilter_worker = worker
    worker.progress.connect(dialog.progress.setValue)
    worker.message.connect(dialog.lbl_status.setText)
    _bind_refilter_cancel(dialog)
    worker.finished_ok.connect(lambda sim_pairs: _handle_refilter_finished_ok(dialog, prepared, sim_pairs))
    worker.finished_err.connect(lambda msg: _handle_refilter_finished_err(dialog, msg))
    worker.start()


def clear_similarity_refilter(dialog) -> None:
    if dialog.refilter_worker is not None and dialog.refilter_worker.isRunning():
        return
    _stop_refilter_timers(dialog)
    dialog._thumbnail_reload_suppressed = False
    source = _restore_refilter_source(dialog)
    if not source:
        return
    dialog._similarity_by_ms.clear()
    dialog._last_refilter_sim_by_ms.clear()
    dialog._direct_group_clip_ranges = {}
    dialog._refilter_active = False
    dialog.btn_refilter_clear.setEnabled(False)
    pts = [ms for ms, _ in source]
    dialog._populate_from_result(dialog.current_path, pts, source, reset_similarity=False)
    dialog._update_scene_clip_button_enabled()
    dialog.lbl_status.setText(f"유사씬 해제: {len(source)}개 복원")


def _build_refilter_worker(dialog, prepared: dict):
    if prepared["worker_count_eff"] <= 1:
        return SceneSimilarityWorker(
            dialog.current_path,
            prepared["ms_list"],
            prepared["sample_paths"],
            mode=prepared["mode"],
            normalize_scores=True,
            **prepared["worker_kwargs"],
        )
    dialog.lbl_status.setText(
        f"SigLIP2 CPU 병렬 준비: {len(prepared['ms_list'])}개 씬, 자동 워커 {int(prepared['worker_count_eff'])}개"
    )
    QtWidgets.QApplication.processEvents()

    def _mk_worker(chunk_ms: List[int]) -> SceneSimilarityWorker:
        return SceneSimilarityWorker(
            dialog.current_path,
            chunk_ms,
            prepared["sample_paths"],
            mode=prepared["mode"],
            normalize_scores=False,
            **prepared["worker_kwargs"],
        )

    return SceneSimilarityParallelRunner(
        prepared["ms_list"],
        prepared["worker_count_eff"],
        _mk_worker,
        normalize_scores=(prepared["mode"] != "siglip2"),
        parent=dialog,
    )


def _bind_refilter_cancel(dialog) -> None:
    try:
        dialog.btn_cancel.clicked.disconnect()
    except TypeError:
        pass
    dialog.btn_cancel.clicked.connect(lambda: _cancel_refilter_now(dialog))


def _cancel_refilter_now(dialog) -> None:
    worker = getattr(dialog, "refilter_worker", None)
    if worker is None or not worker.isRunning():
        return
    dialog.lbl_status.setText("취소 중…")
    try:
        worker.cancel()
    except RuntimeError:
        logger.debug("refilter worker cancel skipped", exc_info=True)
    dialog.btn_cancel.setEnabled(False)


def _handle_refilter_finished_ok(dialog, prepared: dict, sim_pairs: List[tuple[int, float]]) -> None:
    dialog._set_refilter_running(False)
    dialog.refilter_worker = None
    cache_store_kwargs = dict(prepared["cache_kwargs"])
    cache_store_kwargs.update(
        {
            "source_mode": prepared["source_mode"],
            "direct_interval_sec": dialog._current_refilter_direct_sec() if prepared["source_mode"] == "direct" else 0,
            "sim_threshold": float(dialog.spn_sim_thr.value()),
        }
    )
    refilter_cache_set(
        dialog.current_path,
        prepared["sample_paths"],
        prepared["mode"],
        prepared["ms_list"],
        sim_pairs,
        **cache_store_kwargs,
    )
    dialog._apply_refilter_pairs(prepared["source"], sim_pairs, prepared["mode"], cache_hit=False)


def _handle_refilter_finished_err(dialog, msg: str) -> None:
    dialog._set_refilter_running(False)
    dialog.refilter_worker = None
    if msg != "사용자 취소":
        QtWidgets.QMessageBox.warning(dialog, "오류", msg)
    dialog.lbl_status.setText("대기")


def _stop_refilter_timers(dialog) -> None:
    try:
        if dialog._refilter_reapply_timer.isActive():
            dialog._refilter_reapply_timer.stop()
    except RuntimeError:
        logger.debug("refilter reapply timer stop skipped during clear", exc_info=True)
    try:
        if dialog._thumbnail_resume_timer.isActive():
            dialog._thumbnail_resume_timer.stop()
    except RuntimeError:
        logger.debug("thumbnail resume timer stop skipped during clear", exc_info=True)


def _restore_refilter_source(dialog) -> List[tuple[int, float]]:
    source = list(dialog._refilter_source_data or [])
    if source:
        return source
    over = list(getattr(dialog, "_refilter_source_override_ms", []) or [])
    if not over:
        return []
    return [(int(ms), 0.0) for ms in sorted(set(int(x) for x in over if int(x) >= 0))]
