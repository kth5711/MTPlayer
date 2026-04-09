from __future__ import annotations

from typing import Any, Dict, List, Optional
import hashlib
import os
import time

from .cache import (
    REFILTER_ALGO_VERSION,
    REFILTER_FRAME_PROFILES,
    SIGLIP_SCENE_FEATURE_CACHE_ALGO_VERSION,
    _CACHE_LOCK,
    _REFILTER_CACHE,
    _SIGLIP_SCENE_FEATURE_CACHE,
    _default_cache_dir,
    _file_sig_for_cache,
    _normalize_adapter_path,
    _normalize_pose_weights,
    _normalize_refilter_agg_mode,
    _normalize_refilter_mode,
    _normalize_refilter_sampling_mode,
    _normalize_sample_paths,
    _normalize_sample_texts,
    _npz_scalar_int,
    _normalize_scene_ms,
    _path_signature_fields,
    _payload_video_signature,
    _normalize_siglip_decode_scale_w,
    _pose_weight_signature,
    _read_json_dict,
    _read_npz_dict,
    _sample_sigs_for_cache,
    _sample_text_sigs_for_cache,
    _scene_ms_digest,
    _siglip_decode_scale_signature,
    _video_paths_match,
    _write_json_atomic,
    _write_npz_atomic,
)
from .refilter_feature_rows import (
    _siglip_scene_feature_maps_to_arrays,
    _siglip_scene_feature_payload_to_maps,
)


def _refilter_cache_key(
    video_path: str,
    sample_image_paths: List[str],
    mode: str,
    scene_ms: List[int],
    pose_weights: Optional[dict] = None,
    siglip_model_id: str = "",
    siglip_adapter_path: str = "",
    sample_texts: Optional[List[str]] = None,
    agg_mode: str = "max",
    kofn_k: int = 1,
    frame_profile: str = "normal",
    sampling_mode: str = "start_frame",
    hybrid_siglip_weight: float = 0.55,
    siglip_two_stage: bool = False,
    siglip_stage2_ratio: float = 0.35,
    siglip_decode_hwaccel: bool = True,
    siglip_ffmpeg_scale_w: int = 0,
) -> str:
    v = _file_sig_for_cache(video_path)
    s = _sample_sigs_for_cache(sample_image_paths)
    t = _sample_text_sigs_for_cache(sample_texts or [])
    mode_norm = _normalize_refilter_mode(mode)
    weight_sig = _pose_weight_signature(pose_weights) if mode_norm in ("pose_comp", "hybrid") else "-"
    siglip_sig = str(siglip_model_id or "").strip() if mode_norm in ("siglip2", "hybrid") else "-"
    adapter_sig = _normalize_adapter_path(siglip_adapter_path) if mode_norm in ("siglip2", "hybrid") else "-"
    text_sig = t if mode_norm in ("siglip2", "hybrid") else "-"
    agg_norm = _normalize_refilter_agg_mode(agg_mode)
    frame_norm = _normalized_frame_profile(frame_profile)
    sampling_norm = _normalize_refilter_sampling_mode(sampling_mode)
    hybrid_sig = f"{max(0.0, min(1.0, float(hybrid_siglip_weight))):.4f}" if mode_norm == "hybrid" else "-"
    two_stage_sig = "1" if (mode_norm == "siglip2" and bool(siglip_two_stage)) else "0"
    ratio_sig = f"{max(0.05, min(1.0, float(siglip_stage2_ratio))):.4f}" if mode_norm == "siglip2" else "-"
    decode_sig = "torchcodec-first+opencv" if mode_norm == "siglip2" else "-"
    scale_sig = _siglip_decode_scale_signature(siglip_ffmpeg_scale_w) if mode_norm == "siglip2" else "-"
    sig = (
        f"{REFILTER_ALGO_VERSION}|{v}|{s}|{text_sig}|{mode_norm}|{weight_sig}|{siglip_sig}|{adapter_sig}|"
        f"{agg_norm}|{max(1, int(kofn_k))}|{frame_norm}|{sampling_norm}|{hybrid_sig}|{two_stage_sig}|"
        f"{ratio_sig}|{decode_sig}|{scale_sig}|{_scene_ms_digest(scene_ms)}"
    )
    return hashlib.md5(sig.encode("utf-8")).hexdigest()


def _refilter_cache_disk_path(key: str) -> str:
    return os.path.join(_default_cache_dir(), f"refilter_{key}.json")


def _siglip_scene_feature_cache_key(
    video_path: str,
    scene_ms: List[int],
    *,
    siglip_model_id: str = "",
    siglip_adapter_path: str = "",
    frame_profile: str = "normal",
    sampling_mode: str = "start_frame",
    siglip_ffmpeg_scale_w: int = 0,
) -> str:
    sig = (
        f"{SIGLIP_SCENE_FEATURE_CACHE_ALGO_VERSION}|{_file_sig_for_cache(video_path)}|"
        f"{str(siglip_model_id or '').strip()}|{_normalize_adapter_path(siglip_adapter_path)}|"
        f"{_normalized_frame_profile(frame_profile)}|{_normalize_refilter_sampling_mode(sampling_mode)}|"
        f"{_siglip_decode_scale_signature(siglip_ffmpeg_scale_w)}|"
        f"{_scene_ms_digest(_normalize_scene_ms(scene_ms))}"
    )
    return hashlib.md5(sig.encode("utf-8")).hexdigest()


def _siglip_scene_feature_cache_disk_path(key: str) -> str:
    return os.path.join(_default_cache_dir(), f"siglip_scene_{key}.npz")


