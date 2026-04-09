import os

from PyQt6 import QtWidgets

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
