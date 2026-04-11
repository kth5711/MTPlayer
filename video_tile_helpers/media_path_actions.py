import os
import shutil
import time
from typing import Any

from PyQt6 import QtCore, QtWidgets

from app_shell.state import replace_recent_media_path
from bookmarks.shared import path_signature_fields
from bookmarks.state import relink_bookmarks_for_media_path
from i18n import tr


def rename_current_media_from_context(tile) -> bool:
    old_path = _current_local_media_path(tile)
    if not old_path:
        _show_missing_local_media_message(tile)
        return False
    old_name = os.path.basename(old_path)
    text, ok = _prompt_new_file_name(tile, old_name)
    if not ok:
        return False
    new_name = str(text or "").strip()
    if not new_name:
        QtWidgets.QMessageBox.information(tile, tr(tile, "파일 이름 바꾸기"), tr(tile, "파일 이름이 비어 있습니다."))
        return False
    if _contains_path_separator(new_name):
        QtWidgets.QMessageBox.warning(
            tile,
            tr(tile, "파일 이름 바꾸기"),
            tr(tile, "파일 이름에 경로를 포함할 수 없습니다."),
        )
        return False
    _, old_ext = os.path.splitext(old_name)
    if old_ext and not os.path.splitext(new_name)[1]:
        new_name = f"{new_name}{old_ext}"
    new_path = os.path.join(os.path.dirname(old_path), new_name)
    return _change_current_media_path(
        tile,
        old_path,
        new_path,
        action_title=tr(tile, "파일 이름 바꾸기"),
    )


def move_current_media_from_context(tile) -> bool:
    old_path = _current_local_media_path(tile)
    if not old_path:
        _show_missing_local_media_message(tile)
        return False
    new_path, _ = QtWidgets.QFileDialog.getSaveFileName(
        tile,
        tr(tile, "파일 경로 바꾸기"),
        old_path,
    )
    if not new_path:
        return False
    _, old_ext = os.path.splitext(old_path)
    if old_ext and not os.path.splitext(new_path)[1] and not os.path.isdir(new_path):
        new_path = f"{new_path}{old_ext}"
    return _change_current_media_path(
        tile,
        old_path,
        new_path,
        action_title=tr(tile, "파일 경로 바꾸기"),
    )


def _show_missing_local_media_message(tile) -> None:
    QtWidgets.QMessageBox.information(
        tile,
        tr(tile, "안내"),
        tr(tile, "현재 로컬 미디어 파일을 찾을 수 없습니다."),
    )


def _current_local_media_path(tile) -> str:
    try:
        path = str(tile._current_media_path() or "").strip()
    except Exception:
        path = ""
    if not path:
        return ""
    normalized = _normalize_local_path(path)
    return normalized if os.path.isfile(normalized) else ""


def _contains_path_separator(name: str) -> bool:
    for separator in (os.sep, os.altsep):
        if separator and separator in name:
            return True
    return False


def _prompt_new_file_name(tile, old_name: str) -> tuple[str, bool]:
    dialog = QtWidgets.QInputDialog(tile)
    dialog.setWindowTitle(tr(tile, "파일 이름 바꾸기"))
    dialog.setLabelText(tr(tile, "새 파일 이름:"))
    dialog.setTextEchoMode(QtWidgets.QLineEdit.EchoMode.Normal)
    dialog.setTextValue(old_name)
    line_edit = dialog.findChild(QtWidgets.QLineEdit)
    if line_edit is not None:
        stem_length = _rename_selection_length(old_name)

        def _apply_selection() -> None:
            try:
                line_edit.setSelection(0, stem_length)
            except Exception:
                pass

        QtCore.QTimer.singleShot(0, _apply_selection)
    ok = dialog.exec() == int(QtWidgets.QDialog.DialogCode.Accepted)
    return dialog.textValue(), ok


def _rename_selection_length(file_name: str) -> int:
    stem, ext = os.path.splitext(file_name)
    if ext and stem:
        return len(stem)
    return len(file_name)


