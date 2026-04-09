from __future__ import annotations

from typing import Any, Dict, List, Optional
import hashlib
import json
import os
import re
import tempfile
import time
import threading

from .similarity import (
    REFILTER_FRAME_PROFILES,
    _normalize_adapter_path,
    _normalize_pose_weights,
    _normalize_refilter_agg_mode,
    _normalize_refilter_mode,
    _normalize_refilter_sampling_mode as _normalize_refilter_sampling_mode_base,
    _siglip_decode_scale_label,
    _normalize_siglip_decode_scale_w,
    _pose_weight_signature,
    _siglip_decode_scale_signature,
)


SCENE_CACHE_ALGO_VERSION = "dc3"
REFILTER_ALGO_VERSION = "rc16"
SIGLIP_SCENE_FEATURE_CACHE_ALGO_VERSION = "sfc1"

_SCENE_CACHE: dict[tuple, dict] = {}
_REFILTER_CACHE: dict[str, dict] = {}
_SIGLIP_SCENE_FEATURE_CACHE: dict[str, dict] = {}
_CACHE_LOCK = threading.RLock()


def _normalize_refilter_sampling_mode(mode: str) -> str:
    m = str(mode or "").strip().lower()
    if m == "adaptive_window":
        return "scene_window"
    return _normalize_refilter_sampling_mode_base(m)


def _refilter_sampling_label(mode: str) -> str:
    m = _normalize_refilter_sampling_mode(mode)
    if m == "scene_window":
        return "구간 샘플링"
    if m == "start_frame":
        return "패스트(씬시작 1샷)"
    return m or "-"


def _default_cache_dir() -> str:
    try:
        import appdirs  # type: ignore

        d = appdirs.user_cache_dir("player_app", "local")
    except Exception:
        d = os.path.join(os.path.expanduser("~"), ".player_app_cache")
    os.makedirs(d, exist_ok=True)
    return d


def _read_json_dict(path: str) -> dict:
    try:
        with _CACHE_LOCK:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _write_json_atomic(path: str, payload: dict) -> None:
    target = os.path.abspath(str(path or "").strip())
    if not target:
        raise RuntimeError("cache path is empty")
    cache_dir = os.path.dirname(target) or "."
    os.makedirs(cache_dir, exist_ok=True)
    tmp_path = ""
    fd = -1
    try:
        fd, tmp_path = tempfile.mkstemp(prefix="cache_", suffix=".tmp", dir=cache_dir)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = -1
            json.dump(payload, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target)
        tmp_path = ""
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except Exception:
                pass
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _read_npz_dict(path: str) -> dict:
    try:
        import numpy as np  # type: ignore
    except Exception:
        return {}
    try:
        with _CACHE_LOCK:
            with np.load(path, allow_pickle=False) as data:
                return {str(k): data[k] for k in list(getattr(data, "files", []) or [])}
    except Exception:
        return {}


def _write_npz_atomic(path: str, payload: Dict[str, Any]) -> None:
    try:
        import numpy as np  # type: ignore
    except Exception as e:
        raise RuntimeError("numpy is required for SigLIP feature cache") from e

    target = os.path.abspath(str(path or "").strip())
    if not target:
        raise RuntimeError("cache path is empty")
    cache_dir = os.path.dirname(target) or "."
    os.makedirs(cache_dir, exist_ok=True)
    tmp_path = ""
    fd = -1
    try:
        fd, tmp_path = tempfile.mkstemp(prefix="cache_", suffix=".npz.tmp", dir=cache_dir)
        with os.fdopen(fd, "wb") as f:
            fd = -1
            np.savez_compressed(f, **payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target)
        tmp_path = ""
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except Exception:
                pass
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _npz_scalar_text(value: Any, default: str = "") -> str:
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None  # type: ignore
    try:
        if value is None:
            return str(default or "")
        if np is not None and isinstance(value, np.ndarray):
            flat = value.reshape(-1)
            if int(flat.size) <= 0:
                return str(default or "")
            return str(flat[0])
        return str(value)
    except Exception:
        return str(default or "")


def _npz_scalar_int(value: Any, default: int = 0) -> int:
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None  # type: ignore
    try:
        if value is None:
            return int(default)
        if np is not None and isinstance(value, np.ndarray):
            flat = value.reshape(-1)
            if int(flat.size) <= 0:
                return int(default)
            return int(flat[0])
        return int(value)
    except Exception:
        return int(default)


