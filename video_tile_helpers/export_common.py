import hashlib
import os
import re
import urllib.parse
from typing import Optional, Tuple

WINDOWS_EXPORT_PATH_SOFT_LIMIT = 235
_INVALID_PATH_COMPONENT_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _tile_status_message(tile, text: str, timeout_ms: int = 4000) -> None:
    mw = tile._main_window() if hasattr(tile, "_main_window") else None
    if mw is None or not hasattr(mw, "statusBar"):
        return
    try:
        mw.statusBar().showMessage(str(text or ""), int(timeout_ms))
    except Exception:
        pass


def _tile_export_message(tile, text: str) -> None:
    _tile_status_message(tile, text, 3000)


def _tile_ffmpeg_bin(tile) -> str:
    from .support import current_ffmpeg_bin

    mw = tile._main_window() if hasattr(tile, "_main_window") else None
    preferred = str(getattr(mw, "ffmpeg_path", "") or "").strip() if mw is not None else ""
    return current_ffmpeg_bin(preferred)


def _current_existing_media_path(tile) -> str:
    path = str(tile._current_media_path() or "").strip()
    return path if path and os.path.exists(path) else ""


def _tile_media_source_path(tile) -> str:
    media = tile.mediaplayer.get_media()
    if not media:
        return ""
    src = media.get_mrl() or ""
    if not src.startswith("file:///"):
        return ""
    path = urllib.parse.unquote(src[8:])
    if os.name == "nt":
        path = path.replace("/", "\\")
    return path


def _export_time_strings(tile, start_pos: float, end_pos: float) -> Tuple[str, str]:
    try:
        length_ms = int(tile.mediaplayer.get_length() or 0)
    except Exception:
        length_ms = 0
    return tile._pos_to_str(start_pos, length_ms), tile._pos_to_str(end_pos, length_ms)


def get_export_path(
    tile,
    ext: str,
    start_pos: Optional[float] = None,
    end_pos: Optional[float] = None,
) -> Optional[str]:
    src_path = _tile_media_source_path(tile)
    if not src_path:
        return None
    base_dir = os.path.dirname(src_path)
    base_name, _ = os.path.splitext(os.path.basename(src_path))
    save_dir = os.path.join(base_dir, f"{base_name}_clips")
    start_pos = tile.posA if start_pos is None else start_pos
    end_pos = tile.posB if end_pos is None else end_pos
    start_str, end_str = _export_time_strings(tile, start_pos or 0.0, end_pos or 1.0)
    ext = str(ext or "").strip().lower()
    prefix = "clip" if ext == "mp4" else ("gif" if ext == "gif" else "audio_clip")
    out_path = guard_joined_export_path(
        base_dir,
        [f"{base_name}_clips", f"{prefix}_{start_str}-{end_str}.{ext}"],
        fallback_prefix=prefix,
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    return out_path


def _resolve_audio_export_range(tile) -> Optional[Tuple[int, int, float, float, int]]:
    try:
        length_ms = int(tile.mediaplayer.get_length() or 0)
    except Exception:
        length_ms = 0
    if length_ms <= 0:
        return None
    try:
        start_pos = max(0.0, min(1.0, float(tile.posA if tile.posA is not None else 0.0)))
        end_pos = max(0.0, min(1.0, float(tile.posB if tile.posB is not None else 1.0)))
    except (TypeError, ValueError):
        return None
    if end_pos < start_pos:
        start_pos, end_pos = end_pos, start_pos
    start_ms = max(0, int(round(start_pos * float(length_ms))))
    end_ms = max(start_ms + 1, int(round(end_pos * float(length_ms))))
    return start_ms, end_ms, start_pos, end_pos, length_ms


def _sanitize_path_component(text: str, fallback: str) -> str:
    value = _INVALID_PATH_COMPONENT_RE.sub("_", str(text or "").strip())
    value = value.rstrip(" .")
    return value or str(fallback or "export")


def _compact_path_component(text: str, max_len: int, fallback: str) -> str:
    value = _sanitize_path_component(text, fallback)
    max_len = max(12, int(max_len))
    if len(value) <= max_len:
        return value
    stem, ext = os.path.splitext(value)
    digest = hashlib.sha1(value.encode("utf-8", "ignore")).hexdigest()[:10]
    suffix = f"_{digest}"
    if ext:
        budget = max(1, max_len - len(ext) - len(suffix))
        stem = (stem or fallback)[:budget].rstrip(" ._") or str(fallback or "x")
        return f"{stem}{suffix}{ext}"
    budget = max(1, max_len - len(suffix))
    stem = value[:budget].rstrip(" ._") or str(fallback or "x")
    return f"{stem}{suffix}"


def _path_is_too_long(path: str) -> bool:
    if os.name != "nt":
        return False
    try:
        candidate = os.path.abspath(path)
    except Exception:
        candidate = str(path or "")
    return len(candidate) >= WINDOWS_EXPORT_PATH_SOFT_LIMIT


def guard_output_path(path: str, fallback_prefix: str = "export") -> str:
    base_dir, filename = os.path.split(str(path or ""))
    clean_name = _sanitize_path_component(filename, fallback_prefix)
    candidate = os.path.join(base_dir, clean_name)
    if not _path_is_too_long(candidate):
        return candidate
    for budget in (96, 72, 56, 40, 28, 20):
        shrunk = _compact_path_component(clean_name, budget, fallback_prefix)
        candidate = os.path.join(base_dir, shrunk)
        if not _path_is_too_long(candidate):
            return candidate
    return os.path.join(base_dir, _compact_path_component(clean_name, 16, fallback_prefix))


def guard_joined_export_path(base_dir: str, components, fallback_prefix: str = "export") -> str:
    parts = list(components or [])
    if not parts:
        return str(base_dir or "")
    clean_parts = [
        _sanitize_path_component(part, f"{fallback_prefix}_{idx + 1}")
        for idx, part in enumerate(parts)
    ]
    candidate = os.path.join(str(base_dir or ""), *clean_parts)
    if not _path_is_too_long(candidate):
        return candidate
    for budget in (96, 72, 56, 40, 28, 20):
        shrunk_parts = [
            _compact_path_component(part, budget, f"{fallback_prefix}_{idx + 1}")
            for idx, part in enumerate(clean_parts)
        ]
        candidate = os.path.join(str(base_dir or ""), *shrunk_parts)
        if not _path_is_too_long(candidate):
            return candidate
    final_parts = [
        _compact_path_component(part, 16, f"{fallback_prefix}_{idx + 1}")
        for idx, part in enumerate(clean_parts)
    ]
    return os.path.join(str(base_dir or ""), *final_parts)
