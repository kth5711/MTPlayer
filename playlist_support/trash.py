import os
from typing import Optional

from PyQt6 import QtCore, QtWidgets

try:
    from send2trash import send2trash
except ImportError:
    send2trash = None  # type: ignore[assignment]

from i18n import tr
from video_tile_helpers.playlist_bookmarks import remove_playlist_entry_start_positions


def _set_last_trash_error(main, message: str) -> None:
    try:
        main._last_trash_error = str(message or "")
    except Exception:
        pass


def _last_trash_error(main) -> str:
    return str(getattr(main, "_last_trash_error", "") or "").strip()


def trash_failure_message(main, path: str) -> str:
    detail = _last_trash_error(main)
    if detail:
        return tr(main, "휴지통으로 보낼 수 없습니다.\n\n{path}\n\n원인: {error}", path=path, error=detail)
    return tr(main, "휴지통으로 보낼 수 없습니다.\n\n{path}", path=path)


def trash_path(main, path: str) -> bool:
    _set_last_trash_error(main, "")
    try:
        if send2trash is None:
            _set_last_trash_error(main, tr(main, "send2trash 모듈을 찾지 못했습니다. 설치: pip install send2trash"))
            return False
        if not os.path.exists(path):
            return True
        send2trash(os.path.abspath(path))
        return True
    except Exception as exc:
        _set_last_trash_error(main, str(exc) or exc.__class__.__name__)
        return False


def trash_playlist_entry(main, tile, row: int, path: str) -> tuple[bool, bool]:
    playlist = getattr(tile, "playlist", []) or []
    current_index, current_path = _current_playlist_state(main, tile, playlist)
    is_current = bool((current_index == int(row)) and current_path and current_path == main._normalize_playlist_path(path))
    was_playing = _prepare_current_entry_for_trash(tile, is_current)
    ok = main._trash_path(path)
    if ok or (not is_current) or (not os.path.exists(path)):
        return bool(ok), bool(was_playing)
    _restore_failed_trash_entry(tile, playlist, current_index, path, was_playing)
    return False, bool(was_playing)


def _current_playlist_state(main, tile, playlist):
    try:
        current_index = int(getattr(tile, "current_index", -1))
    except Exception:
        current_index = -1
    current_path = ""
    if 0 <= current_index < len(playlist):
        current_path = main._normalize_playlist_path(playlist[current_index])
    return current_index, current_path


def _prepare_current_entry_for_trash(tile, is_current: bool) -> bool:
    if not is_current:
        return False
    try:
        was_playing = bool(tile.mediaplayer.is_playing())
    except Exception:
        was_playing = False
    for action in (tile.stop, lambda: tile.mediaplayer.set_media(None)):
        try:
            action()
        except Exception:
            pass
    _release_focus_review_players(tile)
    _rebuild_empty_current_player(tile)
    return was_playing


def _restore_failed_trash_entry(tile, playlist, current_index: int, path: str, was_playing: bool):
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


def _release_focus_review_players(tile) -> None:
    window = getattr(tile, "_focus_review_window", None)
    if window is None:
        return
    for name in ("_release_preview_player", "_release_fullscreen_preview_player"):
        release = getattr(window, name, None)
        if callable(release):
            try:
                release()
            except Exception:
                pass


def _rebuild_empty_current_player(tile) -> None:
    release = getattr(tile, "_release_mediaplayer", None)
    recreate = getattr(tile, "_create_mediaplayer", None)
    if not callable(release) or not callable(recreate):
        return
    instance = getattr(tile, "vlc_instance", None) or getattr(tile, "shared_vlc_instance", None)
    if instance is None:
        return
    try:
        release(release_owned_instance=False)
    except Exception:
        return
    try:
        tile._last_bound_video_target = None
    except Exception:
        pass
    try:
        recreate(instance)
    except Exception:
        return
    try:
        tile.bind_hwnd(force=True)
    except Exception:
        pass
    try:
        tile._update_play_button()
    except Exception:
        pass


def pl_delete_selected(main, trash: bool):
    metas = _selected_file_metas(main)
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
    by_tile: dict[int, list[dict]] = {}
    for meta in metas:
        by_tile.setdefault(int(meta["tile_idx"]), []).append(meta)
    return by_tile


def _delete_tile_rows(main, tile, metas: list[dict], trash: bool):
    metas.sort(key=lambda meta: meta["row"], reverse=True)
    playlist = getattr(tile, "playlist", [])
    removed_rows = []
    removed_current_was_playing: Optional[bool] = None
    for meta in metas:
        removed, was_playing = _remove_playlist_row(main, tile, playlist, meta, trash, removed_rows)
        if removed and removed_current_was_playing is None and isinstance(was_playing, bool):
            removed_current_was_playing = was_playing
    remove_playlist_entry_start_positions(tile, removed_rows)
    main._adjust_tile_current_index_after_row_removal(tile, removed_rows, was_playing_override=removed_current_was_playing)


def _remove_playlist_row(main, tile, playlist, meta, trash: bool, removed_rows: list[int]) -> tuple[bool, Optional[bool]]:
    row, path = int(meta["row"]), meta["path"]
    if not (0 <= row < len(playlist)):
        return False, None
    was_playing = None
    if trash:
        ok, was_playing = main._trash_playlist_entry(tile, row, path)
        if not ok:
            _warn_trash_failure(main, path)
            return False, None
    try:
        playlist.pop(row)
        removed_rows.append(row)
        return True, was_playing
    except Exception:
        return False, None


def _warn_trash_failure(main, path: str):
    QtWidgets.QMessageBox.warning(
        main,
        tr(main, "휴지통 실패"),
        trash_failure_message(main, path),
    )


def _confirm_trash_playlist_selection(main, metas: list[dict]) -> bool:
    if not metas:
        return False
    if len(metas) == 1:
        message = tr(main, "선택한 파일을 휴지통으로 보내시겠습니까?\n\n{path}", path=metas[0]["path"])
    else:
        message = tr(main, "{count}개의 파일을 휴지통으로 보내시겠습니까?", count=len(metas))
    reply = QtWidgets.QMessageBox.question(
        main,
        tr(main, "휴지통으로 이동"),
        message,
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
    )
    return reply == QtWidgets.QMessageBox.StandardButton.Yes