def _npz_scalar_float(value: Any, default: float = 0.0) -> float:
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None  # type: ignore
    try:
        if value is None:
            return float(default)
        if np is not None and isinstance(value, np.ndarray):
            flat = value.reshape(-1)
            if int(flat.size) <= 0:
                return float(default)
            return float(flat[0])
        return float(value)
    except Exception:
        return float(default)


def _read_siglip_scene_feature_meta(path: str) -> dict:
    try:
        import numpy as np  # type: ignore
    except Exception:
        return {}
    try:
        with _CACHE_LOCK:
            with np.load(path, allow_pickle=False) as data:
                files = set(getattr(data, "files", []) or [])
                video_path = os.path.abspath(_npz_scalar_text(data["video_path"], "")) if "video_path" in files else ""
                video_mtime_ns = _npz_scalar_int(data["video_mtime_ns"], 0) if "video_mtime_ns" in files else 0
                video_size = _npz_scalar_int(data["video_size"], 0) if "video_size" in files else 0
                saved_at = _npz_scalar_float(data["saved_at"], 0.0) if "saved_at" in files else 0.0
                scene_count = (
                    _npz_scalar_int(data["scene_count"], 0)
                    if "scene_count" in files
                    else int(np.asarray(data["scene_ms"], dtype=np.int64).reshape(-1).size) if "scene_ms" in files else 0
                )
                coarse_scene_count = (
                    _npz_scalar_int(data["coarse_scene_count"], 0)
                    if "coarse_scene_count" in files
                    else int(np.count_nonzero(np.asarray(data["coarse_counts"], dtype=np.int32).reshape(-1))) if "coarse_counts" in files else 0
                )
                full_scene_count = (
                    _npz_scalar_int(data["full_scene_count"], 0)
                    if "full_scene_count" in files
                    else int(np.count_nonzero(np.asarray(data["full_counts"], dtype=np.int32).reshape(-1))) if "full_counts" in files else 0
                )
                return {
                    "video_path": video_path,
                    "video_mtime_ns": int(video_mtime_ns),
                    "video_size": int(video_size),
                    "saved_at": float(saved_at),
                    "siglip_model_id": _npz_scalar_text(data["siglip_model_id"], "") if "siglip_model_id" in files else "",
                    "siglip_adapter_path": _npz_scalar_text(data["siglip_adapter_path"], "") if "siglip_adapter_path" in files else "",
                    "frame_profile": _npz_scalar_text(data["frame_profile"], "normal") if "frame_profile" in files else "normal",
                    "sampling_mode": _npz_scalar_text(data["sampling_mode"], "start_frame") if "sampling_mode" in files else "start_frame",
                    "siglip_ffmpeg_scale_w": _npz_scalar_int(data["siglip_ffmpeg_scale_w"], 0) if "siglip_ffmpeg_scale_w" in files else 0,
                    "siglip_two_stage": bool(_npz_scalar_int(data["siglip_two_stage"], 0)) if "siglip_two_stage" in files else False,
                    "scene_count": int(scene_count),
                    "coarse_scene_count": int(coarse_scene_count),
                    "full_scene_count": int(full_scene_count),
                }
    except Exception:
        return {}


def _cache_saved_time_text(ts: float) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts)))
    except Exception:
        return "-"


def _norm_path(path: str) -> str:
    try:
        return os.path.abspath(str(path or "").strip())
    except Exception:
        return ""


def _norm_path_key(path: str) -> str:
    p = _norm_path(path)
    if not p:
        return ""
    try:
        return os.path.normcase(os.path.normpath(p))
    except Exception:
        return p


def _path_stat_signature(path: str) -> tuple[int, int]:
    p = _norm_path(path)
    if not p:
        return (0, 0)
    try:
        st = os.stat(p)
        return (int(st.st_mtime_ns), int(st.st_size))
    except Exception:
        return (0, 0)


def _path_signature_fields(path: str) -> dict[str, int]:
    mtime_ns, size = _path_stat_signature(path)
    return {
        "video_mtime_ns": int(mtime_ns),
        "video_size": int(size),
    }


