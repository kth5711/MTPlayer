import os
from typing import Optional

from PyQt6 import QtCore

from i18n import tr
from video_tile_helpers.playlist_bookmarks import (
    playlist_entry_bookmark_cursor,
    playlist_entry_bookmark_positions,
    remove_playlist_entry_start_positions,
    select_playlist_entry_bookmark,
)


def on_files_moved_between_tiles(main, dst_tile_idx: int, entries: list[tuple[int, int, str]]):
    if not entries:
        return
    try:
        dst_tile = main.canvas.tiles[dst_tile_idx]
    except IndexError:
        return
    moved_subtitles, moved_bookmarks = _remove_source_entries(main, entries)
    _append_destination_entries(dst_tile, entries, moved_subtitles, moved_bookmarks)
    main.update_playlist()


def _remove_source_entries(main, entries):
    moved_subtitles = {}
    moved_bookmarks = {}
    for src_tile_idx, src_entries in _entries_by_source(entries).items():
        try:
            src_tile = main.canvas.tiles[src_tile_idx]
        except IndexError:
            continue
        playlist = getattr(src_tile, "playlist", [])
        removed_rows = []
        for row, _path in sorted(src_entries, reverse=True):
            if 0 <= row < len(playlist):
                _capture_removed_entry(src_tile, src_tile_idx, row, playlist, moved_subtitles, moved_bookmarks)
                try:
                    playlist.pop(row)
                    removed_rows.append(row)
                except Exception:
                    pass
        remove_playlist_entry_start_positions(src_tile, removed_rows)
        main._adjust_tile_current_index_after_row_removal(src_tile, removed_rows)
    return moved_subtitles, moved_bookmarks


def _entries_by_source(entries):
    by_source: dict[int, list[tuple[int, str]]] = {}
    for src_tile_idx, row, path in entries:
        by_source.setdefault(src_tile_idx, []).append((row, path))
    return by_source


def _capture_removed_entry(src_tile, src_tile_idx, row: int, playlist, moved_subtitles, moved_bookmarks):
    actual_path = playlist[row]
    moved_bookmarks[(src_tile_idx, row, actual_path)] = (
        playlist_entry_bookmark_positions(src_tile, row),
        playlist_entry_bookmark_cursor(src_tile, row),
    )
    moved_subtitles[(src_tile_idx, row, actual_path)] = src_tile.pop_external_subtitle_for_path(actual_path)


def _append_destination_entries(dst_tile, entries, moved_subtitles, moved_bookmarks):
    playlist = getattr(dst_tile, "playlist", [])
    for src_tile_idx, row, path in entries:
        playlist.append(path)
        dst_row = len(playlist) - 1
        positions, cursor = moved_bookmarks.get((src_tile_idx, row, path), ([], None))
        if positions:
            dst_tile.set_playlist_entry_bookmark_positions(dst_row, positions, cursor=cursor)
        dst_tile.set_external_subtitle_for_path(path, moved_subtitles.get((src_tile_idx, row, path)), overwrite=False)


def play_from_tile_row(main, payload, row: Optional[int] = None):
    data = payload if isinstance(payload, dict) else {"type": "file", "tile_idx": payload, "row": row}
    _play_from_playlist_meta(main, data)


def play_from_playlist(main, item, column):
    _play_from_playlist_meta(main, item.data(0, QtCore.Qt.ItemDataRole.UserRole))


def _play_from_playlist_meta(main, data):
    target = _playlist_target_from_data(data)
    if target is None:
        return
    tile, tile_index, playlist_index = _resolve_playlist_target(main, *target[:2])
    if tile is None:
        return
    _play_tile_playlist_entry(main, tile, tile_index, playlist_index, target[2], data)


def _playlist_target_from_data(data):
    if isinstance(data, dict):
        if data.get("type") not in {"file", "bookmark"}:
            return None
        try:
            bookmark_subindex = int(data.get("bookmark_subindex", -1)) if data.get("type") == "bookmark" else None
            return int(data.get("tile_idx", -1)), int(data.get("row", -1)), bookmark_subindex
        except (TypeError, ValueError):
            return None
    if isinstance(data, (list, tuple)) and len(data) >= 2:
        try:
            return int(data[0]), int(data[1]), None
        except (TypeError, ValueError):
            return None
    return None


def _resolve_playlist_target(main, tile_index: int, playlist_index: int):
    tiles = getattr(main.canvas, "tiles", [])
    if not (0 <= tile_index < len(tiles)):
        return None, tile_index, playlist_index
    tile = tiles[tile_index]
    playlist = getattr(tile, "playlist", []) or []
    if not (0 <= playlist_index < len(playlist)):
        return None, tile_index, playlist_index
    return tile, tile_index, playlist_index


def _play_tile_playlist_entry(main, tile, tile_index: int, playlist_index: int, bookmark_subindex, data):
    playlist = getattr(tile, "playlist", []) or []
    try:
        select_playlist_entry_bookmark(tile, playlist_index, bookmark_subindex)
        if tile.set_media(playlist[playlist_index]):
            tile._apply_current_playlist_start_position()
            tile.play()
            _show_playlist_play_message(main, tile_index, data, playlist[playlist_index])
    except Exception as exc:
        main.statusBar().showMessage(tr(main, "재생 실패: {error}", error=exc))


def _show_playlist_play_message(main, tile_index: int, data, path: str):
    label = str(data.get("path", path)) if isinstance(data, dict) else path
    main.statusBar().showMessage(
        tr(main, "{index}번 타일의 '{label}' 재생", index=tile_index + 1, label=os.path.basename(label) or label)
    )
