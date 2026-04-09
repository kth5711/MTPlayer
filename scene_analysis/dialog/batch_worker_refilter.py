from typing import Dict

from scene_analysis.core.cache import refilter_cache_get, refilter_cache_set
from scene_analysis.core.media import FFMPEG_BIN
from scene_analysis.core.refilter import (
    build_scene_similarity_cache_kwargs,
    build_scene_similarity_worker_kwargs,
    run_scene_similarity,
)

from .batch_sources import (
    _build_direct_refilter_ms,
    _normalize_scene_source_ms,
    _resolve_refilter_scene_source_payload,
    _scene_filtered_points,
)


def _batch_message(worker, idx: int, total: int, base: str, text: str) -> None:
    worker.message.emit(f"[{idx + 1}/{total}] {base} | {text}")


def _refilter_source_mode(config: Dict[str, object]) -> str:
    return "scene" if bool(config.get("run_scene", True)) else "direct"


def _resolve_refilter_scene_from_history(worker, path: str, config: Dict[str, object], state: Dict[str, object]) -> str | None:
    return _resolve_refilter_scene_source_payload(
        path,
        worker.options,
        prefer_recent_history_only=(not bool(config.get("run_scene", True))),
    )[0]


def _apply_refilter_source_payload(worker, src_pts, src_top, config: Dict[str, object], state: Dict[str, object]) -> None:
    state["scene_pts"] = src_pts
    state["scene_top"] = src_top
    if bool(config.get("run_scene", True)):
        state["scene_source_ms"] = _scene_filtered_points(src_pts, src_top, worker.options)
    else:
        state["scene_source_ms"] = _normalize_scene_source_ms(src_pts)
    if not state["scene_source_ms"]:
        state["scene_source_ms"] = [0]


def _ensure_refilter_scene_source(
    worker,
    path: str,
    idx: int,
    total: int,
    base: str,
    config: Dict[str, object],
    state: Dict[str, object],
) -> str:
    source_mode = _refilter_source_mode(config)
    if source_mode != "scene":
        state["scene_source_ms"] = _build_direct_refilter_ms(
            path, int(config.get("refilter_direct_sec", 2))
        )
        return source_mode
    if state.get("scene_source_ms"):
        return source_mode
    src_cache_label, src_pts, src_top = _resolve_refilter_scene_source_payload(
        path,
        worker.options,
        prefer_recent_history_only=(not bool(config.get("run_scene", True))),
    )
    if src_cache_label == "결과기록":
        worker.message.emit(f"[{idx + 1}/{total}] {base} 유사씬 소스로 최근 씬변화 결과기록 사용")
    if src_cache_label is None:
        raise RuntimeError(
            "유사씬 소스가 씬변화 결과인데 기존 결과가 없습니다. '씬변화'도 체크하거나 직행 샘플을 사용하세요."
        )
    _apply_refilter_source_payload(worker, src_pts, src_top, config, state)
    return source_mode


def _refilter_cache_kwargs(config: Dict[str, object]) -> Dict[str, object]:
    return build_scene_similarity_cache_kwargs(
        siglip_model_id=str(config.get("siglip_model_id") or ""),
        agg_mode=str(config.get("agg_mode") or "max"),
        kofn_k=int(config.get("kofn_k", 1)),
        frame_profile=str(config.get("frame_profile") or "normal"),
        sample_texts=list(config.get("sample_texts") or []),
        siglip_adapter_path=str(config.get("siglip_adapter_path") or ""),
        sampling_mode=str(config.get("sampling_mode") or "start_frame"),
        siglip_two_stage=bool(config.get("siglip_two_stage", False)),
        siglip_stage2_ratio=float(config.get("siglip_stage2_ratio", 0.35)),
        siglip_decode_hwaccel=bool(config.get("siglip_decode_hwaccel", True)),
        siglip_ffmpeg_scale_w=int(config.get("siglip_ffmpeg_scale_w", 0)),
    )


def _load_refilter_cache(path: str, config: Dict[str, object], state: Dict[str, object], cache_kwargs: Dict[str, object]) -> None:
    if not bool(config.get("use_cache", True)):
        return
    cached_pairs = refilter_cache_get(
        path,
        list(config.get("sample_paths") or []),
        str(config.get("refilter_mode") or "siglip2"),
        list(state.get("scene_source_ms") or []),
        **cache_kwargs,
    )
    if cached_pairs is not None:
        state["refilter_pairs"] = list(cached_pairs or [])
        state["refilter_cache_label"] = "메모리/디스크"