def _payload_video_signature(payload: dict) -> tuple[int, int]:
    try:
        mtime_ns = int(payload.get("video_mtime_ns", 0) or 0)
    except Exception:
        mtime_ns = 0
    try:
        size = int(payload.get("video_size", 0) or 0)
    except Exception:
        size = 0
    return (mtime_ns, size)


def _video_paths_match(requested_path: str, stored_path: str = "", stored_mtime_ns: int = 0, stored_size: int = 0) -> bool:
    req_abs = _norm_path(requested_path)
    stored_abs = _norm_path(stored_path)
    if req_abs and stored_abs and _norm_path_key(req_abs) == _norm_path_key(stored_abs):
        return True
    req_sig = _path_stat_signature(req_abs)
    if req_sig == (0, 0):
        return False
    try:
        stored_sig = (int(stored_mtime_ns or 0), int(stored_size or 0))
    except Exception:
        stored_sig = (0, 0)
    if stored_sig != (0, 0):
        return req_sig == stored_sig
    if stored_abs:
        return req_sig == _path_stat_signature(stored_abs)
    return False


def resolve_cached_video_path(requested_path: str, stored_path: str = "", stored_mtime_ns: int = 0, stored_size: int = 0) -> str:
    req_abs = _norm_path(requested_path)
    stored_abs = _norm_path(stored_path)
    if req_abs and _video_paths_match(req_abs, stored_abs, stored_mtime_ns, stored_size):
        return req_abs
    return stored_abs or req_abs


def _normalize_sample_paths(sample_image_paths: List[str]) -> List[str]:
    out = []
    seen = set()
    for p in (sample_image_paths or []):
        pp = os.path.abspath(str(p or "").strip())
        if not pp or pp in seen:
            continue
        seen.add(pp)
        out.append(pp)
    return sorted(out)


def _normalize_sample_texts(sample_texts: List[str]) -> List[str]:
    out = []
    seen = set()
    for raw in (sample_texts or []):
        for part in re.split(r"[\r\n;]+", str(raw or "")):
            txt = re.sub(r"\s+", " ", part).strip()
            if not txt or txt in seen:
                continue
            seen.add(txt)
            out.append(txt)
    return sorted(out)


def _file_sig_for_cache(path: str) -> tuple:
    p = _norm_path(path)
    mtime_ns, size = _path_stat_signature(p)
    return p, mtime_ns, size


def _sample_sigs_for_cache(sample_image_paths: List[str]) -> tuple:
    return tuple(_file_sig_for_cache(p) for p in _normalize_sample_paths(sample_image_paths))


def _sample_text_sigs_for_cache(sample_texts: List[str]) -> tuple:
    return tuple(_normalize_sample_texts(sample_texts))


def _scene_ms_digest(scene_ms: List[int]) -> str:
    data = ",".join(str(int(x)) for x in (scene_ms or []))
    return hashlib.md5(data.encode("utf-8")).hexdigest()


def _normalize_scene_ms(scene_ms: List[int]) -> List[int]:
    if scene_ms is None:
        items = []
    else:
        try:
            items = scene_ms.tolist() if hasattr(scene_ms, "tolist") else list(scene_ms)
        except Exception:
            items = [scene_ms]
    out = []
    seen = set()
    for value in items:
        try:
            ms = int(value)
        except Exception:
            continue
        if ms < 0 or ms in seen:
            continue
        seen.add(ms)
        out.append(ms)
    return sorted(out)


def _cache_key(path, use_ff, thr, dw, fps, ff_hwaccel=False):
    p = os.path.abspath(path or "")
    try:
        st = os.stat(p)
        sig = (
            f"{SCENE_CACHE_ALGO_VERSION}|{p}|{st.st_mtime_ns}|{st.st_size}|"
            f"{use_ff}|{float(thr):.3f}|{int(dw)}|{int(fps)}|{int(bool(ff_hwaccel))}"
        )
    except Exception:
        sig = (
            f"{SCENE_CACHE_ALGO_VERSION}|{p}|0|0|{use_ff}|{float(thr):.3f}|"
            f"{int(dw)}|{int(fps)}|{int(bool(ff_hwaccel))}"
        )
    return hashlib.md5(sig.encode("utf-8")).hexdigest()