def _normalized_frame_profile(frame_profile: str) -> str:
    profile = str(frame_profile or "").strip().lower()
    return profile if profile in REFILTER_FRAME_PROFILES else "normal"


def _siglip_payload_video_signature(payload: dict) -> tuple[int, int]:
    try:
        mtime_ns = _npz_scalar_int(payload.get("video_mtime_ns"), 0)
    except Exception:
        mtime_ns = 0
    try:
        size = _npz_scalar_int(payload.get("video_size"), 0)
    except Exception:
        size = 0
    return (int(mtime_ns), int(size))


def _refilter_request_meta(
    sample_image_paths: List[str],
    mode: str,
    scene_ms: List[int],
    pose_weights: Optional[dict],
    siglip_model_id: str,
    siglip_adapter_path: str,
    sample_texts: Optional[List[str]],
    agg_mode: str,
    kofn_k: int,
    frame_profile: str,
    sampling_mode: str,
    hybrid_siglip_weight: float,
    siglip_two_stage: bool,
    siglip_stage2_ratio: float,
    siglip_ffmpeg_scale_w: int,
) -> dict:
    mode_norm = _normalize_refilter_mode(mode)
    return {
        "sample_image_paths": _normalize_sample_paths(sample_image_paths),
        "sample_texts": _normalize_sample_texts(sample_texts or []) if mode_norm in ("siglip2", "hybrid") else [],
        "scene_ms": _normalize_scene_ms(scene_ms),
        "mode": mode_norm,
        "pose_weights": _normalize_pose_weights(pose_weights) if mode_norm in ("pose_comp", "hybrid") else None,
        "siglip_model_id": str(siglip_model_id or "").strip() if mode_norm in ("siglip2", "hybrid") else None,
        "siglip_adapter_path": _normalize_adapter_path(siglip_adapter_path) if mode_norm in ("siglip2", "hybrid") else None,
        "agg_mode": _normalize_refilter_agg_mode(agg_mode),
        "kofn_k": max(1, int(kofn_k)),
        "frame_profile": _normalized_frame_profile(frame_profile),
        "sampling_mode": _normalize_refilter_sampling_mode(sampling_mode),
        "hybrid_siglip_weight": round(max(0.0, min(1.0, float(hybrid_siglip_weight))), 4) if mode_norm == "hybrid" else None,
        "siglip_two_stage": bool(siglip_two_stage) if mode_norm == "siglip2" else False,
        "siglip_stage2_ratio": round(max(0.05, min(1.0, float(siglip_stage2_ratio))), 4) if mode_norm == "siglip2" else None,
        "siglip_ffmpeg_scale_w": _normalize_siglip_decode_scale_w(siglip_ffmpeg_scale_w, default=0) if mode_norm == "siglip2" else 0,
    }


def _refilter_payload_matches_request(
    payload: dict,
    video_path: str,
    sample_image_paths: List[str],
    mode: str,
    scene_ms: List[int],
    pose_weights: Optional[dict],
    siglip_model_id: str,
    siglip_adapter_path: str,
    sample_texts: Optional[List[str]],
    agg_mode: str,
    kofn_k: int,
    frame_profile: str,
    sampling_mode: str,
    hybrid_siglip_weight: float,
    siglip_two_stage: bool,
    siglip_stage2_ratio: float,
    siglip_ffmpeg_scale_w: int,
) -> bool:
    stored_path = str(payload.get("video_path") or "")
    stored_mtime_ns, stored_size = _payload_video_signature(payload)
    if not _video_paths_match(video_path, stored_path, stored_mtime_ns, stored_size):
        return False
    expected = _refilter_request_meta(
        sample_image_paths,
        mode,
        scene_ms,
        pose_weights,
        siglip_model_id,
        siglip_adapter_path,
        sample_texts,
        agg_mode,
        kofn_k,
        frame_profile,
        sampling_mode,
        hybrid_siglip_weight,
        siglip_two_stage,
        siglip_stage2_ratio,
        siglip_ffmpeg_scale_w,
    )
    payload_meta = _refilter_request_meta(
        payload.get("sample_image_paths") or [],
        str(payload.get("mode") or "siglip2"),
        payload.get("scene_ms") or [],
        payload.get("pose_weights"),
        str(payload.get("siglip_model_id") or ""),
        str(payload.get("siglip_adapter_path") or ""),
        payload.get("sample_texts") or [],
        str(payload.get("agg_mode") or "max"),
        int(payload.get("kofn_k", 1) or 1),
        str(payload.get("frame_profile") or "normal"),
        str(payload.get("sampling_mode") or "start_frame"),
        float(payload.get("hybrid_siglip_weight", 0.55) or 0.55),
        bool(payload.get("siglip_two_stage", False)),
        float(payload.get("siglip_stage2_ratio", 0.35) or 0.35),
        int(payload.get("siglip_ffmpeg_scale_w", 0) or 0),
    )
    return payload_meta == expected


def _siglip_scene_feature_arrays(scene_ms, coarse_counts, coarse_feats, full_counts, full_feats):
    try:
        import numpy as np  # type: ignore
    except Exception:
        return None
    arrays = {
        "scene_ms": np.asarray(_normalize_scene_ms(scene_ms), dtype=np.int64),
        "coarse_counts": np.asarray(coarse_counts, dtype=np.int32).reshape(-1),
        "coarse_feats": np.asarray(coarse_feats, dtype=np.float16),
        "full_counts": np.asarray(full_counts, dtype=np.int32).reshape(-1),
        "full_feats": np.asarray(full_feats, dtype=np.float16),
    }
    arrays["coarse_feats"] = _reshape_feature_array(arrays["coarse_feats"])
    arrays["full_feats"] = _reshape_feature_array(arrays["full_feats"])
    return arrays


