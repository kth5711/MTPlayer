import os
import urllib.parse
from typing import Optional, Tuple


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
    os.makedirs(save_dir, exist_ok=True)
    start_pos = tile.posA if start_pos is None else start_pos
    end_pos = tile.posB if end_pos is None else end_pos
    start_str, end_str = _export_time_strings(tile, start_pos or 0.0, end_pos or 1.0)
    ext = str(ext or "").strip().lower()
    prefix = "clip" if ext == "mp4" else ("gif" if ext == "gif" else "audio_clip")
    return os.path.join(save_dir, f"{prefix}_{start_str}-{end_str}.{ext}")


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