def _cache_key_candidates(path, use_ff, thr, dw, fps, ff_hwaccel=False) -> List[str]:
    keys: List[str] = []

    def _add(key: str):
        if key and key not in keys:
            keys.append(key)

    _add(_cache_key(path, use_ff, thr, dw, fps, ff_hwaccel))
    if bool(use_ff):
        _add(_cache_key(path, use_ff, thr, dw, fps, (not bool(ff_hwaccel))))
    return keys


def _disk_cache_path(path, use_ff, thr, dw, fps, ff_hwaccel=False):
    return os.path.join(_default_cache_dir(), _cache_key(path, use_ff, thr, dw, fps, ff_hwaccel) + ".json")


def store_to_disk(path, use_ff, thr, dw, fps, pts, top, ff_hwaccel=False):
    try:
        payload = {
            "video_path": os.path.abspath(path or ""),
            "use_ff": bool(use_ff),
            "thr": float(thr),
            "dw": int(dw),
            "fps": int(fps),
            "ff_hwaccel": bool(ff_hwaccel),
            "pts": list(pts or []),
            "top": list(top or []),
            "algo": SCENE_CACHE_ALGO_VERSION,
            "saved_at": float(time.time()),
        }
        payload.update(_path_signature_fields(path))
        with _CACHE_LOCK:
            _write_json_atomic(_disk_cache_path(path, use_ff, thr, dw, fps, ff_hwaccel), payload)
    except Exception:
        pass


def _scene_payload_matches_request(payload: dict, path: str, use_ff: bool, thr: float, dw: int, fps: int, ff_hwaccel: bool = False) -> bool:
    try:
        payload_thr = round(float(payload.get("thr")), 3)
        payload_dw = int(payload.get("dw"))
        payload_fps = int(payload.get("fps"))
    except Exception:
        return False
    allowed_hw = {int(bool(ff_hwaccel))}
    if bool(use_ff):
        allowed_hw.add(int(not bool(ff_hwaccel)))
    payload_hw = int(bool(payload.get("ff_hwaccel", False)))
    payload_use_ff = bool(payload.get("use_ff", True))
    stored_path = str(payload.get("video_path") or payload.get("path") or "")
    stored_mtime_ns, stored_size = _payload_video_signature(payload)
    return (
        payload_use_ff == bool(use_ff)
        and payload_thr == round(float(thr), 3)
        and payload_dw == int(dw)
        and payload_fps == int(fps)
        and payload_hw in allowed_hw
        and _video_paths_match(path, stored_path, stored_mtime_ns, stored_size)
    )


def _load_compatible_scene_payload(path: str, use_ff: bool, thr: float, dw: int, fps: int, ff_hwaccel: bool = False) -> dict:
    cache_dir = _default_cache_dir()
    try:
        with _CACHE_LOCK:
            names = list(os.listdir(cache_dir))
    except Exception:
        return {}
    best_payload = {}
    best_saved_at = -1.0
    for name in names:
        if not name.endswith(".json"):
            continue
        payload = _read_json_dict(os.path.join(cache_dir, name))
        if not payload or not isinstance(payload.get("pts"), list):
            continue
        if not _scene_payload_matches_request(payload, path, use_ff, thr, dw, fps, ff_hwaccel):
            continue
        try:
            saved_at = float(payload.get("saved_at", 0.0) or 0.0)
        except Exception:
            saved_at = 0.0
        if saved_at >= best_saved_at:
            best_payload = payload
            best_saved_at = saved_at
    return best_payload


def load_from_disk(path, use_ff, thr, dw, fps, ff_hwaccel=False):
    for key in _cache_key_candidates(path, use_ff, thr, dw, fps, ff_hwaccel):
        fp = os.path.join(_default_cache_dir(), key + ".json")
        payload = _read_json_dict(fp)
        if not payload:
            continue
        return payload.get("pts") or [], payload.get("top") or payload.get("top10") or []
    payload = _load_compatible_scene_payload(path, use_ff, thr, dw, fps, ff_hwaccel)
    if payload:
        return payload.get("pts") or [], payload.get("top") or payload.get("top10") or []
    return None, None


