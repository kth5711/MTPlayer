import os
from typing import Dict

from scene_analysis.core.cache import _normalize_sample_paths, _normalize_sample_texts
from scene_analysis.core.media import FFMPEG_BIN, resolve_ffmpeg_bin


def _scene_batch_run_options(options: Dict[str, object]) -> Dict[str, object]:
    return {
        "use_ff": bool(options.get("use_ff", True)),
        "ff_hwaccel": bool(options.get("ff_hwaccel", False)),
        "thr": float(options.get("thr", 0.35)),
        "dw": int(options.get("dw", 320)),
        "fps": int(options.get("fps", 5)),
        "ffbin": resolve_ffmpeg_bin(str(options.get("ffbin") or FFMPEG_BIN)),
        "use_cache": bool(options.get("use_cache", True)),
        "run_scene": bool(options.get("run_scene", True)),
        "run_refilter": bool(options.get("run_refilter", False)),
        "decode_chunk_size": int(options.get("decode_chunk_size", 64)),
        "sim_thr": float(options.get("sim_thr", 0.70)),
    }


def _scene_batch_similarity_options(options: Dict[str, object]) -> Dict[str, object]:
    return {
        "refilter_mode": str(options.get("refilter_mode") or "siglip2"),
        "refilter_direct_sec": max(1, int(options.get("refilter_direct_sec", 2))),
        "sample_paths": [
            p for p in _normalize_sample_paths(options.get("sample_image_paths") or []) if p
        ],
        "sample_texts": _normalize_sample_texts(options.get("sample_texts") or []),
        "agg_mode": str(options.get("agg_mode") or "max"),
        "kofn_k": max(1, int(options.get("kofn_k", 1))),
        "frame_profile": str(options.get("frame_profile") or "normal"),
        "sampling_mode": str(options.get("sampling_mode") or "start_frame"),
        "siglip_model_id": str(options.get("siglip_model_id") or "").strip(),
        "siglip_adapter_path": str(options.get("siglip_adapter_path") or "").strip(),
        "siglip_decode_hwaccel": bool(options.get("siglip_decode_hwaccel", True)),
        "siglip_two_stage": bool(options.get("siglip_two_stage", False)),
        "siglip_stage2_ratio": float(options.get("siglip_stage2_ratio", 0.35)),
        "siglip_scene_feature_cache": bool(options.get("siglip_scene_feature_cache", True)),
        "siglip_ffmpeg_scale_w": int(options.get("siglip_ffmpeg_scale_w", 0)),
        "siglip_batch_size": int(options.get("siglip_batch_size", 64)),
        "siglip_ffmpeg_bin": str(options.get("siglip_ffmpeg_bin") or FFMPEG_BIN),
    }


def _scene_batch_worker_options(options: Dict[str, object]) -> Dict[str, object]:
    merged = _scene_batch_run_options(options)
    merged.update(_scene_batch_similarity_options(options))
    return merged


def _new_scene_batch_item_state() -> Dict[str, object]:
    return {
        "scene_pts": [],
        "scene_top": [],
        "scene_source_ms": [],
        "refilter_pairs": [],
        "item_cache_only": True,
        "scene_cache_label": None,
        "refilter_cache_label": None,
    }


def _scene_batch_base_name(path: str) -> str:
    base = os.path.basename(str(path or "").strip())
    return base or str(path or "")


def _emit_scene_batch_item_start(worker, path: str, idx: int, total: int, base: str) -> None:
    worker.item_started.emit(path)
    worker.current_progress.emit(0)
    worker.overall_progress.emit(int((idx / max(1, total)) * 100))
    worker.message.emit(f"[{idx + 1}/{total}] {base} 준비 중…")


def _scene_batch_result(config: Dict[str, object], state: Dict[str, object]) -> Dict[str, object]:
    run_scene = bool(config.get("run_scene", True))
    run_refilter = bool(config.get("run_refilter", False))
    item_cache_only = bool(state.get("item_cache_only"))
    scene_source_ms = list(state.get("scene_source_ms") or [])
    refilter_pairs = list(state.get("refilter_pairs") or [])
    sim_thr = float(config.get("sim_thr", 0.70))
    scene_count = len(scene_source_ms) if run_scene else 0

    if run_refilter:
        hit_count = sum(1 for _ms, sim in refilter_pairs if float(sim) >= sim_thr)
        return {
            "count_text": f"{int(hit_count)}/{len(scene_source_ms)}",
            "status": (
                "씬+유사 캐시"
                if item_cache_only and run_scene
                else ("유사씬 캐시" if item_cache_only else ("씬+유사 완료" if run_scene else "유사씬 완료"))
            ),
            "message": (
                f"완료 (후보 {len(scene_source_ms)}개, 통과 {int(hit_count)}개, 임계값 {sim_thr:.2f})"
            ),
            "item_cache_only": item_cache_only,
        }

    return {
        "count_text": str(int(scene_count)),
        "status": "씬변화 캐시" if item_cache_only else "씬변화 완료",
        "message": f"완료 ({int(scene_count)}개)",
        "item_cache_only": item_cache_only,
    }
