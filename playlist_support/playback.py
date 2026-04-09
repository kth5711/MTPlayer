import os
from typing import Optional

from PyQt6 import QtCore

from video_tile_helpers.playlist_bookmarks import select_playlist_entry_bookmark
from i18n import tr


def play_from_tile_row(main, payload, row: Optional[int] = None):
    data = payload if isinstance(payload, dict) else {"type": "file", "tile_idx": payload, "row": row}
    _play_from_playlist_meta(main, data)


def play_from_playlist(main, item, _column):
    _play_from_playlist_meta(main, item.data(0, QtCore.Qt.ItemDataRole.UserRole))


def _play_from_playlist_meta(main, data):
    target = _resolve_playlist_target(main, data)
    if target is None:
        return
    tile, tile_index, playlist_index, bookmark_subindex, label = target
    playlist = getattr(tile, "playlist", []) or []
    try:
        select_playlist_entry_bookmark(tile, playlist_index, bookmark_subindex)
        if tile.set_media(playlist[playlist_index]):
            tile._apply_current_playlist_start_position()
            tile.play()
            _show_playback_status(main, tile_index, label)
    except Exception as exc:
        main.statusBar().showMessage(tr(main, "재생 실패: {error}", error=exc))


def _resolve_playlist_target(main, data):
    resolved = _resolve_playlist_indices(data)
    if resolved is None:
        return None
    tile_index, playlist_index, bookmark_subindex, label = resolved
    tiles = getattr(main.canvas, "tiles", [])
    if not (0 <= tile_index < len(tiles)):
        return None
    tile = tiles[tile_index]
    playlist = getattr(tile, "playlist", []) or []
    if not (0 <= playlist_index < len(playlist)):
        return None
    return tile, tile_index, playlist_index, bookmark_subindex, label or playlist[playlist_index]


def _resolve_playlist_indices(data):
    if isinstance(data, dict):
        if data.get("type") not in {"file", "bookmark"}:
            return None
        try:
            tile_index = int(data.get("tile_idx", -1))
            playlist_index = int(data.get("row", -1))
            bookmark_subindex = int(data.get("bookmark_subindex", -1)) if data.get("type") == "bookmark" else None
        except (TypeError, ValueError):
            return None
        return tile_index, playlist_index, bookmark_subindex, str(data.get("path", ""))
    if isinstance(data, (list, tuple)) and len(data) >= 2:
        try:
            return int(data[0]), int(data[1]), None, ""
        except (TypeError, ValueError):
            return None
    return None


def _show_playback_status(main, tile_index: int, label: str):
    main.statusBar().showMessage(
        tr(main, "{index}번 타일의 '{label}' 재생", index=tile_index + 1, label=os.path.basename(label) or label)
    )