def _scene_key(path: str, use_ff: bool, thr: float, dw: int, fps: int, ff_hwaccel: bool = False):
    path_abs = os.path.abspath(path or "")
    try:
        st = os.stat(path_abs)
        sig = (st.st_mtime_ns, st.st_size)
    except Exception:
        sig = (0, 0)
    return (
        SCENE_CACHE_ALGO_VERSION,
        path_abs,
        sig,
        bool(use_ff),
        round(float(thr), 3),
        int(dw),
        int(fps),
        int(bool(ff_hwaccel)),
    )


def _scene_key_candidates(path: str, use_ff: bool, thr: float, dw: int, fps: int, ff_hwaccel: bool = False) -> List[tuple]:
    keys: List[tuple] = []

    def _add(key: tuple):
        if key not in keys:
            keys.append(key)

    _add(_scene_key(path, use_ff, thr, dw, fps, ff_hwaccel))
    if bool(use_ff):
        _add(_scene_key(path, use_ff, thr, dw, fps, (not bool(ff_hwaccel))))
    return keys


def scene_cache_get(path: str, use_ff: bool, thr: float, dw: int, fps: int, ff_hwaccel: bool = False):
    with _CACHE_LOCK:
        for key in _scene_key_candidates(path, use_ff, thr, dw, fps, ff_hwaccel):
            cached = _SCENE_CACHE.get(key)
            if cached is not None:
                return cached
        req_sig = _path_stat_signature(path)
        if req_sig == (0, 0):
            return None
        for key in _scene_key_candidates(path, use_ff, thr, dw, fps, ff_hwaccel):
            for cached_key, cached in list(_SCENE_CACHE.items()):
                if not (isinstance(cached_key, tuple) and len(cached_key) == len(key)):
                    continue
                if tuple(cached_key[:1]) != tuple(key[:1]) or tuple(cached_key[3:]) != tuple(key[3:]):
                    continue
                if tuple(cached_key[2]) != req_sig:
                    continue
                if not isinstance(cached, dict):
                    continue
                aliased = dict(cached)
                aliased["video_path"] = _norm_path(path)
                aliased.update(_path_signature_fields(path))
                _SCENE_CACHE[key] = aliased
                return aliased
    return None


def scene_cache_set(path: str, use_ff: bool, thr: float, dw: int, fps: int, pts_ms: List[int], top10=None, ff_hwaccel: bool = False):
    with _CACHE_LOCK:
        _SCENE_CACHE[_scene_key(path, use_ff, thr, dw, fps, ff_hwaccel)] = {
            "video_path": _norm_path(path),
            "pts": list(pts_ms or []),
            "top10": list(top10 or []),
            **_path_signature_fields(path),
        }


def scene_cache_clear_for_path(path: str):
    path_abs = _norm_path(path)
    with _CACHE_LOCK:
        for k in list(_SCENE_CACHE.keys()):
            value = _SCENE_CACHE.get(k) or {}
            stored_path = str(value.get("video_path") or (k[1] if isinstance(k, tuple) and len(k) >= 2 else ""))
            stored_mtime_ns, stored_size = _payload_video_signature(value if isinstance(value, dict) else {})
            if _video_paths_match(path_abs, stored_path, stored_mtime_ns, stored_size):
                _SCENE_CACHE.pop(k, None)


def scene_cache_clear_all():
    with _CACHE_LOCK:
        _SCENE_CACHE.clear()


from .cache_history import cache_history_entries, remove_cache_history_entries
from .cache_refilter import (
    _refilter_cache_disk_path,
    _refilter_cache_key,
    _siglip_scene_feature_cache_disk_path,
    _siglip_scene_feature_cache_key,
    refilter_cache_clear_all,
    refilter_cache_clear_for_video,
    refilter_cache_get,
    refilter_cache_set,
    siglip_scene_feature_cache_get,
    siglip_scene_feature_cache_set,
)


__all__ = [
    "_read_json_dict",
    "_payload_video_signature",
    "_path_signature_fields",
    "_video_paths_match",
    "resolve_cached_video_path",
    "cache_history_entries",
    "load_from_disk",
    "refilter_cache_clear_all",
    "refilter_cache_clear_for_video",
    "refilter_cache_get",
    "refilter_cache_set",
    "remove_cache_history_entries",
    "scene_cache_clear_all",
    "scene_cache_clear_for_path",
    "scene_cache_get",
    "scene_cache_set",
    "siglip_scene_feature_cache_get",
    "siglip_scene_feature_cache_set",
    "store_to_disk",
]
