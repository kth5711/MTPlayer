import os

from PyQt6 import QtCore, QtGui, QtWidgets

from i18n import tr
from url_media_resolver import (
    apply_media_request_options,
    is_probably_url,
    media_source_display_name,
)
from .support import is_animated_image_file_path, is_image_file_path

from .player_media_resolve import _resolve_playback_source_with_worker


def set_media(tile, path: str) -> bool:
    path = _prepare_media_path(tile, path)
    if is_image_file_path(path):
        _load_image_media(tile, path)
        return True
    tile._clear_image_display()
    tile._set_image_mode_enabled(False)
    playback_source, media_headers = _resolved_playback_source(tile, path)
    _set_vlc_media(tile, playback_source, media_headers, path)
    _post_media_load_updates(tile, original_path=path)
    return True


def _prepare_media_path(tile, path: str) -> str:
    path = str(path or "").strip()
    if not path:
        raise RuntimeError(tr(tile, "빈 미디어 경로입니다."))
    if getattr(tile, "mediaplayer", None) is None:
        raise RuntimeError(tr(tile, "VLC 플레이어가 준비되지 않았습니다."))
    _clear_existing_media(tile)
    _update_tile_title(tile, path)
    _reset_loop_state(tile)
    return path


def _clear_existing_media(tile):
    try:
        cur_media = tile.mediaplayer.get_media()
    except Exception:
        cur_media = None
    if cur_media is None:
        return
    for action in (tile.mediaplayer.stop, lambda: tile.mediaplayer.set_media(None)):
        try:
            action()
        except Exception:
            pass


def _update_tile_title(tile, path: str):
    name = media_source_display_name(path)
    if hasattr(tile, "_restore_media_title_hitbox"):
        tile._restore_media_title_hitbox()
    fm = tile.title.fontMetrics()
    width = tile.title.maximumWidth()
    tile.title.setText(fm.elidedText(name, QtCore.Qt.TextElideMode.ElideRight, width))
    tile.title.setToolTip(path)
    _refresh_detached_window_title(tile)


def _refresh_detached_window_title(tile):
    try:
        window = tile.window()
        if window is not None and hasattr(window, "refresh_title"):
            window.refresh_title()
    except Exception:
        pass


def _reset_loop_state(tile):
    tile.posA = None
    tile.posB = None
    tile.loop_enabled = False
    tile._playlist_bookmark_end_ms = None
    tile._playlist_bookmark_guard_active = False
    tile._playlist_bookmark_auto_advance = False
    tile._update_ab_controls()


def _load_image_media(tile, path: str):
    if is_animated_image_file_path(path):
        _load_animated_image(tile, path)
    else:
        _load_static_image(tile, path)
    tile._set_image_mode_enabled(True)
    tile._refresh_image_display()
    _post_media_load_updates(tile, bookmark_length_ms=0, original_path=path)


def _load_animated_image(tile, path: str):
    movie = QtGui.QMovie(path)
    if not movie.isValid():
        _raise_image_open_error(tile, path, "GIF를 열 수 없습니다.\n\n{path}")
    movie.setCacheMode(QtGui.QMovie.CacheMode.CacheAll)
    tile._set_image_movie(movie)
    if movie.frameCount() != 0:
        try:
            movie.jumpToFrame(0)
        except Exception:
            pass
    movie.start()
    pixmap = movie.currentPixmap()
    if pixmap is not None and not pixmap.isNull():
        tile._set_image_source_pixmap(pixmap)


def _load_static_image(tile, path: str):
    pixmap = QtGui.QPixmap(path)
    if pixmap.isNull():
        _raise_image_open_error(tile, path, "이미지를 열 수 없습니다.\n\n{path}")
    tile._set_image_movie(None)
    tile._set_image_source_pixmap(pixmap)


def _raise_image_open_error(tile, path: str, message: str):
    tile._set_image_mode_enabled(False)
    tile._clear_image_display()
    tile._notify_playlist_changed(focus_mainwin=False)
    raise RuntimeError(tr(tile, message, path=path))


