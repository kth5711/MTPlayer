from typing import Any, Optional
import logging
import os

from PyQt6 import QtWidgets

from scene_analysis.core.cache import _normalize_sample_paths, refilter_cache_get
from scene_analysis.core.media import FFMPEG_BIN, resolve_ffmpeg_bin
from scene_analysis.core.refilter import (
    build_scene_similarity_cache_kwargs,
    build_scene_similarity_worker_kwargs,
    build_scene_similarity_worker_plan,
)


logger = logging.getLogger(__name__)


def prepare_similarity_refilter(dialog) -> Optional[dict[str, Any]]:
    if not _ensure_refilter_can_start(dialog):
        return None
    sample_paths, sample_texts = _load_sample_inputs(dialog)
    if not sample_paths and not sample_texts:
        QtWidgets.QMessageBox.information(dialog, "알림", "샘플 이미지 또는 텍스트를 입력하세요.")
        return None
    path = _resolve_video_path(dialog)
    if not path:
        QtWidgets.QMessageBox.warning(dialog, "오류", "현재 영상 경로를 찾을 수 없습니다.")
        return None
    dialog.current_path = path
    source_mode, source = _resolve_refilter_source(dialog)
    if not source:
        return None
    return _prepared_refilter_context(dialog, path, source_mode, source, sample_paths, sample_texts)


def _ensure_refilter_can_start(dialog) -> bool:
    if getattr(dialog, "worker", None) is not None:
        QtWidgets.QMessageBox.information(dialog, "알림", "씬변화가 실행 중입니다.")
        return False
    batch_worker = getattr(dialog, "_scene_batch_worker", None)
    if batch_worker is not None and batch_worker.isRunning():
        QtWidgets.QMessageBox.information(dialog, "알림", "순차 작업이 실행 중입니다.")
        return False
    return not (dialog.refilter_worker is not None and dialog.refilter_worker.isRunning())


def _load_sample_inputs(dialog) -> tuple[list[str], list[str]]:
    return [path for path in _normalize_sample_paths(dialog.sample_image_paths) if os.path.exists(path)], dialog._current_sample_texts()


def _prepared_refilter_context(
    dialog,
    path: str,
    source_mode: str,
    source: list[tuple[int, float]],
    sample_paths: list[str],
    sample_texts: list[str],
) -> dict[str, Any]:
    ms_list = [int(ms) for ms, _ in source]
    shared = _shared_refilter_settings(dialog)
    cache_kwargs = _build_cache_kwargs(shared, sample_texts)
    worker_setup = _build_worker_setup(dialog, path, shared, sample_texts)
    worker_plan = build_scene_similarity_worker_plan(len(ms_list), shared["siglip_device"])
    prep_note = f"{str(worker_setup.get('gpu_auto_note') or '')}{str(worker_plan.get('worker_note') or '')}"
    _show_prepare_status(dialog, source_mode, len(ms_list), prep_note)
    return _prepared_payload(
        path,
        source_mode,
        source,
        sample_paths,
        sample_texts,
        ms_list,
        cache_kwargs,
        worker_setup,
        worker_plan,
        prep_note,
    )


def _build_cache_kwargs(shared: dict[str, Any], sample_texts: list[str]) -> dict[str, Any]:
    return build_scene_similarity_cache_kwargs(
        pose_weights=None,
        siglip_model_id=shared["siglip_model_id"],
        agg_mode=shared["agg_mode"],
        kofn_k=shared["kofn_k"],
        frame_profile=shared["frame_profile"],
        hybrid_siglip_weight=0.55,
        sample_texts=sample_texts,
        siglip_adapter_path=shared["siglip_adapter_path"],
        sampling_mode=shared["sampling_mode"],
        siglip_two_stage=shared["siglip_two_stage"],
        siglip_stage2_ratio=shared["siglip_stage2_ratio"],
        siglip_decode_hwaccel=shared["siglip_decode_hwaccel"],
        siglip_ffmpeg_scale_w=shared["siglip_decode_scale_w"],
    )


