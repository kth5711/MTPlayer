from __future__ import annotations

from typing import List, Optional
import os

from .cache import (
    _CACHE_LOCK,
    _REFILTER_CACHE,
    _SCENE_CACHE,
    _SIGLIP_SCENE_FEATURE_CACHE,
    _cache_saved_time_text,
    _default_cache_dir,
    _normalize_refilter_agg_mode,
    _normalize_refilter_mode,
    _normalize_sample_paths,
    _normalize_sample_texts,
    _payload_video_signature,
    _read_json_dict,
    _read_siglip_scene_feature_meta,
    _refilter_sampling_label,
    _scene_key,
    _siglip_decode_scale_label,
    _video_paths_match,
)


def _cache_dir_names(cache_dir: str) -> List[str]:
    try:
        with _CACHE_LOCK:
            return sorted(os.listdir(cache_dir))
    except Exception:
        return []


def _history_saved_at(file_path: str, saved_at: float) -> float:
    ts = float(saved_at or 0.0)
    if ts > 0.0:
        return ts
    try:
        return float(os.path.getmtime(file_path))
    except Exception:
        return 0.0


def _siglip_history_entry(file_path: str, file_name: str, current_path: str, current_only: bool) -> Optional[dict]:
    meta = _read_siglip_scene_feature_meta(file_path)
    if not meta:
        return None
    video_path = os.path.abspath(str(meta.get("video_path") or ""))
    video_mtime_ns, video_size = _payload_video_signature(meta)
    if current_only and current_path and (not _video_paths_match(current_path, video_path, video_mtime_ns, video_size)):
        return None
    saved_at = _history_saved_at(file_path, float(meta.get("saved_at", 0.0) or 0.0))
    model_id = str(meta.get("siglip_model_id") or "siglip2").strip() or "siglip2"
    sampling = _refilter_sampling_label(str(meta.get("sampling_mode") or "start_frame"))
    frame_profile = str(meta.get("frame_profile") or "normal").strip().lower() or "normal"
    coarse_scene_count = int(meta.get("coarse_scene_count", 0) or 0)
    full_scene_count = int(meta.get("full_scene_count", 0) or 0)
    scene_count = int(meta.get("scene_count", max(coarse_scene_count, full_scene_count)) or 0)
    scale_w = int(meta.get("siglip_ffmpeg_scale_w", 0) or 0)
    detail = (
        f"{model_id}/{sampling}/{frame_profile} | "
        f"coarse={coarse_scene_count}, full={full_scene_count}, "
        f"scale={_siglip_decode_scale_label(scale_w, compact=True)}"
    )
    cache_key = file_name[len("siglip_scene_"):-len(".npz")]
    return {
        "type": "siglip_feature",
        "file_path": file_path,
        "file_name": file_name,
        "cache_key": cache_key,
        "video_path": video_path,
        "video_name": os.path.basename(video_path) if video_path else "(알 수 없음)",
        "count": scene_count,
        "detail": detail,
        "saved_at": saved_at,
        "saved_text": _cache_saved_time_text(saved_at),
        "video_mtime_ns": video_mtime_ns,
        "video_size": video_size,
        "coarse_scene_count": coarse_scene_count,
        "full_scene_count": full_scene_count,
    }


def _history_json_entry(file_path: str, file_name: str, current_path: str, current_only: bool) -> Optional[dict]:
    payload = _read_json_dict(file_path)
    if not payload:
        return None
    is_refilter = bool(file_name.startswith("refilter_"))
    video_path = os.path.abspath(str(payload.get("video_path") or payload.get("path") or ""))
    video_mtime_ns, video_size = _payload_video_signature(payload)
    if current_only and current_path and (not _video_paths_match(current_path, video_path, video_mtime_ns, video_size)):
        return None
    saved_at = _history_saved_at(file_path, float(payload.get("saved_at", 0.0) or 0.0))
    if is_refilter:
        return _history_refilter_entry(file_path, file_name, payload, video_path, saved_at)
    return _history_scene_entry(file_path, file_name, payload, video_path, saved_at, current_path, current_only)


def _history_refilter_entry(file_path: str, file_name: str, payload: dict, video_path: str, saved_at: float) -> dict:
    pairs = payload.get("pairs") or []
    mode = _normalize_refilter_mode(str(payload.get("mode") or "siglip2"))
    agg = _normalize_refilter_agg_mode(str(payload.get("agg_mode") or "max"))
    sampling = _refilter_sampling_label(str(payload.get("sampling_mode") or "start_frame"))
    source_mode = str(payload.get("source_mode") or "scene").strip().lower()
    source_label = "scene" if source_mode == "scene" else "direct"
    img_n = len(_normalize_sample_paths(payload.get("sample_image_paths") or []))
    txt_n = len(_normalize_sample_texts(payload.get("sample_texts") or []))
    detail = f"{mode}/{agg}/{sampling}/{source_label} | img={img_n}, text={txt_n}"
    cache_key = file_name[len("refilter_"):-len(".json")]
    return {
        "type": "refilter",
        "file_path": file_path,
        "file_name": file_name,
        "cache_key": cache_key,
        "video_path": video_path,
        "video_name": os.path.basename(video_path) if video_path else "(알 수 없음)",
        "count": len(pairs),
        "detail": detail,
        "saved_at": saved_at,
        "saved_text": _cache_saved_time_text(saved_at),
        "video_mtime_ns": int(payload.get("video_mtime_ns", 0) or 0),
        "video_size": int(payload.get("video_size", 0) or 0),
    }


