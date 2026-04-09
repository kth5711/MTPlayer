from typing import Any, Optional
import logging
import os

from PyQt6 import QtWidgets

from scene_analysis.core.cache import load_from_disk, scene_cache_get, scene_cache_set, store_to_disk
from scene_analysis.core.detect import SceneDetectWorker
from scene_analysis.core.media import FFMPEG_BIN, resolve_ffmpeg_bin
from scene_analysis.core.similarity import _gpu_decode_chunk_batch_limits


logger = logging.getLogger(__name__)

_SCAN_CONTROL_ATTRS = (
    "ed_ff", "spn_thr", "spn_dw", "spn_fps",
    "spn_back", "chk_use_cache", "btn_cache_history", "btn_scan_batch", "btn_scan",
    "spn_topk", "spn_mingap", "spn_batch", "cmb_scene_sort",
    "spn_scene_frame_secs", "chk_scene_frame_prev", "spn_scene_frame_shift_count",
    "spn_scene_frame_shift_step", "btn_scene_frame_shift_prev", "btn_scene_frame_shift_next",
    "chk_scene_frame_preview", "btn_scene_set_ab", "btn_scene_clip_save", "btn_scene_gif_save",
    "chk_scene_clip_merge", "btn_scene_frame_save", "btn_scene_bookmark_add", "lst_scene_frame_preview",
    "lst_ref_img", "edt_ref_text", "btn_pick_ref", "btn_remove_ref", "btn_clear_ref",
    "cmb_refilter_mode", "cmb_refilter_source", "edt_siglip_adapter", "btn_pick_siglip_adapter",
    "cmb_refilter_sampling", "chk_siglip_two_stage", "spn_siglip_stage2_ratio",
    "spn_refilter_direct_sec", "cmb_siglip_decode_scale",
    "chk_refilter_direct_group", "cmb_frame_profile", "cmb_refilter_agg", "spn_kofn_k",
    "cmb_weight_profile", "sld_hybrid_siglip", "spn_sim_thr", "btn_refilter",
)


def scan_unlock(dialog) -> None:
    dialog._set_scan_progress_active(False)
    dialog.btn_cancel.setEnabled(False)
    _set_scan_controls_enabled(dialog, True)
    dialog._update_ref_image_actions()
    dialog._on_refilter_mode_changed()
    dialog._on_refilter_source_mode_changed()
    dialog._on_siglip_two_stage_changed()
    dialog.btn_refilter_clear.setEnabled(dialog._refilter_active)
    dialog._update_scene_clip_button_enabled()
    dialog.worker = None


def run_scan(dialog, *_args, **_kwargs) -> None:
    blocked_message = _scan_blocked_message(dialog)
    if blocked_message is not None:
        QtWidgets.QMessageBox.information(dialog, "알림", blocked_message)
        return
    path = _current_scan_path(dialog)
    if not path:
        QtWidgets.QMessageBox.information(dialog, "알림", "열린 영상이 없습니다.")
        return
    scan_args = _scan_args(dialog)
    if _try_apply_scan_cache(dialog, path, scan_args):
        return
    _lock_scan_ui(dialog)
    worker = _create_scan_worker(dialog, path, scan_args)
    _connect_scan_worker(dialog, path, scan_args, worker)
    _bind_scan_cancel(dialog)


def _scan_blocked_message(dialog) -> Optional[str]:
    if dialog.refilter_worker is not None and dialog.refilter_worker.isRunning():
        return "유사씬 탐색이 실행 중입니다. 완료 후 다시 시도하세요."
    batch_worker = getattr(dialog, "_scene_batch_worker", None)
    if batch_worker is not None and batch_worker.isRunning():
        return "순차 작업이 실행 중입니다. 완료 후 다시 시도하세요."
    return None


def _current_scan_path(dialog) -> Optional[str]:
    try:
        raw_path = dialog.host._current_media_path()
    except (AttributeError, RuntimeError):
        logger.debug("scan current media path lookup failed", exc_info=True)
        return None
    path = os.path.abspath(str(raw_path or "").strip())
    if not path:
        return None
    if not os.path.exists(path):
        logger.debug("scan current media path missing: %s", path)
        return None
    return path


def _scan_args(dialog) -> dict[str, Any]:
    ff_hwaccel = True
    setattr(dialog.host, "ffmpeg_hwaccel", ff_hwaccel)
    return {
        "thr": float(dialog.spn_thr.value()),
        "dw": int(dialog.spn_dw.value()),
        "fps": int(dialog.spn_fps.value()),
        "ffbin": _dialog_ffmpeg_bin(dialog),
        "use_ff": True,
        "ff_hwaccel": ff_hwaccel,
    }


def _try_apply_scan_cache(dialog, path: str, scan_args: dict[str, Any]) -> bool:
    if not dialog.chk_use_cache.isChecked():
        return False
    cached = scene_cache_get(path, scan_args["use_ff"], scan_args["thr"], scan_args["dw"], scan_args["fps"], ff_hwaccel=scan_args["ff_hwaccel"])
    if cached:
        return _apply_cached_scan(dialog, path, cached["pts"], cached.get("top10", []), "캐시 사용(메모리)")
    pts_disk, top_disk = load_from_disk(path, scan_args["use_ff"], scan_args["thr"], scan_args["dw"], scan_args["fps"], ff_hwaccel=scan_args["ff_hwaccel"])
    if not pts_disk:
        return False
    return _apply_cached_scan(dialog, path, pts_disk, top_disk or [], "캐시 사용(디스크)")