def _reshape_feature_array(arr):
    if int(getattr(arr, "ndim", 0)) != 1:
        return arr
    return arr.reshape(0 if int(arr.size) <= 0 else 1, -1)


def _valid_siglip_scene_feature_arrays(arrays) -> bool:
    if arrays is None:
        return False
    scene_size = int(arrays["scene_ms"].size)
    if int(arrays["coarse_counts"].size) != scene_size or int(arrays["full_counts"].size) != scene_size:
        return False
    if int(arrays["coarse_feats"].shape[0]) != int(arrays["coarse_counts"].sum()):
        return False
    if int(arrays["full_feats"].shape[0]) != int(arrays["full_counts"].sum()):
        return False
    return True


def _parse_siglip_scene_feature_payload(payload: dict, video_path: str):
    try:
        import numpy as np  # type: ignore
    except Exception:
        return None
    try:
        arrays = _siglip_scene_feature_arrays(
            payload.get("scene_ms"),
            payload.get("coarse_counts"),
            payload.get("coarse_feats"),
            payload.get("full_counts"),
            payload.get("full_feats"),
        )
        if not _valid_siglip_scene_feature_arrays(arrays):
            scene_ms, coarse_map, full_map = _siglip_scene_feature_payload_to_maps(payload)
            if not scene_ms:
                return None
            arrays = _siglip_scene_feature_maps_to_arrays(scene_ms, coarse_map, full_map)
        if not _valid_siglip_scene_feature_arrays(arrays):
            return None
        return {
            "video_path": str(np.asarray(payload.get("video_path")).reshape(-1)[0]) if payload.get("video_path") is not None else os.path.abspath(video_path or ""),
            "video_mtime_ns": _npz_scalar_int(payload.get("video_mtime_ns"), 0),
            "video_size": _npz_scalar_int(payload.get("video_size"), 0),
            "scene_ms": arrays["scene_ms"],
            "coarse_counts": arrays["coarse_counts"],
            "coarse_feats": arrays["coarse_feats"],
            "full_counts": arrays["full_counts"],
            "full_feats": arrays["full_feats"],
            "saved_at": float(np.asarray(payload.get("saved_at")).reshape(-1)[0]) if payload.get("saved_at") is not None else 0.0,
        }
    except Exception:
        return None


def siglip_scene_feature_cache_get(
    video_path: str,
    scene_ms: List[int],
    *,
    siglip_model_id: str = "",
    siglip_adapter_path: str = "",
    frame_profile: str = "normal",
    sampling_mode: str = "start_frame",
    siglip_ffmpeg_scale_w: int = 0,
):
    key = _siglip_scene_feature_cache_key(
        video_path,
        scene_ms,
        siglip_model_id=siglip_model_id,
        siglip_adapter_path=siglip_adapter_path,
        frame_profile=frame_profile,
        sampling_mode=sampling_mode,
        siglip_ffmpeg_scale_w=siglip_ffmpeg_scale_w,
    )
    with _CACHE_LOCK:
        cached = _SIGLIP_SCENE_FEATURE_CACHE.get(key)
        if isinstance(cached, dict):
            return cached
    payload = _read_npz_dict(_siglip_scene_feature_cache_disk_path(key))
    parsed = _parse_siglip_scene_feature_payload(payload, video_path)
    if parsed is None:
        payload, parsed = _find_compatible_siglip_scene_feature_cache(
            video_path,
            scene_ms,
            siglip_model_id=siglip_model_id,
            siglip_adapter_path=siglip_adapter_path,
            frame_profile=frame_profile,
            sampling_mode=sampling_mode,
            siglip_ffmpeg_scale_w=siglip_ffmpeg_scale_w,
        )
        if parsed is None:
            payload, parsed = _find_relaxed_siglip_scene_feature_cache(
                video_path,
                scene_ms,
                siglip_model_id=siglip_model_id,
                siglip_adapter_path=siglip_adapter_path,
            )
        if parsed is None:
            return None
        _store_siglip_scene_feature_cache_alias(
            key,
            video_path,
            parsed,
            payload,
            siglip_model_id=siglip_model_id,
            siglip_adapter_path=siglip_adapter_path,
            frame_profile=frame_profile,
            sampling_mode=sampling_mode,
            siglip_ffmpeg_scale_w=siglip_ffmpeg_scale_w,
        )
    with _CACHE_LOCK:
        _SIGLIP_SCENE_FEATURE_CACHE[key] = parsed
    return parsed


def _find_compatible_siglip_scene_feature_cache(
    video_path: str,
    scene_ms: List[int],
    *,
    siglip_model_id: str,
    siglip_adapter_path: str,
    frame_profile: str,
    sampling_mode: str,
    siglip_ffmpeg_scale_w: int,
):
    cache_dir = _default_cache_dir()
    try:
        with _CACHE_LOCK:
            names = sorted(os.listdir(cache_dir), reverse=True)
    except Exception:
        return {}, None
    scene_ms_norm = _normalize_scene_ms(scene_ms)
    requested_video = os.path.abspath(video_path or "")
    requested_model = str(siglip_model_id or "").strip()
    requested_adapter = _normalize_adapter_path(siglip_adapter_path)
    requested_profile = _normalized_frame_profile(frame_profile)
    requested_sampling = _normalize_refilter_sampling_mode(sampling_mode)
    requested_scale = _normalize_siglip_decode_scale_w(siglip_ffmpeg_scale_w, default=0)
    for name in names:
        if not (name.startswith("siglip_scene_") and name.endswith(".npz")):
            continue
        fp = os.path.join(cache_dir, name)
        payload = _read_npz_dict(fp)
        if not payload:
            continue
        if not _siglip_scene_feature_payload_matches(
            payload,
            requested_video=requested_video,
            requested_scene_ms=scene_ms_norm,
            requested_model=requested_model,
            requested_adapter=requested_adapter,
            requested_profile=requested_profile,
            requested_sampling=requested_sampling,
            requested_scale=requested_scale,
        ):
            continue
        parsed = _parse_siglip_scene_feature_payload(payload, video_path)
        if parsed is not None:
            return payload, parsed
    return {}, None


