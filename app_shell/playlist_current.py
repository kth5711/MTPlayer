import os
from typing import Iterable

from PyQt6 import QtCore, QtWidgets

from i18n import tr
from playlist_support.trash import trash_failure_message
from video_tile_helpers.playlist_bookmarks import remove_playlist_entry_start_positions


def remove_current_playlist_items(main):
    changed = False
    for tile in main.canvas.get_selected_tiles(for_delete=True):
        playlist = getattr(tile, "playlist", []) or []
        try:
            row = int(getattr(tile, "current_index", -1))
        except Exception:
            row = -1
        if not (0 <= row < len(playlist)):
            continue
        was_playing = None
        try:
            was_playing = bool(tile.mediaplayer.is_playing())
        except Exception:
            pass
        try:
            playlist.pop(row)
        except Exception:
            continue
        remove_playlist_entry_start_positions(tile, [row])
        changed = True
        main._adjust_tile_current_index_after_row_removal(tile, [row], was_playing_override=was_playing)
    if changed:
        main.update_playlist()


def clear_selected_tile_playlists(main):
    tile_indices = _selected_playlist_tile_indices(main)
    if not tile_indices:
        return
    _clear_tile_playlists(main, tile_indices)


def clear_all_tile_playlists(main):
    tile_indices = [
        tile_index
        for tile_index, tile in enumerate(getattr(main.canvas, "tiles", []) or [])
        if _tile_has_playlist_content(tile)
    ]
    if not tile_indices:
        _show_playlist_already_empty_message(main)
        return
    _clear_tile_playlists(main, tile_indices)


def _clear_tile_playlists(main, tile_indices: list[int]) -> None:
    if not tile_indices or not _confirm_clear_tile_playlists(main, tile_indices):
        return
    cleared = 0
    for tile_index in tile_indices:
        tiles = getattr(main.canvas, "tiles", []) or []
        if not (0 <= int(tile_index) < len(tiles)):
            continue
        tile = tiles[int(tile_index)]
        if not _tile_has_playlist_content(tile):
            continue
        try:
            tile.clear_playlist()
        except Exception:
            continue
        cleared += 1
    if not cleared:
        _show_playlist_already_empty_message(main)
        return
    main.update_playlist(force=True)
    try:
        main.statusBar().showMessage(
            tr(main, "플레이리스트 비우기: {count}개 타일", count=cleared),
            3000,
        )
    except Exception:
        pass


def _confirm_clear_tile_playlists(main, tile_indices: list[int]) -> bool:
    if len(tile_indices) == 1:
        tile_label = tr(main, "타일 {index}", index=int(tile_indices[0]) + 1)
        message = tr(main, "{tile}의 플레이리스트를 비우시겠습니까?", tile=tile_label)
    else:
        message = tr(main, "{count}개 타일의 플레이리스트를 비우시겠습니까?", count=len(tile_indices))
    reply = QtWidgets.QMessageBox.question(
        main,
        tr(main, "플레이리스트 비우기"),
        message,
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
    )
    return reply == QtWidgets.QMessageBox.StandardButton.Yes


def _show_playlist_already_empty_message(main) -> None:
    try:
        main.statusBar().showMessage(tr(main, "플레이리스트가 비어 있습니다."), 3000)
    except Exception:
        pass


def _selected_playlist_tile_indices(main) -> list[int]:
    indices: list[int] = []
    tree = getattr(main, "playlist_widget", None)
    if tree is not None:
        for item in tree.selectedItems():
            meta = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if not isinstance(meta, dict):
                continue
            if str(meta.get("type") or "") not in {"tile", "file", "bookmark"}:
                continue
            try:
                tile_index = int(meta.get("tile_idx", -1))
            except Exception:
                continue
            if tile_index >= 0 and tile_index not in indices:
                indices.append(tile_index)
    if indices:
        return sorted(indices)
    if tree is not None:
        current_item = tree.currentItem()
        if current_item is not None:
            meta = current_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(meta, dict) and str(meta.get("type") or "") in {"tile", "file", "bookmark"}:
                try:
                    tile_index = int(meta.get("tile_idx", -1))
                except Exception:
                    tile_index = -1
                if tile_index >= 0:
                    indices.append(tile_index)
    if indices:
        return sorted(indices)
    for tile in _selected_canvas_tiles(main):
        try:
            tile_index = int(main.canvas.tiles.index(tile))
        except Exception:
            continue
        if tile_index not in indices:
            indices.append(tile_index)
    return sorted(indices)


def _selected_canvas_tiles(main) -> Iterable[object]:
    getter = getattr(main.canvas, "get_selected_tiles", None)
    if not callable(getter):
        return []
    try:
        return list(getter(for_delete=True) or [])
    except TypeError:
        try:
            return list(getter() or [])
        except Exception:
            return []
    except Exception:
        return []


def _tile_has_playlist_content(tile) -> bool:
    playlist = getattr(tile, "playlist", []) or []
    if playlist:
        return True
    try:
        if getattr(tile, "_current_media_kind", "none") != "none":
            return True
    except Exception:
        pass
    try:
        return bool(getattr(tile, "mediaplayer", None) and tile.mediaplayer.get_media() is not None)
    except Exception:
        return False


def _collect_current_playlist_targets(main) -> list[tuple[object, int, str]]:
    targets = []
    for tile in main.canvas.get_selected_tiles(for_delete=True):
        playlist = getattr(tile, "playlist", []) or []
        try:
            row = int(getattr(tile, "current_index", -1))
        except Exception:
            row = -1
        if 0 <= row < len(playlist):
            cur_path = playlist[row]
            if cur_path and os.path.exists(cur_path):
                targets.append((tile, row, cur_path))
    return targets


def _confirm_trash_current_playlist_items(main, targets: list[tuple[object, int, str]]) -> bool:
    if len(targets) == 1:
        msg = f"선택한 파일을 휴지통으로 보내시겠습니까?\n\n{targets[0][2]}"
    else:
        msg = f"{len(targets)}개의 파일을 휴지통으로 보내시겠습니까?"
    reply = QtWidgets.QMessageBox.question(
        main,
        "휴지통으로 이동",
        msg,
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
    )
    return reply == QtWidgets.QMessageBox.StandardButton.Yes


def _trash_current_playlist_target(main, tile, row: int, cur_path: str) -> bool:
    ok, was_playing = main._trash_playlist_entry(tile, row, cur_path)
    if not ok:
        QtWidgets.QMessageBox.warning(
            main,
            tr(main, "휴지통 실패"),
            trash_failure_message(main, cur_path),
        )
        return False
    playlist = getattr(tile, "playlist", []) or []
    if not (0 <= row < len(playlist)):
        return False
    try:
        playlist.pop(row)
    except Exception as exc:
        print("휴지통 이동 실패:", exc)
        return False
    remove_playlist_entry_start_positions(tile, [row])
    main._adjust_tile_current_index_after_row_removal(tile, [row], was_playing_override=was_playing)
    return True


def trash_current_playlist_items(main):
    targets = _collect_current_playlist_targets(main)
    if not targets or not _confirm_trash_current_playlist_items(main, targets):
        return
    changed = False
    for tile, row, cur_path in targets:
        changed = _trash_current_playlist_target(main, tile, row, cur_path) or changed
    if changed:
        main.update_playlist()