def _change_current_media_path(tile, old_path: str, new_path: str, *, action_title: str) -> bool:
    main = tile._main_window()
    old_norm = _normalize_local_path(old_path)
    target_norm = _normalize_target_path(old_norm, new_path)
    if not old_norm or not os.path.isfile(old_norm):
        _show_missing_local_media_message(tile)
        return False
    if not target_norm:
        return False
    if _same_local_path(old_norm, target_norm):
        QtWidgets.QMessageBox.information(tile, action_title, tr(tile, "같은 경로입니다."))
        return False
    if os.path.exists(target_norm):
        QtWidgets.QMessageBox.warning(
            tile,
            action_title,
            tr(tile, "대상 파일이 이미 있습니다.\n\n{path}", path=target_norm),
        )
        return False
    old_signature = path_signature_fields(old_norm)
    sessions = _capture_active_media_sessions(main, old_norm)
    _release_active_media_sessions(sessions)
    try:
        final_path = _move_local_media_with_retry(old_norm, target_norm)
    except Exception as exc:
        _restore_active_media_sessions(sessions, old_norm)
        QtWidgets.QMessageBox.warning(
            tile,
            action_title,
            tr(tile, "파일 경로 변경 실패:\n\n{error}", error=exc),
        )
        return False
    _rewrite_app_media_references(main, old_norm, final_path, old_signature)
    _restore_active_media_sessions(sessions, final_path)
    _refresh_focus_review_windows(sessions)
    _announce_media_path_change(main or tile, final_path)
    return True


def _normalize_local_path(path: str) -> str:
    return os.path.abspath(os.path.normpath(str(path or "").strip()))


def _normalize_target_path(old_path: str, requested_path: str) -> str:
    target = _normalize_local_path(requested_path)
    if os.path.isdir(target):
        return os.path.join(target, os.path.basename(old_path))
    return target


def _same_local_path(a: str, b: str) -> bool:
    return os.path.normcase(_normalize_local_path(a)) == os.path.normcase(_normalize_local_path(b))


def _move_local_media_with_retry(old_path: str, new_path: str) -> str:
    target_dir = os.path.dirname(new_path)
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            moved = shutil.move(old_path, new_path)
            return _normalize_local_path(moved or new_path)
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                try:
                    QtWidgets.QApplication.processEvents()
                except Exception:
                    pass
                time.sleep(0.12)
    if last_error is not None:
        raise last_error
    raise RuntimeError("move failed")


def _capture_active_media_sessions(main, old_path: str) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    tiles = list(getattr(getattr(main, "canvas", None), "tiles", []) or [])
    for candidate in tiles:
        current_path = _tile_current_media_path(candidate)
        if not current_path or not _same_local_path(current_path, old_path):
            continue
        try:
            position_ms = int(candidate.current_playback_ms())
        except Exception:
            position_ms = 0
        try:
            was_playing = bool(candidate.mediaplayer.is_playing())
        except Exception:
            was_playing = False
        try:
            current_index = int(getattr(candidate, "current_index", -1))
        except Exception:
            current_index = -1
        sessions.append(
            {
                "tile": candidate,
                "position_ms": max(0, position_ms),
                "was_playing": was_playing,
                "current_index": current_index,
                "had_playlist": bool(getattr(candidate, "playlist", None)),
                "was_static_image": bool(getattr(candidate, "is_static_image", lambda: False)()),
            }
        )
    return sessions


def _tile_current_media_path(tile) -> str:
    try:
        path = str(tile._current_media_path() or "").strip()
    except Exception:
        path = ""
    return _normalize_local_path(path) if path else ""


def _release_active_media_sessions(sessions: list[dict[str, Any]]) -> None:
    for session in sessions:
        tile = session.get("tile")
        if tile is None:
            continue
        try:
            tile.mediaplayer.stop()
        except Exception:
            pass
        try:
            tile.mediaplayer.set_media(None)
        except Exception:
            pass
        try:
            tile._clear_image_display()
            tile._set_image_mode_enabled(False)
        except Exception:
            pass