def _find_relaxed_siglip_scene_feature_cache(
    video_path: str,
    scene_ms: List[int],
    *,
    siglip_model_id: str,
    siglip_adapter_path: str,
):
    cache_dir = _default_cache_dir()
    try:
        with _CACHE_LOCK:
            names = sorted(os.listdir(cache_dir), reverse=True)
    except Exception:
        return {}, None
    requested_video = os.path.abspath(video_path or "")
    requested_scene_ms = _normalize_scene_ms(scene_ms)
    requested_model = str(siglip_model_id or "").strip()
    requested_adapter = _normalize_adapter_path(siglip_adapter_path)
    best_payload = {}
    best_parsed = None
    best_score = (-1, -1, -1.0)
    for name in names:
        if not (name.startswith("siglip_scene_") and name.endswith(".npz")):
            continue
        fp = os.path.join(cache_dir, name)
        payload = _read_npz_dict(fp)
        if not payload:
            continue
        if not _siglip_scene_feature_payload_relaxed_matches(
            payload,
            requested_video=requested_video,
            requested_scene_ms=requested_scene_ms,
            requested_model=requested_model,
            requested_adapter=requested_adapter,
        ):
            continue
        parsed = _parse_siglip_scene_feature_payload(payload, video_path)
        if parsed is None:
            continue
        score = _siglip_scene_feature_payload_score(payload)
        if score > best_score:
            best_payload = payload
            best_parsed = parsed
            best_score = score
    return best_payload, best_parsed


def _siglip_scene_feature_payload_matches(
    payload: dict,
    *,
    requested_video: str,
    requested_scene_ms: List[int],
    requested_model: str,
    requested_adapter: str,
    requested_profile: str,
    requested_sampling: str,
    requested_scale: int,
) -> bool:
    import numpy as np  # type: ignore

    try:
        payload_video = os.path.abspath(str(np.asarray(payload.get("video_path")).reshape(-1)[0]))
    except Exception:
        payload_video = ""
    payload_mtime_ns, payload_size = _siglip_payload_video_signature(payload)
    if not _video_paths_match(requested_video, payload_video, payload_mtime_ns, payload_size):
        return False
    try:
        payload_scene_ms = _normalize_scene_ms(np.asarray(payload.get("scene_ms"), dtype=np.int64).reshape(-1).tolist())
    except Exception:
        payload_scene_ms = []
    if payload_scene_ms != requested_scene_ms:
        return False
    try:
        payload_model = str(np.asarray(payload.get("siglip_model_id")).reshape(-1)[0]).strip()
    except Exception:
        payload_model = ""
    if payload_model != requested_model:
        return False
    try:
        payload_adapter = _normalize_adapter_path(str(np.asarray(payload.get("siglip_adapter_path")).reshape(-1)[0]))
    except Exception:
        payload_adapter = ""
    if payload_adapter != requested_adapter:
        return False
    try:
        payload_profile = _normalized_frame_profile(str(np.asarray(payload.get("frame_profile")).reshape(-1)[0]))
    except Exception:
        payload_profile = "normal"
    if payload_profile != requested_profile:
        return False
    try:
        payload_sampling = _normalize_refilter_sampling_mode(str(np.asarray(payload.get("sampling_mode")).reshape(-1)[0]))
    except Exception:
        payload_sampling = "start_frame"
    if payload_sampling != requested_sampling:
        return False
    try:
        payload_scale = _normalize_siglip_decode_scale_w(np.asarray(payload.get("siglip_ffmpeg_scale_w")).reshape(-1)[0], default=0)
    except Exception:
        payload_scale = 0
    return payload_scale == requested_scale


def _siglip_scene_feature_payload_relaxed_matches(
    payload: dict,
    *,
    requested_video: str,
    requested_scene_ms: List[int],
    requested_model: str,
    requested_adapter: str,
) -> bool:
    import numpy as np  # type: ignore

    try:
        payload_video = os.path.abspath(str(np.asarray(payload.get("video_path")).reshape(-1)[0]))
    except Exception:
        payload_video = ""
    payload_mtime_ns, payload_size = _siglip_payload_video_signature(payload)
    if not _video_paths_match(requested_video, payload_video, payload_mtime_ns, payload_size):
        return False
    try:
        payload_scene_ms = _normalize_scene_ms(np.asarray(payload.get("scene_ms"), dtype=np.int64).reshape(-1).tolist())
    except Exception:
        payload_scene_ms = []
    if payload_scene_ms != requested_scene_ms:
        return False
    try:
        payload_model = str(np.asarray(payload.get("siglip_model_id")).reshape(-1)[0]).strip()
    except Exception:
        payload_model = ""
    if payload_model != requested_model:
        return False
    try:
        payload_adapter = _normalize_adapter_path(str(np.asarray(payload.get("siglip_adapter_path")).reshape(-1)[0]))
    except Exception:
        payload_adapter = ""
    return payload_adapter == requested_adapter


