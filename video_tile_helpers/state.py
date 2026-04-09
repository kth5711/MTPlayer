import os
from typing import TYPE_CHECKING, Any, Dict, Optional

from PyQt6 import QtCore
from i18n import tr
from .playlist_bookmarks import restore_playlist_entries_with_start_positions

if TYPE_CHECKING:
    from video_tile import VideoTile


def to_state(tile: "VideoTile") -> Dict[str, Any]:
    return {
        "playlist": tile.playlist[:],
        "playlist_entries": tile.playlist_entries_with_start_positions(),
        "current_index": tile.current_index,
        "position": _current_position(tile),
        "playing": _is_playing(tile),
        "volume": tile.sld_vol.value(),
        "rate": tile.playback_rate,
        "display_mode": getattr(tile, "display_mode", "fit"),
        "zoom_percent": int(getattr(tile, "zoom_percent", 100) or 100),
        "transform_mode": getattr(tile, "transform_mode", "none"),
        "subtitles": dict(tile.external_subtitles),
        "repeat": _repeat_state(tile),
        "loop": _loop_state(tile),
        "window": _window_state(tile),
    }


def _current_position(tile: "VideoTile") -> Optional[float]:
    position = None
    try:
        raw_pos = tile.mediaplayer.get_position()
        if isinstance(raw_pos, float) and 0 <= raw_pos <= 1:
            position = raw_pos
    except Exception:
        position = None
    return position


def _is_playing(tile: "VideoTile") -> bool:
    try:
        return bool(tile.mediaplayer.is_playing())
    except Exception:
        return False


def _repeat_state(tile: "VideoTile") -> Dict[str, Any]:
    return {
        "mode": tile.repeat_mode,
        "single": bool(tile.repeat_one_enabled),
        "playlist": bool(tile.playlist_repeat_enabled),
    }


def _loop_state(tile: "VideoTile") -> Dict[str, Any]:
    return {
        "enabled": tile.loop_enabled,
        "A": tile.posA,
        "B": tile.posB,
        "tile_volume": int(tile.tile_volume),
        "tile_muted": bool(tile.tile_muted),
    }


def _window_state(tile: "VideoTile") -> Dict[str, float]:
    return {
        "opacity": float(getattr(tile, "detached_window_opacity", 1.0)),
    }


def restore_session_media_state(tile: "VideoTile", position: Optional[float], playing: bool):
    def _apply_position():
        if isinstance(position, float) and 0 <= position <= 1:
            tile.set_position(position, show_overlay=False)

    if playing:
        tile.play()
        QtCore.QTimer.singleShot(180, _apply_position)
        return
    QtCore.QTimer.singleShot(180, _apply_position)
    QtCore.QTimer.singleShot(260, tile.pause)


def _restore_repeat_state(tile: "VideoTile", repeat: Any):
    repeat_mode = repeat.get("mode")
    if repeat_mode not in tile.REPEAT_MODES:
        if bool(repeat.get("single", False)):
            repeat_mode = "single"
        elif bool(repeat.get("playlist", False)):
            repeat_mode = "playlist"
        else:
            repeat_mode = "off"
    tile.set_repeat_mode(repeat_mode)


def _restore_loop_state(tile: "VideoTile", loop_state: Any):
    tile.loop_enabled = bool(loop_state.get("enabled", False))
    tile.posA = loop_state.get("A", None)
    tile.posB = loop_state.get("B", None)
    try:
        tile.tile_volume = int(loop_state.get("tile_volume", getattr(tile, "tile_volume", 120)))
    except (TypeError, ValueError):
        tile.tile_volume = int(getattr(tile, "tile_volume", 120))
    tile.tile_volume = max(0, min(120, int(tile.tile_volume)))
    tile.tile_muted = bool(loop_state.get("tile_muted", getattr(tile, "tile_muted", False)))
    if not (tile.loop_enabled and tile.posA is not None and tile.posB is not None):
        tile.loop_enabled = False


def _restore_window_state(tile: "VideoTile", window_state: Any):
    try:
        opacity = float(window_state.get("opacity", getattr(tile, "detached_window_opacity", 1.0)))
    except (AttributeError, TypeError, ValueError):
        opacity = float(getattr(tile, "detached_window_opacity", 1.0))
    tile.detached_window_opacity = max(0.10, min(1.0, opacity))


def from_state(tile: "VideoTile", state):
    try:
        _restore_playlist_state(tile, state)
        _restore_volume_and_display_state(tile, state)
        _restore_subtitles(tile, state.get("subtitles", {}))
        _restore_repeat_state(tile, state.get("repeat", {}))
        _restore_loop_state(tile, state.get("loop", {}))
        _restore_window_state(tile, state.get("window", {}))
        tile.on_volume(tile.tile_volume)
        tile._update_ab_controls()
        _restore_media_path(tile, state)
    except Exception as exc:
        print("from_state 실패:", exc)


def _restore_playlist_state(tile: "VideoTile", state):
    tile.clear_playlist()
    entries = state.get("playlist_entries", [])
    if isinstance(entries, list) and entries:
        restore_playlist_entries_with_start_positions(tile, entries)
    else:
        tile.playlist = state.get("playlist", [])[:]
    tile.current_index = int(state.get("current_index", -1))
    tile._update_add_button()


def _restore_volume_and_display_state(tile: "VideoTile", state):
    volume = int(state.get("volume", 80))
    tile.sld_vol.setValue(volume)
    tile.on_volume(volume)
    tile.playback_rate = float(state.get("rate", 1.0))
    tile.lbl_rate.setText(tr(tile, "배속: {rate:.1f}x", rate=tile.playback_rate))
    tile.set_display_mode(str(state.get("display_mode", "fit")))
    tile.set_transform_mode(str(state.get("transform_mode", "none")))
    tile.set_zoom_percent(int(state.get("zoom_percent", 100)))


def _restore_subtitles(tile: "VideoTile", subtitles: Any):
    if not isinstance(subtitles, dict):
        tile.external_subtitles = {}
        return
    tile.external_subtitles = {
        tile._normalize_media_path(key): value
        for key, value in subtitles.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _restore_media_path(tile: "VideoTile", state):
    path = _restorable_media_path(tile)
    if not path:
        return
    if not tile.set_media(path):
        return
    restore_session_media_state(tile, state.get("position", None), bool(state.get("playing", False)))


def _restorable_media_path(tile: "VideoTile") -> Optional[str]:
    if not tile.playlist:
        return None
    if not (0 <= tile.current_index < len(tile.playlist)):
        tile.current_index = 0
    path = tile.playlist[tile.current_index]
    if path and (os.path.exists(path) or "://" in path):
        return path
    return None