def _rewrite_app_media_references(main, old_path: str, new_path: str, old_signature: dict[str, int]) -> None:
    tiles = list(getattr(getattr(main, "canvas", None), "tiles", []) or []) if main is not None else []
    for tile in tiles:
        _rewrite_tile_media_references(tile, old_path, new_path)
    if main is not None:
        replace_recent_media_path(main, old_path, new_path)
        relink_bookmarks_for_media_path(
            main,
            old_path,
            new_path,
            old_mtime_ns=int(old_signature.get("video_mtime_ns", 0) or 0),
            old_size=int(old_signature.get("video_size", 0) or 0),
        )
        try:
            if hasattr(main, "request_playlist_refresh"):
                main.request_playlist_refresh(force=True)
            else:
                main.update_playlist(force=True)
        except Exception:
            pass
        try:
            main.save_config()
        except Exception:
            pass


def _rewrite_tile_media_references(tile, old_path: str, new_path: str) -> None:
    playlist = list(getattr(tile, "playlist", []) or [])
    changed = False
    for index, path in enumerate(playlist):
        normalized = _normalize_path_if_local(path)
        if normalized and _same_local_path(normalized, old_path):
            playlist[index] = new_path
            changed = True
    if changed:
        tile.playlist = playlist
    subtitles = dict(getattr(tile, "external_subtitles", {}) or {})
    if subtitles:
        updated_subtitles: dict[str, str] = {}
        subtitle_changed = False
        for key, value in subtitles.items():
            normalized_key = _normalize_path_if_local(key)
            if normalized_key and _same_local_path(normalized_key, old_path):
                updated_subtitles[new_path] = value
                subtitle_changed = True
            else:
                updated_subtitles[str(key)] = value
        if subtitle_changed:
            tile.external_subtitles = updated_subtitles


def _normalize_path_if_local(path: str) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    if "://" in text:
        return ""
    return _normalize_local_path(text)


def _restore_active_media_sessions(sessions: list[dict[str, Any]], target_path: str) -> None:
    target_norm = _normalize_local_path(target_path)
    for session in sessions:
        tile = session.get("tile")
        if tile is None:
            continue
        _ensure_tile_current_path(tile, target_norm, int(session.get("current_index", -1) or -1), bool(session.get("had_playlist", False)))
        if not tile.set_media(target_norm, show_error_dialog=False):
            continue
        try:
            tile._notify_playlist_changed(focus_mainwin=False)
        except Exception:
            pass
        if bool(session.get("was_static_image", False)):
            continue
        position_ms = max(0, int(session.get("position_ms", 0) or 0))
        was_playing = bool(session.get("was_playing", False))
        QtCore.QTimer.singleShot(
            160,
            lambda t=tile, pos=position_ms, playing=was_playing: _resume_media_session(t, pos, playing),
        )


def _ensure_tile_current_path(tile, target_path: str, current_index: int, had_playlist: bool) -> None:
    playlist = list(getattr(tile, "playlist", []) or [])
    if playlist:
        if 0 <= current_index < len(playlist):
            current_path = _normalize_path_if_local(playlist[current_index])
            if current_path and _same_local_path(current_path, target_path):
                tile.current_index = current_index
                return
        for index, path in enumerate(playlist):
            normalized = _normalize_path_if_local(path)
            if normalized and _same_local_path(normalized, target_path):
                tile.current_index = index
                return
    if not had_playlist:
        tile.playlist = [target_path]
        tile.current_index = 0


def _resume_media_session(tile, position_ms: int, was_playing: bool) -> None:
    try:
        if position_ms > 0:
            tile.seek_ms(int(position_ms), play=was_playing, show_overlay=False)
        elif was_playing:
            tile.play()
    except Exception:
        try:
            if was_playing:
                tile.play()
        except Exception:
            pass


def _refresh_focus_review_windows(sessions: list[dict[str, Any]]) -> None:
    for session in sessions:
        tile = session.get("tile")
        if tile is None:
            continue
        window = getattr(tile, "_focus_review_window", None)
        if window is None:
            continue
        try:
            QtCore.QTimer.singleShot(220, window.refresh_snapshot_from_tile)
        except Exception:
            pass


def _announce_media_path_change(owner, path: str) -> None:
    try:
        owner.statusBar().showMessage(tr(owner, "미디어 경로 변경: {path}", path=path), 3000)
    except Exception:
        pass