def _siglip_scene_feature_payload_score(payload: dict) -> tuple[int, int, float]:
    import numpy as np  # type: ignore

    try:
        full_scene_count = int(np.asarray(payload.get("full_scene_count")).reshape(-1)[0])
    except Exception:
        full_scene_count = 0
    try:
        coarse_scene_count = int(np.asarray(payload.get("coarse_scene_count")).reshape(-1)[0])
    except Exception:
        coarse_scene_count = 0
    try:
        saved_at = float(np.asarray(payload.get("saved_at")).reshape(-1)[0])
    except Exception:
        saved_at = 0.0
    return (full_scene_count, coarse_scene_count, saved_at)


def _store_siglip_scene_feature_cache_alias(
    key: str,
    video_path: str,
    parsed: dict,
    payload: dict,
    *,
    siglip_model_id: str,
    siglip_adapter_path: str,
    frame_profile: str,
    sampling_mode: str,
    siglip_ffmpeg_scale_w: int,
) -> None:
    arrays = {
        "scene_ms": parsed.get("scene_ms"),
        "coarse_counts": parsed.get("coarse_counts"),
        "coarse_feats": parsed.get("coarse_feats"),
        "full_counts": parsed.get("full_counts"),
        "full_feats": parsed.get("full_feats"),
    }
    try:
        siglip_two_stage = bool(int(payload.get("siglip_two_stage", [0])[0]))  # type: ignore[index]
    except Exception:
        siglip_two_stage = False
    alias_payload = _siglip_scene_feature_payload(
        video_path,
        arrays,
        siglip_model_id=siglip_model_id,
        siglip_adapter_path=siglip_adapter_path,
        frame_profile=frame_profile,
        sampling_mode=sampling_mode,
        siglip_ffmpeg_scale_w=siglip_ffmpeg_scale_w,
        siglip_two_stage=siglip_two_stage,
    )
    try:
        with _CACHE_LOCK:
            _write_npz_atomic(_siglip_scene_feature_cache_disk_path(key), alias_payload)
    except Exception:
        pass


def _siglip_scene_feature_payload(
    video_path: str,
    arrays,
    *,
    siglip_model_id: str,
    siglip_adapter_path: str,
    frame_profile: str,
    sampling_mode: str,
    siglip_ffmpeg_scale_w: int,
    siglip_two_stage: bool,
):
    import numpy as np  # type: ignore

    return {
        "video_path": np.asarray(os.path.abspath(video_path or "")),
        "video_mtime_ns": np.asarray([_path_signature_fields(video_path)["video_mtime_ns"]], dtype=np.int64),
        "video_size": np.asarray([_path_signature_fields(video_path)["video_size"]], dtype=np.int64),
        "scene_ms": arrays["scene_ms"],
        "coarse_counts": arrays["coarse_counts"],
        "coarse_feats": arrays["coarse_feats"],
        "full_counts": arrays["full_counts"],
        "full_feats": arrays["full_feats"],
        "siglip_model_id": np.asarray(str(siglip_model_id or "").strip()),
        "siglip_adapter_path": np.asarray(_normalize_adapter_path(siglip_adapter_path)),
        "frame_profile": np.asarray(_normalized_frame_profile(frame_profile)),
        "sampling_mode": np.asarray(_normalize_refilter_sampling_mode(sampling_mode)),
        "siglip_ffmpeg_scale_w": np.asarray([_normalize_siglip_decode_scale_w(siglip_ffmpeg_scale_w, default=0)], dtype=np.int32),
        "siglip_two_stage": np.asarray([1 if bool(siglip_two_stage) else 0], dtype=np.int8),
        "scene_count": np.asarray([int(arrays["scene_ms"].size)], dtype=np.int32),
        "coarse_scene_count": np.asarray([int((arrays["coarse_counts"] > 0).sum())], dtype=np.int32),
        "full_scene_count": np.asarray([int((arrays["full_counts"] > 0).sum())], dtype=np.int32),
        "saved_at": np.asarray([float(time.time())], dtype=np.float64),
    }


def _siglip_scene_feature_memory_entry(video_path: str, arrays, payload, **meta):
    return {
        "video_path": os.path.abspath(video_path or ""),
        "video_mtime_ns": _npz_scalar_int(payload.get("video_mtime_ns"), 0),
        "video_size": _npz_scalar_int(payload.get("video_size"), 0),
        "scene_ms": arrays["scene_ms"],
        "coarse_counts": arrays["coarse_counts"],
        "coarse_feats": arrays["coarse_feats"],
        "full_counts": arrays["full_counts"],
        "full_feats": arrays["full_feats"],
        "siglip_model_id": str(meta["siglip_model_id"] or "").strip(),
        "siglip_adapter_path": _normalize_adapter_path(meta["siglip_adapter_path"]),
        "frame_profile": _normalized_frame_profile(meta["frame_profile"]),
        "sampling_mode": _normalize_refilter_sampling_mode(meta["sampling_mode"]),
        "siglip_ffmpeg_scale_w": _normalize_siglip_decode_scale_w(meta["siglip_ffmpeg_scale_w"], default=0),
        "siglip_two_stage": bool(meta["siglip_two_stage"]),
        "saved_at": float(payload["saved_at"][0]),
    }


