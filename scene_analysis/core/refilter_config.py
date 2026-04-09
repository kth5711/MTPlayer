from __future__ import annotations

from typing import Any, Dict, List, Optional

from .cache import _normalize_sample_texts
from .media import SIGLIP_BATCH_DEFAULT, _normalize_siglip_batch_size, resolve_ffmpeg_bin
from .similarity import (
    _auto_decode_chunk_batch_limits,
    _cpu_auto_worker_count,
    _normalize_adapter_path,
    _normalize_refilter_sampling_mode,
    _normalize_siglip_decode_scale_w,
)


def build_scene_similarity_cache_kwargs(
    *,
    pose_weights: Optional[dict] = None,
    siglip_model_id: str = "",
    agg_mode: str = "max",
    kofn_k: int = 1,
    frame_profile: str = "normal",
    hybrid_siglip_weight: float = 0.55,
    sample_texts: Optional[List[str]] = None,
    siglip_adapter_path: str = "",
    sampling_mode: str = "start_frame",
    siglip_two_stage: bool = False,
    siglip_stage2_ratio: float = 0.35,
    siglip_decode_hwaccel: bool = True,
    siglip_ffmpeg_scale_w: int = 0,
) -> Dict[str, Any]:
    return {
        "pose_weights": pose_weights,
        "siglip_model_id": str(siglip_model_id or "").strip(),
        "agg_mode": str(agg_mode or "max"),
        "kofn_k": max(1, int(kofn_k)),
        "frame_profile": str(frame_profile or "normal"),
        "hybrid_siglip_weight": float(hybrid_siglip_weight),
        "sample_texts": _normalize_sample_texts(sample_texts or []),
        "siglip_adapter_path": _normalize_adapter_path(siglip_adapter_path),
        "sampling_mode": _normalize_refilter_sampling_mode(sampling_mode),
        "siglip_two_stage": bool(siglip_two_stage), "siglip_stage2_ratio": float(siglip_stage2_ratio),
        "siglip_decode_hwaccel": bool(siglip_decode_hwaccel),
        "siglip_ffmpeg_scale_w": _normalize_siglip_decode_scale_w(siglip_ffmpeg_scale_w, default=0),
    }


def _scene_similarity_batch_and_note(video_path: str, siglip_batch_size: int, siglip_decode_hwaccel: bool):
    _auto_chunk, auto_batch, tier, video_w, video_h = _auto_decode_chunk_batch_limits(
        video_path,
        prefer_gpu_decode=bool(siglip_decode_hwaccel),
    )
    batch_size = int(auto_batch)
    mode_label = "GPU" if bool(siglip_decode_hwaccel) else "CPU"
    if int(video_w) > 0 and int(video_h) > 0:
        note = f", 자동 Batch/Chunk={int(auto_batch)} ({mode_label} {str(tier).upper()} {int(video_w)}x{int(video_h)})"
    else:
        note = f", 자동 Batch/Chunk={int(auto_batch)} ({mode_label} {str(tier).upper()})"
    return int(batch_size), note


def _scene_similarity_worker_result(
    video_path: str,
    cache_kwargs: Dict[str, Any],
    siglip_batch_size: int,
    siglip_decode_hwaccel: bool,
    siglip_ffmpeg_bin: str,
    siglip_scene_feature_cache: bool,
) -> Dict[str, Any]:
    batch_size, gpu_auto_note = _scene_similarity_batch_and_note(
        video_path, siglip_batch_size, siglip_decode_hwaccel
    )
    worker_kwargs = dict(cache_kwargs)
    worker_kwargs.update(
        {
            "siglip_batch_size": int(batch_size),
            "siglip_ffmpeg_bin": resolve_ffmpeg_bin(str(siglip_ffmpeg_bin or "").strip()),
            "siglip_scene_feature_cache": bool(siglip_scene_feature_cache),
        }
    )
    return {
        "cache_kwargs": cache_kwargs,
        "worker_kwargs": worker_kwargs,
        "siglip_batch_size": int(batch_size),
        "gpu_auto_note": gpu_auto_note,
    }


def _scene_similarity_cache_kwargs_from_params(params: Dict[str, Any]) -> Dict[str, Any]:
    return build_scene_similarity_cache_kwargs(
        pose_weights=params.get("pose_weights"),
        siglip_model_id=str(params.get("siglip_model_id") or ""),
        agg_mode=str(params.get("agg_mode") or "max"),
        kofn_k=int(params.get("kofn_k") or 1),
        frame_profile=str(params.get("frame_profile") or "normal"),
        hybrid_siglip_weight=float(params.get("hybrid_siglip_weight") or 0.55),
        sample_texts=params.get("sample_texts"),
        siglip_adapter_path=str(params.get("siglip_adapter_path") or ""),
        sampling_mode=str(params.get("sampling_mode") or "start_frame"),
        siglip_two_stage=bool(params.get("siglip_two_stage")),
        siglip_stage2_ratio=float(params.get("siglip_stage2_ratio") or 0.35),
        siglip_decode_hwaccel=bool(params.get("siglip_decode_hwaccel", True)),
        siglip_ffmpeg_scale_w=int(params.get("siglip_ffmpeg_scale_w") or 0),
    )


def build_scene_similarity_worker_kwargs(
    video_path: str,
    *,
    pose_weights: Optional[dict] = None,
    siglip_model_id: str = "",
    agg_mode: str = "max",
    kofn_k: int = 1,
    frame_profile: str = "normal",
    hybrid_siglip_weight: float = 0.55,
    sample_texts: Optional[List[str]] = None,
    siglip_adapter_path: str = "",
    sampling_mode: str = "start_frame",
    siglip_batch_size: int = SIGLIP_BATCH_DEFAULT,
    siglip_decode_hwaccel: bool = True,
    siglip_two_stage: bool = False,
    siglip_stage2_ratio: float = 0.35,
    siglip_ffmpeg_bin: str = "",
    siglip_ffmpeg_scale_w: int = 0,
    siglip_scene_feature_cache: bool = True,
) -> Dict[str, Any]:
    params = locals()
    cache_kwargs = _scene_similarity_cache_kwargs_from_params(params)
    return _scene_similarity_worker_result(
        video_path,
        cache_kwargs,
        siglip_batch_size,
        siglip_decode_hwaccel,
        siglip_ffmpeg_bin,
        siglip_scene_feature_cache,
    )


def build_scene_similarity_worker_plan(scene_count: int, siglip_device: str) -> Dict[str, Any]:
    if str(siglip_device or "").strip().lower().startswith("cuda"):
        return {"worker_count_eff": 1, "worker_note": ", 자동워커=1(GPU)"}
    worker_count_eff, cpu_cores = _cpu_auto_worker_count(max(1, int(scene_count)), ratio=0.7)
    cpu_cap = max(1, int(float(max(1, int(cpu_cores))) * 0.7))
    return {
        "worker_count_eff": int(worker_count_eff),
        "worker_note": f", 자동워커={int(worker_count_eff)}(CPU {int(cpu_cores)}코어, 상한 {int(cpu_cap)})",
    }


__all__ = [
    "build_scene_similarity_cache_kwargs",
    "build_scene_similarity_worker_kwargs",
    "build_scene_similarity_worker_plan",
]