def _apply_cached_scan(dialog, path: str, pts, top, status: str) -> bool:
    base_pts = dialog._apply_user_threshold(pts, top)
    filtered_pts = dialog._filter_pts(base_pts, top)
    dialog._populate_from_result(path, filtered_pts, top)
    dialog.lbl_status.setText(status)
    return True


def _lock_scan_ui(dialog) -> None:
    dialog.listw.clear()
    dialog.lbl_status.setText("씬변화 준비…")
    dialog.progress.setValue(0)
    dialog._set_scan_progress_active(True)
    dialog.btn_cancel.setEnabled(True)
    _set_scan_controls_enabled(dialog, False, include_refilter_clear=True)
    for slider in dialog.weight_sliders.values():
        slider.setEnabled(False)
    QtWidgets.QApplication.processEvents()


def _set_scan_controls_enabled(dialog, enabled: bool, include_refilter_clear: bool = False) -> None:
    for name in _SCAN_CONTROL_ATTRS:
        widget = getattr(dialog, name, None)
        if widget is not None:
            widget.setEnabled(enabled)
    if include_refilter_clear:
        dialog.btn_refilter_clear.setEnabled(enabled)


def _create_scan_worker(dialog, path: str, scan_args: dict[str, Any]):
    decode_chunk_size = dialog._current_siglip_batch_size()
    if bool(scan_args["ff_hwaccel"]):
        decode_chunk_size, _scan_batch, _scan_tier, _scan_w, _scan_h = _gpu_decode_chunk_batch_limits(path)
        decode_chunk_size = int(decode_chunk_size)
    dialog.worker = SceneDetectWorker(
        path,
        scan_args["use_ff"],
        scan_args["thr"],
        scan_args["dw"],
        scan_args["fps"],
        scan_args["ffbin"],
        dialog.host,
        ff_hwaccel=scan_args["ff_hwaccel"],
        decode_chunk_size=decode_chunk_size,
    )
    dialog.worker.progress.connect(dialog.progress.setValue)
    dialog.worker.message.connect(dialog.lbl_status.setText)
    return dialog.worker


def _connect_scan_worker(dialog, path: str, scan_args: dict[str, Any], worker) -> None:
    worker.finished_ok.connect(lambda all_pts, all_rows: _scan_done_ok(dialog, path, scan_args, all_pts, all_rows))
    worker.finished_err.connect(lambda msg: _scan_done_err(dialog, msg))
    worker.start()


def _scan_done_ok(dialog, path: str, scan_args: dict[str, Any], all_pts, all_scenes_with_score) -> None:
    scene_cache_set(path, scan_args["use_ff"], scan_args["thr"], scan_args["dw"], scan_args["fps"], all_pts, all_scenes_with_score, ff_hwaccel=scan_args["ff_hwaccel"])
    store_to_disk(path, scan_args["use_ff"], scan_args["thr"], scan_args["dw"], scan_args["fps"], all_pts, all_scenes_with_score, ff_hwaccel=scan_args["ff_hwaccel"])
    base_pts = dialog._apply_user_threshold(all_pts, all_scenes_with_score)
    filtered_pts = dialog._filter_pts(base_pts, all_scenes_with_score)
    dialog._populate_from_result(path, filtered_pts, all_scenes_with_score)
    dialog._scan_unlock()


def _scan_done_err(dialog, msg: str) -> None:
    dialog._scan_unlock()
    if msg != "사용자 취소":
        QtWidgets.QMessageBox.warning(dialog, "오류", msg)
    dialog.lbl_status.setText("대기")


def _bind_scan_cancel(dialog) -> None:
    try:
        dialog.btn_cancel.clicked.disconnect()
    except TypeError:
        pass
    dialog.btn_cancel.clicked.connect(lambda: _cancel_scan(dialog))


def _cancel_scan(dialog) -> None:
    if getattr(dialog, "worker", None):
        dialog.lbl_status.setText("취소 중…")
        dialog.worker.cancel()
        dialog.btn_cancel.setEnabled(False)


def _dialog_ffmpeg_bin(dialog) -> str:
    preferred = str(getattr(getattr(dialog, "ed_ff", None), "text", lambda: "")() or "").strip()
    if not preferred:
        host = getattr(dialog, "host", None)
        preferred = str(getattr(host, "ffmpeg_path", "") or "").strip()
    ffbin = resolve_ffmpeg_bin(preferred or FFMPEG_BIN)
    try:
        if hasattr(dialog, "ed_ff"):
            dialog.ed_ff.setText(ffbin)
    except (AttributeError, RuntimeError, TypeError):
        logger.debug("scene dialog ffmpeg line edit sync skipped", exc_info=True)
    try:
        host = getattr(dialog, "host", None)
        if host is not None:
            host.ffmpeg_path = ffbin
    except (AttributeError, RuntimeError, TypeError):
        logger.debug("scene dialog host ffmpeg path sync skipped", exc_info=True)
    return ffbin