def siglip_scene_feature_cache_set(
    video_path: str,
    scene_ms: List[int],
    *,
    coarse_counts,
    coarse_feats,
    full_counts,
    full_feats,
    siglip_model_id: str = "",
    siglip_adapter_path: str = "",
    frame_profile: str = "normal",
    sampling_mode: str = "start_frame",
    siglip_ffmpeg_scale_w: int = 0,
    siglip_two_stage: bool = False,
):
    arrays = _siglip_scene_feature_arrays(scene_ms, coarse_counts, coarse_feats, full_counts, full_feats)
    if not _valid_siglip_scene_feature_arrays(arrays):
        return
    key = _siglip_scene_feature_cache_key(
        video_path,
        arrays["scene_ms"].tolist(),
        siglip_model_id=siglip_model_id,
        siglip_adapter_path=siglip_adapter_path,
        frame_profile=frame_profile,
        sampling_mode=sampling_mode,
        siglip_ffmpeg_scale_w=siglip_ffmpeg_scale_w,
    )
    payload = _siglip_scene_feature_payload(
        video_path,
        arrays,
        siglip_model_id=siglip_model_id,
        siglip_adapter_path=siglip_adapter_path,
        frame_profile=frame_profile,
        sampling_mode=sampling_mode,
        siglip_ffmpeg_scale_w=siglip_ffmpeg_scale_w,
        siglip_two_stage=siglip_two_stage,
    )
    with _CACHE_LOCK:
        _SIGLIP_SCENE_FEATURE_CACHE[key] = _siglip_scene_feature_memory_entry(
            video_path,
            arrays,
            payload,
            siglip_model_id=siglip_model_id,
            siglip_adapter_path=siglip_adapter_path,
            frame_profile=frame_profile,
            sampling_mode=sampling_mode,
            siglip_ffmpeg_scale_w=siglip_ffmpeg_scale_w,
            siglip_two_stage=siglip_two_stage,
        )
    try:
        with _CACHE_LOCK:
            _write_npz_atomic(_siglip_scene_feature_cache_disk_path(key), payload)
    except Exception:
        pass


def _refilter_pairs(sim_pairs: List[tuple[int, float]]) -> List[tuple[int, float]]:
    return [(int(ms), float(sim)) for ms, sim in (sim_pairs or [])]


def _find_compatible_refilter_memory_cache(
    video_path: str,
    sample_image_paths: List[str],
    mode: str,
    scene_ms: List[int],
    pose_weights: Optional[dict],
    siglip_model_id: str,
    siglip_adapter_path: str,
    sample_texts: Optional[List[str]],
    agg_mode: str,
    kofn_k: int,
    frame_profile: str,
    sampling_mode: str,
    hybrid_siglip_weight: float,
    siglip_two_stage: bool,
    siglip_stage2_ratio: float,
    siglip_ffmpeg_scale_w: int,
):
    with _CACHE_LOCK:
        values = list(_REFILTER_CACHE.values())
    for cached in values:
        if not isinstance(cached, dict):
            continue
        if not _refilter_payload_matches_request(
            cached,
            video_path,
            sample_image_paths,
            mode,
            scene_ms,
            pose_weights,
            siglip_model_id,
            siglip_adapter_path,
            sample_texts,
            agg_mode,
            kofn_k,
            frame_profile,
            sampling_mode,
            hybrid_siglip_weight,
            siglip_two_stage,
            siglip_stage2_ratio,
            siglip_ffmpeg_scale_w,
        ):
            continue
        return cached
    return None


def _find_compatible_refilter_disk_cache(
    video_path: str,
    sample_image_paths: List[str],
    mode: str,
    scene_ms: List[int],
    pose_weights: Optional[dict],
    siglip_model_id: str,
    siglip_adapter_path: str,
    sample_texts: Optional[List[str]],
    agg_mode: str,
    kofn_k: int,
    frame_profile: str,
    sampling_mode: str,
    hybrid_siglip_weight: float,
    siglip_two_stage: bool,
    siglip_stage2_ratio: float,
    siglip_ffmpeg_scale_w: int,
):
    cache_dir = _default_cache_dir()
    try:
        with _CACHE_LOCK:
            names = list(os.listdir(cache_dir))
    except Exception:
        return None
    best_payload = None
    best_saved_at = -1.0
    for name in names:
        if not (name.startswith("refilter_") and name.endswith(".json")):
            continue
        payload = _read_json_dict(os.path.join(cache_dir, name))
        if not payload:
            continue
        if not _refilter_payload_matches_request(
            payload,
            video_path,
            sample_image_paths,
            mode,
            scene_ms,
            pose_weights,
            siglip_model_id,
            siglip_adapter_path,
            sample_texts,
            agg_mode,
            kofn_k,
            frame_profile,
            sampling_mode,
            hybrid_siglip_weight,
            siglip_two_stage,
            siglip_stage2_ratio,
            siglip_ffmpeg_scale_w,
        ):
            continue
        try:
            saved_at = float(payload.get("saved_at", 0.0) or 0.0)
        except Exception:
            saved_at = 0.0
        if saved_at >= best_saved_at:
            best_payload = payload
            best_saved_at = saved_at
    return best_payload


