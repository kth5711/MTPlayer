import os
from typing import Optional

from PyQt6 import QtCore, QtWidgets

try:
    from send2trash import send2trash
except ImportError:
    send2trash = None  # type: ignore[assignment]

from video_tile_helpers.playlist_bookmarks import (
    playlist_entry_bookmark_cursor,
    playlist_entry_bookmark_positions,
    remove_playlist_entry_start_positions,
)
from i18n import tr


def trash_path(main, path: str) -> bool:
    try:
        if send2trash is None:
            return False
        if not os.path.exists(path):
            return True
        send2trash(os.path.abspath(path))
        return True
    except Exception:
        return False


def trash_playlist_entry(main, tile, row: int, path: str) -> tuple[bool, bool]:
    is_current, was_playing, current_index = _current_playlist_state(main, tile, row, path)
    if is_current:
        _detach_current_media(tile)
    ok = main._trash_path(path)
    if ok or (not is_current) or (not os.path.exists(path)):
        return bool(ok), bool(was_playing)
    _restore_trashed_current_media(tile, path, current_index, was_playing)
    return False, bool(was_playing)


def _current_playlist_state(main, tile, row: int, path: str):
    playlist = getattr(tile, "playlist", []) or []
    try:
        current_index = int(getattr(tile, "current_index", -1))
    except Exception:
        current_index = -1
    current_path = ""
    if 0 <= current_index < len(playlist):
        current_path = main._normalize_playlist_path(playlist[current_index])
    target_path = main._normalize_playlist_path(path)
    is_current = bool(current_index == int(row) and current_path and current_path == target_path)
    was_playing = False
    if is_current:
        try:
            was_playing = bool(tile.mediaplayer.is_playing())
        except Exception:
            was_playing = False
    return is_current, was_playing, current_index


def _detach_current_media(tile):
    try:
        tile.stop()
    except Exception:
        pass
    try:
        tile.mediaplayer.set_media(None)
    except Exception:
        pass


def _restore_trashed_current_media(tile, path: str, current_index: int, was_playing: bool):
    playlist = getattr(tile, "playlist", []) or []
    try:
        if 0 <= current_index < len(playlist):
            tile.current_index = current_index
        elif playlist:
            tile.current_index = min(max(0, current_index), len(playlist) - 1)
    except Exception:
        pass
    try:
        if tile.set_media(path) and was_playing:
            tile.play()
    except Exception:
        pass


def pl_delete_selected(main, trash: bool):
    metas = _selected_file_metas(main)
    if not metas:
        return
    if trash and not _confirm_trash_playlist_selection(main, metas):
        return
    for tile_index, tile_metas in _metas_by_tile(metas).items():
        _delete_tile_rows(main, main.canvas.tiles[tile_index], tile_metas, trash)
    main.update_playlist()


def _selected_file_metas(main):
    metas = []
    for item in main.playlist_widget.selectedItems():
        meta = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(meta, dict) and meta.get("type") == "file":
            metas.append(meta)
    return metas


def _metas_by_tile(metas):
    grouped: dict[int, list[dict]] = {}
    for meta in metas:
        grouped.setdefault(int(meta["tile_idx"]), []).append(meta)
    return grouped


def _delete_tile_rows(main, tile, metas: list[dict], trash: bool):
    metas.sort(key=lambda meta: meta["row"], reverse=True)
    playlist = getattr(tile, "playlist", [])
    removed_rows: list[int] = []
    removed_current_was_playing: Optional[bool] = None
    for meta in metas:
        row, path = int(meta["row"]), meta["path"]
        if not (0 <= row < len(playlist)):
            continue
        if trash:
            ok, was_playing = main._trash_playlist_entry(tile, row, path)
            if not ok:
                _show_trash_failure(main, path)
                continue
            if removed_current_was_playing is None and int(getattr(tile, "current_index", -1)) == row:
                removed_current_was_playing = bool(was_playing)
        try:
            playlist.pop(row)
            removed_rows.append(row)
        except Exception:
            pass
    remove_playlist_entry_start_positions(tile, removed_rows)
    main._adjust_tile_current_index_after_row_removal(tile, removed_rows, was_playing_override=removed_current_was_playing)


