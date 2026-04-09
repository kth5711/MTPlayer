from __future__ import annotations

import os

from PyQt6 import QtCore


_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".ts", ".flv"}


def switch_tile_to_saved_media(tile, payload: dict) -> None:
    out_path = str(payload.get("out_path") or "").strip()
    source = str(payload.get("source") or "").strip()
    if not should_replace_stream_playback(payload):
        return
    if not out_path or not source or not os.path.isfile(out_path):
        return
    playlist = list(getattr(tile, "playlist", []) or [])
    if not playlist:
        return
    replaced_indices = [index for index, entry in enumerate(playlist) if str(entry or "").strip() == source]
    if not replaced_indices:
        return
    current_index = int(getattr(tile, "current_index", -1))
    should_reload_current = current_index in replaced_indices
    current_ms = 0
    was_playing = False
    if should_reload_current:
        try:
            current_ms = max(0, int(tile.mediaplayer.get_time() or 0))
        except Exception:
            current_ms = 0
        try:
            was_playing = bool(tile.mediaplayer.is_playing())
        except Exception:
            was_playing = False
    for index in replaced_indices:
        playlist[index] = out_path
    tile.playlist = playlist
    if should_reload_current and tile.set_media(out_path):
        schedule_saved_local_restore(tile, out_path, current_ms, was_playing)
    try:
        tile._notify_playlist_changed(focus_mainwin=False)
    except Exception:
        pass


def schedule_saved_local_restore(tile, media_path: str, target_ms: int, playing: bool) -> None:
    QtCore.QTimer.singleShot(
        220,
        lambda t=tile, path=str(media_path or ""), ms=int(target_ms), is_playing=bool(playing): restore_saved_local_playback(
            t,
            path,
            ms,
            is_playing,
            attempts=8,
        ),
    )


def restore_saved_local_playback(tile, media_path: str, target_ms: int, playing: bool, *, attempts: int) -> None:
    if getattr(tile, "mediaplayer", None) is None:
        return
    if not _is_current_media_path(tile, media_path):
        if attempts > 0:
            _schedule_restore_retry(tile, media_path, target_ms, playing, attempts - 1)
        return
    try:
        length_ms = int(tile.mediaplayer.get_length() or 0)
    except Exception:
        length_ms = 0
    if int(target_ms) > 0 and length_ms <= 0:
        if attempts > 0:
            _schedule_restore_retry(tile, media_path, target_ms, playing, attempts - 1)
        elif playing:
            _resume_after_restore(tile)
        return
    try:
        if int(target_ms) > 0:
            # Keep the player paused while restoring time so it doesn't visibly restart from 0.
            tile.seek_ms(int(target_ms), play=False, show_overlay=False)
        elif playing:
            tile.play()
        else:
            tile._update_play_button()
    except Exception:
        try:
            if playing:
                tile.play()
        except Exception:
            pass
        return
    if int(target_ms) <= 0:
        return
    if attempts <= 0:
        if playing:
            _resume_after_restore(tile)
        return
    try:
        current_ms = int(tile.mediaplayer.get_time() or -1)
    except Exception:
        current_ms = -1
    if current_ms < 0 or abs(int(target_ms) - current_ms) > 1200:
        _schedule_restore_retry(tile, media_path, target_ms, playing, attempts - 1)
        return
    if playing:
        _resume_after_restore(tile)


def _schedule_restore_retry(tile, media_path: str, target_ms: int, playing: bool, attempts: int) -> None:
    QtCore.QTimer.singleShot(
        260,
        lambda t=tile, path=str(media_path or ""), ms=int(target_ms), is_playing=bool(playing), tries=int(attempts): restore_saved_local_playback(
            t,
            path,
            ms,
            is_playing,
            attempts=tries,
        ),
    )


def _resume_after_restore(tile) -> None:
    QtCore.QTimer.singleShot(40, tile.play)


def _is_current_media_path(tile, media_path: str) -> bool:
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


def should_replace_stream_playback(payload: dict) -> bool:
    if bool(payload.get("audio_only", False)):
        return False
    out_path = str(payload.get("out_path") or "").strip()
    return is_video_file(out_path)


def is_video_file(path: str) -> bool:
    return os.path.splitext(str(path or "").lower())[1] in _VIDEO_EXTENSIONS