def refilter_cache_get(
    video_path: str,
    sample_image_paths: List[str],
    mode: str,
    scene_ms: List[int],
    pose_weights: Optional[dict] = None,
    siglip_model_id: str = "",
    siglip_adapter_path: str = "",
    sample_texts: Optional[List[str]] = None,
    agg_mode: str = "max",
    kofn_k: int = 1,
    frame_profile: str = "normal",
    sampling_mode: str = "start_frame",
    hybrid_siglip_weight: float = 0.55,
    siglip_two_stage: bool = False,
    siglip_stage2_ratio: float = 0.35,
    siglip_decode_hwaccel: bool = True,
    siglip_ffmpeg_scale_w: int = 0,
    source_mode: str = "scene",
    direct_interval_sec: int = 0,
):
    key = _refilter_cache_key(
        video_path, sample_image_paths, mode, scene_ms, pose_weights, siglip_model_id, siglip_adapter_path,
        sample_texts, agg_mode, kofn_k, frame_profile, sampling_mode, hybrid_siglip_weight,
        siglip_two_stage, siglip_stage2_ratio, siglip_decode_hwaccel, siglip_ffmpeg_scale_w,
    )
    with _CACHE_LOCK:
        cached = _REFILTER_CACHE.get(key)
        if isinstance(cached, dict):
            pairs = cached.get("pairs") or []
            return [(int(ms), float(sim)) for ms, sim in pairs]
    payload = _read_json_dict(_refilter_cache_disk_path(key))
    try:
        pairs = [(int(ms), float(sim)) for ms, sim in (payload.get("pairs") or [])]
    except Exception:
        return None
    if not payload:
        payload = _find_compatible_refilter_memory_cache(
            video_path,
            sample_image_paths,
            mode,
            scene_ms,
            pose_weights,
            siglip_model_id,
            siglip_adapter_path,
            sample_texts,
            agg_mode,
            kofn_k,
            frame_profile,
            sampling_mode,
            hybrid_siglip_weight,
            siglip_two_stage,
            siglip_stage2_ratio,
            siglip_ffmpeg_scale_w,
        ) or _find_compatible_refilter_disk_cache(
            video_path,
            sample_image_paths,
            mode,
            scene_ms,
            pose_weights,
            siglip_model_id,
            siglip_adapter_path,
            sample_texts,
            agg_mode,
            kofn_k,
            frame_profile,
            sampling_mode,
            hybrid_siglip_weight,
            siglip_two_stage,
            siglip_stage2_ratio,
            siglip_ffmpeg_scale_w,
        )
        if not payload:
            return None
        try:
            pairs = [(int(ms), float(sim)) for ms, sim in (payload.get("pairs") or [])]
        except Exception:
            return None
    cached_payload = dict(payload)
    cached_payload["video_path"] = os.path.abspath(video_path or "")
    cached_payload.update(_path_signature_fields(video_path))
    with _CACHE_LOCK:
        _REFILTER_CACHE[key] = cached_payload
    return pairs


def _refilter_cache_payload(
    video_path: str,
    sample_image_paths: List[str],
    sample_texts: List[str],
    scene_ms: List[int],
    mode: str,
    pairs: List[tuple[int, float]],
    *,
    pose_weights: Optional[dict],
    siglip_model_id: str,
    siglip_adapter_path: str,
    agg_mode: str,
    kofn_k: int,
    frame_profile: str,
    sampling_mode: str,
    hybrid_siglip_weight: float,
    siglip_two_stage: bool,
    siglip_stage2_ratio: float,
    siglip_decode_hwaccel: bool,
    siglip_ffmpeg_scale_w: int,
    source_mode: str,
    direct_interval_sec: int,
    sim_threshold: Optional[float],
) -> dict:
    mode_norm = _normalize_refilter_mode(mode)
    payload = {
        "video_path": os.path.abspath(video_path or ""),
        "sample_image_paths": sample_image_paths,
        "sample_texts": sample_texts,
        "scene_ms": [int(ms) for ms in (scene_ms or [])],
        "mode": mode_norm,
        "pose_weights": _normalize_pose_weights(pose_weights) if mode_norm in ("pose_comp", "hybrid") else None,
        "siglip_model_id": str(siglip_model_id or "").strip() if mode_norm in ("siglip2", "hybrid") else None,
        "siglip_adapter_path": _normalize_adapter_path(siglip_adapter_path) if mode_norm in ("siglip2", "hybrid") else None,
        "agg_mode": _normalize_refilter_agg_mode(agg_mode),
        "kofn_k": max(1, int(kofn_k)),
        "frame_profile": _normalized_frame_profile(frame_profile),
        "sampling_mode": _normalize_refilter_sampling_mode(sampling_mode),
        "hybrid_siglip_weight": max(0.0, min(1.0, float(hybrid_siglip_weight))),
        "siglip_two_stage": bool(siglip_two_stage),
        "siglip_stage2_ratio": max(0.05, min(1.0, float(siglip_stage2_ratio))),
        "siglip_decode_hwaccel": bool(siglip_decode_hwaccel),
        "siglip_ffmpeg_scale_w": _normalize_siglip_decode_scale_w(siglip_ffmpeg_scale_w, default=0),
        "source_mode": "scene" if str(source_mode or "").strip().lower() == "scene" else "direct",
        "direct_interval_sec": max(0, int(direct_interval_sec)),
        "sim_threshold": max(0.0, min(1.0, float(sim_threshold))) if isinstance(sim_threshold, (int, float)) else None,
        "pairs": pairs,
        "algo": REFILTER_ALGO_VERSION,
        "saved_at": float(time.time()),
    }
    payload.update(_path_signature_fields(video_path))
    return payload