def _show_trash_failure(main, path: str):
    QtWidgets.QMessageBox.warning(
        main,
        tr(main, "휴지통 실패"),
        tr(
            main,
            "휴지통으로 보낼 수 없습니다.\n\n{path}\n\nsend2trash 모듈 설치를 권장합니다:  pip install send2trash",
            path=path,
        ),
    )


def _confirm_trash_playlist_selection(main, metas: list[dict]) -> bool:
    if len(metas) == 1:
        msg = tr(main, "선택한 파일을 휴지통으로 보내시겠습니까?\n\n{path}", path=metas[0]["path"])
    else:
        msg = tr(main, "{count}개의 파일을 휴지통으로 보내시겠습니까?", count=len(metas))
    reply = QtWidgets.QMessageBox.question(
        main,
        tr(main, "휴지통으로 이동"),
        msg,
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
    )
    return reply == QtWidgets.QMessageBox.StandardButton.Yes


def on_files_moved_between_tiles(main, dst_tile_idx: int, entries: list[tuple[int, int, str]]):
    if not entries:
        return
    try:
        dst_tile = main.canvas.tiles[dst_tile_idx]
    except IndexError:
        return
    moved_subtitles, moved_bookmarks = _remove_entries_from_source_tiles(main, entries)
    _append_entries_to_destination(dst_tile, entries, moved_subtitles, moved_bookmarks)
    main.update_playlist()


def _remove_entries_from_source_tiles(main, entries):
    by_source: dict[int, list[tuple[int, str]]] = {}
    moved_subtitles = {}
    moved_bookmarks = {}
    for src_tile_idx, row, path in entries:
        by_source.setdefault(src_tile_idx, []).append((row, path))
    for src_tile_idx, source_entries in by_source.items():
        _remove_source_tile_entries(main, src_tile_idx, source_entries, moved_subtitles, moved_bookmarks)
    return moved_subtitles, moved_bookmarks


def _remove_source_tile_entries(main, src_tile_idx, source_entries, moved_subtitles, moved_bookmarks):
    try:
        src_tile = main.canvas.tiles[src_tile_idx]
    except IndexError:
        return
    playlist = getattr(src_tile, "playlist", [])
    removed_rows: list[int] = []
    for row, _path in sorted(source_entries, reverse=True):
        if 0 <= row < len(playlist):
            actual_path = playlist[row]
            moved_bookmarks[(src_tile_idx, row, actual_path)] = (
                playlist_entry_bookmark_positions(src_tile, row),
                playlist_entry_bookmark_cursor(src_tile, row),
            )
            moved_subtitles[(src_tile_idx, row, actual_path)] = src_tile.pop_external_subtitle_for_path(actual_path)
            try:
                playlist.pop(row)
                removed_rows.append(row)
            except Exception:
                pass
    remove_playlist_entry_start_positions(src_tile, removed_rows)
    main._adjust_tile_current_index_after_row_removal(src_tile, removed_rows)


def _append_entries_to_destination(dst_tile, entries, moved_subtitles, moved_bookmarks):
    playlist = getattr(dst_tile, "playlist", [])
    for src_tile_idx, row, path in entries:
        playlist.append(path)
        dst_row = len(playlist) - 1
        positions, cursor = moved_bookmarks.get((src_tile_idx, row, path), ([], None))
        if positions:
            dst_tile.set_playlist_entry_bookmark_positions(dst_row, positions, cursor=cursor)
        subtitle = moved_subtitles.get((src_tile_idx, row, path))
        dst_tile.set_external_subtitle_for_path(path, subtitle, overwrite=False)