def _build_worker_setup(
    dialog,
    path: str,
    shared: dict[str, Any],
    sample_texts: list[str],
) -> dict[str, Any]:
    return build_scene_similarity_worker_kwargs(
        path,
        pose_weights=None,
        siglip_model_id=shared["siglip_model_id"],
        agg_mode=shared["agg_mode"],
        kofn_k=shared["kofn_k"],
        frame_profile=shared["frame_profile"],
        hybrid_siglip_weight=0.55,
        sample_texts=sample_texts,
        siglip_adapter_path=shared["siglip_adapter_path"],
        sampling_mode=shared["sampling_mode"],
        siglip_batch_size=shared["siglip_batch_size"],
        siglip_decode_hwaccel=shared["siglip_decode_hwaccel"],
        siglip_two_stage=shared["siglip_two_stage"],
        siglip_stage2_ratio=shared["siglip_stage2_ratio"],
        siglip_ffmpeg_bin=_dialog_ffmpeg_bin(dialog),
        siglip_ffmpeg_scale_w=shared["siglip_decode_scale_w"],
        siglip_scene_feature_cache=shared["siglip_scene_feature_cache"],
    )


def _prepared_payload(
    path: str,
    source_mode: str,
    source: list[tuple[int, float]],
    sample_paths: list[str],
    sample_texts: list[str],
    ms_list: list[int],
    cache_kwargs: dict[str, Any],
    worker_setup: dict[str, Any],
    worker_plan: dict[str, Any],
    prep_note: str,
) -> dict[str, Any]:
    worker_kwargs = dict(worker_setup.get("worker_kwargs") or {})
    cached_pairs = refilter_cache_get(path, sample_paths, "siglip2", ms_list, **cache_kwargs)
    return {
        "mode": "siglip2",
        "sample_paths": sample_paths,
        "sample_texts": sample_texts,
        "source_mode": source_mode,
        "source": source,
        "ms_list": ms_list,
        "cache_kwargs": cache_kwargs,
        "cached_pairs": cached_pairs,
        "worker_kwargs": worker_kwargs,
        "worker_count_eff": int(worker_plan.get("worker_count_eff", 1) or 1),
        "prep_note": prep_note,
    }


def _resolve_video_path(dialog) -> str:
    path = str(getattr(dialog, "current_path", "") or "").strip()
    if path and os.path.exists(path):
        return path
    try:
        path = str(dialog.host._current_media_path() or "").strip()
    except (AttributeError, RuntimeError):
        logger.debug("similarity refilter current media path fallback failed", exc_info=True)
        path = ""
    return path if path and os.path.exists(path) else ""


def _resolve_refilter_source(dialog) -> tuple[str, list[tuple[int, float]]]:
    source_mode = dialog._current_refilter_source_mode()
    if source_mode == "direct":
        source = dialog._build_direct_refilter_source(dialog._current_refilter_direct_sec())
        if not source:
            QtWidgets.QMessageBox.information(dialog, "알림", "직행 샘플 시점을 생성하지 못했습니다.")
            return source_mode, []
        dialog._refilter_source_override_ms = [int(ms) for ms, _ in source]
        return source_mode, source
    dialog._refilter_source_override_ms = []
    source = list(dialog._refilter_source_data or dialog.all_scenes_data or [])
    if not source:
        QtWidgets.QMessageBox.information(dialog, "알림", "재필터할 씬 결과가 없습니다.")
        return source_mode, []
    return source_mode, source


def _shared_refilter_settings(dialog) -> dict[str, Any]:
    return {
        "agg_mode": dialog._current_refilter_agg_mode(),
        "kofn_k": dialog._current_kofn_k(),
        "frame_profile": dialog._current_frame_profile(),
        "sampling_mode": dialog._current_refilter_sampling_mode(),
        "siglip_decode_hwaccel": (not bool(dialog.chk_cpu_decode.isChecked())) if hasattr(dialog, "chk_cpu_decode") else True,
        "siglip_two_stage": dialog._current_siglip_two_stage(),
        "siglip_stage2_ratio": dialog._current_siglip_stage2_ratio(),
        "siglip_batch_size": dialog._current_siglip_batch_size(),
        "siglip_decode_scale_w": dialog._current_siglip_decode_scale_w(),
        "siglip_scene_feature_cache": dialog._current_siglip_scene_feature_cache_enabled(),
        "siglip_model_id": dialog._current_siglip_model_id(),
        "siglip_adapter_path": dialog._current_siglip_adapter_path(),
        "siglip_device": dialog._siglip_runtime_device(),
    }


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
    return ffbin


def _show_prepare_status(dialog, source_mode: str, ms_count: int, prep_note: str) -> None:
    if source_mode == "direct":
        interval_sec = dialog._current_refilter_direct_sec()
        dialog.lbl_status.setText(f"SigLIP2 직행 샘플 준비: {ms_count}개 (간격 {interval_sec}s{prep_note})")
        QtWidgets.QApplication.processEvents()
        return
    if prep_note:
        dialog.lbl_status.setText(f"SigLIP2 준비 중…{prep_note}")
        QtWidgets.QApplication.processEvents()