def refilter_cache_set(
    video_path: str,
    sample_image_paths: List[str],
    mode: str,
    scene_ms: List[int],
    sim_pairs: List[tuple[int, float]],
    pose_weights: Optional[dict] = None,
    siglip_model_id: str = "",
    siglip_adapter_path: str = "",
    sample_texts: Optional[List[str]] = None,
    agg_mode: str = "max",
    kofn_k: int = 1,
    frame_profile: str = "normal",
    sampling_mode: str = "start_frame",
    hybrid_siglip_weight: float = 0.55,
    siglip_two_stage: bool = False,
    siglip_stage2_ratio: float = 0.35,
    siglip_decode_hwaccel: bool = True,
    siglip_ffmpeg_scale_w: int = 0,
    source_mode: str = "scene",
    direct_interval_sec: int = 0,
    sim_threshold: Optional[float] = None,
):
    key = _refilter_cache_key(
        video_path, sample_image_paths, mode, scene_ms, pose_weights, siglip_model_id, siglip_adapter_path,
        sample_texts, agg_mode, kofn_k, frame_profile, sampling_mode, hybrid_siglip_weight,
        siglip_two_stage, siglip_stage2_ratio, siglip_decode_hwaccel, siglip_ffmpeg_scale_w,
    )
    pairs = _refilter_pairs(sim_pairs)
    payload = _refilter_cache_payload(
        video_path, _normalize_sample_paths(sample_image_paths), _normalize_sample_texts(sample_texts or []),
        scene_ms, mode, pairs, pose_weights=pose_weights, siglip_model_id=siglip_model_id,
        siglip_adapter_path=siglip_adapter_path, agg_mode=agg_mode, kofn_k=kofn_k,
        frame_profile=frame_profile, sampling_mode=sampling_mode, hybrid_siglip_weight=hybrid_siglip_weight,
        siglip_two_stage=siglip_two_stage, siglip_stage2_ratio=siglip_stage2_ratio,
        siglip_decode_hwaccel=siglip_decode_hwaccel, siglip_ffmpeg_scale_w=siglip_ffmpeg_scale_w,
        source_mode=source_mode, direct_interval_sec=direct_interval_sec, sim_threshold=sim_threshold,
    )
    with _CACHE_LOCK:
        _REFILTER_CACHE[key] = dict(payload)
    try:
        with _CACHE_LOCK:
            _write_json_atomic(_refilter_cache_disk_path(key), payload)
    except Exception:
        pass


def _clear_refilter_memory_for_video(path_abs: str):
    with _CACHE_LOCK:
        for key in list(_REFILTER_CACHE.keys()):
            value = _REFILTER_CACHE.get(key) or {}
            stored_mtime_ns, stored_size = _payload_video_signature(value if isinstance(value, dict) else {})
            if _video_paths_match(path_abs, value.get("video_path", ""), stored_mtime_ns, stored_size):
                _REFILTER_CACHE.pop(key, None)
        for key in list(_SIGLIP_SCENE_FEATURE_CACHE.keys()):
            value = _SIGLIP_SCENE_FEATURE_CACHE.get(key) or {}
            if _video_paths_match(path_abs, value.get("video_path", ""), int(value.get("video_mtime_ns", 0) or 0), int(value.get("video_size", 0) or 0)):
                _SIGLIP_SCENE_FEATURE_CACHE.pop(key, None)


def _remove_refilter_disk_file(file_path: str, path_abs: str, is_siglip: bool):
    try:
        if is_siglip:
            data = _read_npz_dict(file_path)
            arr = data.get("video_path")
            candidate = str(arr.reshape(-1)[0]) if arr is not None else ""
            cand_mtime_ns, cand_size = _siglip_payload_video_signature(data)
        else:
            data = _read_json_dict(file_path)
            candidate = str(data.get("video_path", ""))
            cand_mtime_ns, cand_size = _payload_video_signature(data)
        if _video_paths_match(path_abs, candidate, cand_mtime_ns, cand_size):
            with _CACHE_LOCK:
                os.remove(file_path)
    except Exception:
        pass


def _clear_refilter_disk_for_video(path_abs: str):
    cache_dir = _default_cache_dir()
    try:
        with _CACHE_LOCK:
            names = list(os.listdir(cache_dir))
    except Exception:
        return
    for name in names:
        file_path = os.path.join(cache_dir, name)
        if name.startswith("refilter_") and name.endswith(".json"):
            _remove_refilter_disk_file(file_path, path_abs, False)
        elif name.startswith("siglip_scene_") and name.endswith(".npz"):
            _remove_refilter_disk_file(file_path, path_abs, True)


def refilter_cache_clear_for_video(video_path: str):
    path_abs = os.path.abspath(video_path or "")
    _clear_refilter_memory_for_video(path_abs)
    _clear_refilter_disk_for_video(path_abs)


def refilter_cache_clear_all():
    with _CACHE_LOCK:
        _REFILTER_CACHE.clear()
        _SIGLIP_SCENE_FEATURE_CACHE.clear()
    cache_dir = _default_cache_dir()
    try:
        with _CACHE_LOCK:
            names = list(os.listdir(cache_dir))
    except Exception:
        return
    for name in names:
        if (
            name.startswith("refilter_") and name.endswith(".json")
        ) or (
            name.startswith("siglip_scene_") and name.endswith(".npz")
        ):
            try:
                with _CACHE_LOCK:
                    os.remove(os.path.join(cache_dir, name))
            except Exception:
                pass


__all__ = [
    "_refilter_cache_key",
    "_refilter_cache_disk_path",
    "_siglip_scene_feature_cache_key",
    "_siglip_scene_feature_cache_disk_path",
    "siglip_scene_feature_cache_get",
    "siglip_scene_feature_cache_set",
    "refilter_cache_get",
    "refilter_cache_set",
    "refilter_cache_clear_for_video",
    "refilter_cache_clear_all",
]