def _resolved_playback_source(tile, path: str):
    if not is_probably_url(path):
        return path, {}
    main = tile._main_window()
    _show_status(main, tr(tile, "URL 해석 중: {path}", path=path), 0)
    cursor_overridden = _set_wait_cursor()
    try:
        resolved = _resolve_playback_source_with_worker(tile, path)
    except Exception as exc:
        _show_status(main, tr(tile, "URL 해석 실패: {error}", error=exc), 5000)
        raise
    finally:
        _restore_wait_cursor(cursor_overridden)
    _show_resolve_success(tile, main, resolved)
    playback_source = str(resolved.get("playback_url") or path).strip() or path
    headers = resolved.get("headers")
    return playback_source, headers if isinstance(headers, dict) else {}


def _show_status(main, message: str, duration: int):
    try:
        if main is not None:
            main.statusBar().showMessage(message, duration)
    except Exception:
        pass


def _set_wait_cursor() -> bool:
    try:
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        return True
    except Exception:
        return False


def _restore_wait_cursor(cursor_overridden: bool):
    if not cursor_overridden:
        return
    try:
        QtWidgets.QApplication.restoreOverrideCursor()
    except Exception:
        pass


def _show_resolve_success(tile, main, resolved):
    if main is None or not bool(resolved.get("resolved")):
        return
    resolver_name = str(resolved.get("resolver") or "yt-dlp")
    _show_status(main, tr(tile, "URL 해석 완료 ({resolver})", resolver=resolver_name), 3000)


def _set_vlc_media(tile, playback_source: str, media_headers, original_path: str):
    media = tile.vlc_instance.media_new(playback_source)
    apply_media_request_options(media, media_headers)
    tile._apply_media_hw_options(media)
    tile._apply_saved_subtitle_option(media, original_path)
    tile.mediaplayer.set_media(media)
    tile.bind_hwnd(force=True)


def _post_media_load_updates(tile, bookmark_length_ms=None, original_path: str = ""):
    tile.refresh_track_menus()
    _schedule_track_menu_refresh(tile)
    _schedule_saved_subtitle_attach(tile, original_path)
    tile._update_add_button()
    tile._notify_playlist_changed(focus_mainwin=False)
    _refresh_bookmark_marks(tile, bookmark_length_ms)
    tile._restart_main_cursor_hide_timer_if_needed()
    tile._pulse_cursor_bridge_overlay_if_needed()


def _refresh_bookmark_marks(tile, length_ms):
    if not hasattr(tile, "refresh_bookmark_marks"):
        return
    try:
        kwargs = {"force": True}
        if length_ms is not None:
            kwargs["length_ms"] = length_ms
        tile.refresh_bookmark_marks(**kwargs)
    except Exception:
        pass


def _schedule_track_menu_refresh(tile) -> None:
    for delay_ms in (160, 520):
        QtCore.QTimer.singleShot(delay_ms, tile.refresh_track_menus)


def _schedule_saved_subtitle_attach(tile, media_path: str) -> None:
    media_path = str(media_path or "").strip()
    if not media_path or not os.path.exists(media_path):
        return
    try:
        subtitle_path = str(tile.get_external_subtitle_for_path(media_path) or "").strip()
    except Exception:
        subtitle_path = ""
    if not subtitle_path or not os.path.isfile(subtitle_path):
        return
    for delay_ms in (120, 420):
        QtCore.QTimer.singleShot(
            delay_ms,
            lambda t=tile, path=media_path: _try_attach_saved_subtitle(t, path),
        )


def _try_attach_saved_subtitle(tile, media_path: str) -> None:
    if not _current_media_matches(tile, media_path):
        return
    try:
        subtitle_path = str(tile.get_external_subtitle_for_path(media_path) or "").strip()
    except Exception:
        subtitle_path = ""
    if not subtitle_path or not os.path.isfile(subtitle_path):
        return
    try:
        tile._apply_external_subtitle_to_player(subtitle_path)
    except Exception:
        return
    tile.refresh_track_menus()


def _current_media_matches(tile, media_path: str) -> bool:
    try:
        current_path = str(tile._current_media_path() or "").strip()
    except Exception:
        current_path = ""
    if not current_path:
        return False
    try:
        return os.path.abspath(current_path) == os.path.abspath(str(media_path or ""))
    except Exception:
        return current_path == str(media_path or "")