def _history_scene_entry(
    file_path: str,
    file_name: str,
    payload: dict,
    video_path: str,
    saved_at: float,
    current_path: str,
    current_only: bool,
) -> Optional[dict]:
    pts = payload.get("pts") or []
    top = payload.get("top") or payload.get("top10") or []
    if not isinstance(pts, list):
        return None
    if (not video_path) and current_only and current_path:
        return None
    use_ff = bool(payload.get("use_ff", True))
    thr_v = payload.get("thr")
    dw_v = payload.get("dw")
    fps_v = payload.get("fps")
    ff_hw = bool(payload.get("ff_hwaccel", False))
    thr_s = f"{float(thr_v):.2f}" if isinstance(thr_v, (int, float)) else "?"
    dw_s = str(int(dw_v)) if isinstance(dw_v, (int, float)) else "?"
    fps_s = str(int(fps_v)) if isinstance(fps_v, (int, float)) else "?"
    return {
        "type": "scene",
        "file_path": file_path,
        "file_name": file_name,
        "cache_key": file_name[:-len(".json")],
        "video_path": video_path,
        "video_name": os.path.basename(video_path) if video_path else "(알 수 없음)",
        "count": len(pts),
        "detail": f"thr={thr_s}, dw={dw_s}, fps={fps_s}, decode={'gpu' if ff_hw else 'cpu'}",
        "saved_at": saved_at,
        "saved_text": _cache_saved_time_text(saved_at),
        "video_mtime_ns": int(payload.get("video_mtime_ns", 0) or 0),
        "video_size": int(payload.get("video_size", 0) or 0),
        "top_count": len(top) if isinstance(top, list) else 0,
        "use_ff": use_ff,
        "thr": thr_v,
        "dw": dw_v,
        "fps": fps_v,
        "ff_hwaccel": ff_hw,
    }


def cache_history_entries(current_video_path: str = "", current_only: bool = True) -> List[dict]:
    out: List[dict] = []
    cache_dir = _default_cache_dir()
    current_path = os.path.abspath(current_video_path or "")
    for file_name in _cache_dir_names(cache_dir):
        file_path = os.path.join(cache_dir, file_name)
        if not os.path.isfile(file_path):
            continue
        if file_name.startswith("siglip_scene_") and file_name.endswith(".npz"):
            entry = _siglip_history_entry(file_path, file_name, current_path, current_only)
        elif file_name.endswith(".json"):
            entry = _history_json_entry(file_path, file_name, current_path, current_only)
        else:
            entry = None
        if entry is not None:
            out.append(entry)
    out.sort(key=lambda item: float(item.get("saved_at", 0.0)), reverse=True)
    return out


def _remove_scene_history_entry(entry: dict):
    path = os.path.abspath(str(entry.get("video_path") or ""))
    try:
        use_ff = bool(entry.get("use_ff", True))
        thr = float(entry.get("thr"))
        dw = int(entry.get("dw"))
        fps = int(entry.get("fps"))
        ff_hw = bool(entry.get("ff_hwaccel", False))
    except Exception:
        return
    with _CACHE_LOCK:
        _SCENE_CACHE.pop(_scene_key(path, use_ff, thr, dw, fps, ff_hw), None)


def _remove_refilter_history_entry(entry: dict):
    key = str(entry.get("cache_key") or "").strip()
    if not key:
        return
    with _CACHE_LOCK:
        _REFILTER_CACHE.pop(key, None)


def _remove_siglip_feature_history_entry(entry: dict):
    key = str(entry.get("cache_key") or "").strip()
    if not key:
        return
    with _CACHE_LOCK:
        _SIGLIP_SCENE_FEATURE_CACHE.pop(key, None)


def _remove_history_memory_entry(entry: dict):
    entry_type = str(entry.get("type") or "")
    if entry_type == "scene":
        _remove_scene_history_entry(entry)
    elif entry_type == "refilter":
        _remove_refilter_history_entry(entry)
    elif entry_type == "siglip_feature":
        _remove_siglip_feature_history_entry(entry)


def _remove_history_file(file_path: str):
    if not file_path or not os.path.exists(file_path):
        return
    with _CACHE_LOCK:
        os.remove(file_path)


def remove_cache_history_entries(entries: List[dict]) -> tuple[int, int]:
    removed = 0
    failed = 0
    for entry in (entries or []):
        try:
            _remove_history_memory_entry(entry)
            _remove_history_file(str(entry.get("file_path") or ""))
            removed += 1
        except Exception:
            failed += 1
    return removed, failed


__all__ = ["cache_history_entries", "remove_cache_history_entries"]