def _build_refilter_worker_kwargs(path: str, config: Dict[str, object]) -> Dict[str, object]:
    setup = build_scene_similarity_worker_kwargs(
        path,
        siglip_model_id=str(config.get("siglip_model_id") or ""),
        agg_mode=str(config.get("agg_mode") or "max"),
        kofn_k=int(config.get("kofn_k", 1)),
        frame_profile=str(config.get("frame_profile") or "normal"),
        sample_texts=list(config.get("sample_texts") or []),
        siglip_adapter_path=str(config.get("siglip_adapter_path") or ""),
        sampling_mode=str(config.get("sampling_mode") or "start_frame"),
        siglip_batch_size=int(config.get("siglip_batch_size", 64)),
        siglip_decode_hwaccel=bool(config.get("siglip_decode_hwaccel", True)),
        siglip_two_stage=bool(config.get("siglip_two_stage", False)),
        siglip_stage2_ratio=float(config.get("siglip_stage2_ratio", 0.35)),
        siglip_ffmpeg_bin=str(config.get("siglip_ffmpeg_bin") or FFMPEG_BIN),
        siglip_ffmpeg_scale_w=int(config.get("siglip_ffmpeg_scale_w", 0)),
        siglip_scene_feature_cache=bool(config.get("siglip_scene_feature_cache", True)),
    )
    return dict(setup.get("worker_kwargs") or {})


def _run_refilter_similarity(
    worker,
    path: str,
    idx: int,
    total: int,
    base: str,
    config: Dict[str, object],
    state: Dict[str, object],
) -> None:
    state["item_cache_only"] = False
    state["refilter_pairs"] = run_scene_similarity(
        path,
        list(state.get("scene_source_ms") or []),
        list(config.get("sample_paths") or []),
        progress_cb=lambda p: worker.current_progress.emit(
            worker._map_stage_progress(50 if bool(config.get("run_scene", True)) else 0, 100, int(p))
        ),
        message_cb=lambda msg: _batch_message(worker, idx, total, base, msg),
        cancel_cb=lambda: bool(worker._cancel),
        mode=str(config.get("refilter_mode") or "siglip2"),
        normalize_scores=True,
        **_build_refilter_worker_kwargs(path, config),
    )


def _store_refilter_cache(path: str, source_mode: str, config: Dict[str, object], state: Dict[str, object], cache_kwargs: Dict[str, object]) -> None:
    store_kwargs = dict(cache_kwargs)
    store_kwargs.update(
        {
            "source_mode": source_mode,
            "direct_interval_sec": (
                int(config.get("refilter_direct_sec", 2)) if source_mode == "direct" else 0
            ),
            "sim_threshold": float(config.get("sim_thr", 0.70)),
        }
    )
    refilter_cache_set(
        path,
        list(config.get("sample_paths") or []),
        str(config.get("refilter_mode") or "siglip2"),
        list(state.get("scene_source_ms") or []),
        list(state.get("refilter_pairs") or []),
        **store_kwargs,
    )


def _run_refilter_batch_stage(
    worker,
    path: str,
    idx: int,
    total: int,
    base: str,
    config: Dict[str, object],
    state: Dict[str, object],
) -> None:
    if not bool(config.get("run_refilter", False)):
        return
    worker._raise_if_cancelled()
    source_mode = _ensure_refilter_scene_source(worker, path, idx, total, base, config, state)
    if not state.get("scene_source_ms"):
        raise RuntimeError("유사씬 대상 시점을 만들지 못했습니다.")
    cache_kwargs = _refilter_cache_kwargs(config)
    _load_refilter_cache(path, config, state, cache_kwargs)
    if state.get("refilter_cache_label") is not None:
        worker.current_progress.emit(100)
        worker.message.emit(f"[{idx + 1}/{total}] {base} 유사씬 캐시 사용")
        return
    _run_refilter_similarity(worker, path, idx, total, base, config, state)
    _store_refilter_cache(path, source_mode, config, state, cache_kwargs)
