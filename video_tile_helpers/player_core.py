import sys
from typing import Optional

import vlc

from i18n import tr


def vlc_base_instance_args(tile) -> tuple[str, ...]:
    main = tile._main_window()
    args = getattr(main, "vlc_instance_args", None)
    if isinstance(args, (list, tuple)) and all(isinstance(arg, str) for arg in args):
        return tuple(args)
    if sys.platform == "win32":
        return (
            "--avcodec-hw=none",
            "--no-video-title-show",
            "--aout=directsound",
            "--no-xlib",
            "--file-caching=200",
            "--network-caching=200",
        )
    return ("--avcodec-hw=vaapi", "--no-video-title-show")


def vlc_hw_decode_enabled(tile) -> bool:
    main = tile._main_window()
    if main is None:
        return False if sys.platform == "win32" else True
    try:
        return bool(getattr(main, "vlc_hw_decode_enabled", False))
    except Exception:
        return False


def transform_instance_args(tile, mode: str) -> tuple[str, ...]:
    args = [arg for arg in tile._vlc_base_instance_args() if not arg.startswith("--avcodec-hw=")]
    args.extend(("--avcodec-hw=none", "--video-filter=transform", f"--transform-type={mode}"))
    return _dedupe_args(args)


def _dedupe_args(args) -> tuple[str, ...]:
    deduped = []
    seen = set()
    for arg in args:
        if arg in seen:
            continue
        seen.add(arg)
        deduped.append(arg)
    return tuple(deduped)


def create_mediaplayer(tile, instance):
    tile.vlc_instance = instance
    player = instance.media_player_new()
    tile.mediaplayer = player
    tile.event_manager = player.event_manager()
    tile.event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, tile.on_finished)
    _disable_player_inputs(player)
    _apply_player_defaults(tile, player)


def _disable_player_inputs(player):
    for setter in (player.video_set_mouse_input, player.video_set_key_input):
        try:
            setter(False)
        except Exception:
            pass


def _apply_player_defaults(tile, player):
    try:
        tile._apply_tile_volume()
    except Exception:
        pass
    try:
        player.set_rate(tile.playback_rate)
    except Exception:
        pass


def release_mediaplayer(tile, release_owned_instance: bool = True):
    _detach_end_reached_event(tile)
    _stop_and_release_player(tile)
    tile.event_manager = None
    tile.mediaplayer = None
    if release_owned_instance:
        _release_owned_instance(tile)


def _detach_end_reached_event(tile):
    try:
        if tile.event_manager is not None:
            tile.event_manager.event_detach(vlc.EventType.MediaPlayerEndReached, tile.on_finished)
    except Exception:
        pass


def _stop_and_release_player(tile):
    player = getattr(tile, "mediaplayer", None)
    if player is None:
        return
    for action in (player.stop, lambda: player.set_media(None), player.release):
        try:
            action()
        except Exception:
            pass


def _release_owned_instance(tile):
    owned = getattr(tile, "_owned_vlc_instance", None)
    if owned is None:
        return
    try:
        owned.release()
    except Exception:
        pass
    tile._owned_vlc_instance = None


def current_video_target(tile) -> Optional[tuple[str, int]]:
    video_widget = getattr(tile, "video_widget", None)
    if video_widget is None:
        return None
    try:
        winid = int(video_widget.winId())
    except Exception:
        return None
    if sys.platform.startswith("linux"):
        return ("xwindow", winid)
    if sys.platform == "win32":
        return ("hwnd", winid)
    if sys.platform == "darwin":
        return ("nsobject", winid)
    return ("generic", winid)


def bind_hwnd(tile, force: bool = False):
    target = current_video_target(tile)
    if target is None:
        return
    if not force and getattr(tile, "_last_bound_video_target", None) == target:
        tile._apply_display_mode()
        return
    _bind_target(tile, target)
    tile._last_bound_video_target = target
    tile._apply_display_mode()


def _bind_target(tile, target: tuple[str, int]):
    kind, winid = target
    if kind == "xwindow":
        tile.mediaplayer.set_xwindow(winid)
    elif kind == "hwnd":
        tile.mediaplayer.set_hwnd(winid)
    elif kind == "nsobject":
        tile.mediaplayer.set_nsobject(winid)


def should_use_hw_accel(tile) -> bool:
    if not vlc_hw_decode_enabled(tile):
        return False
    main = tile._main_window()
    try:
        tiles = getattr(getattr(main, "canvas", None), "tiles", [])
        return sum(1 for child in tiles if getattr(child, "playlist", None)) >= 6
    except Exception:
        return False


def apply_media_hw_options(tile, media):
    if media is None or getattr(tile, "transform_mode", "none") != "none":
        return
    for option in _media_hw_options(tile):
        try:
            media.add_option(option)
        except Exception:
            pass


def _media_hw_options(tile) -> tuple[str, ...]:
    if not tile._should_use_hw_accel():
        return ()
    if sys.platform == "win32":
        return (":avcodec-hw=d3d11va", ":avcodec-threads=1")
    if sys.platform == "darwin":
        return (":avcodec-hw=videotoolbox",)
    return (":avcodec-hw=vaapi",)


def play(tile):
    if tile.is_static_image():
        tile._update_play_button()
        return
    current_target = current_video_target(tile)
    if current_target is not None and getattr(tile, "_last_bound_video_target", None) != current_target:
        tile.bind_hwnd()
    tile.mediaplayer.set_rate(tile.playback_rate)
    tile.mediaplayer.play()
    tile._update_play_button()
    _refresh_playlist_play_state(tile)
    _show_playback_status_overlay(tile, tr(tile, "재생"))


def pause(tile):
    if tile.is_static_image():
        tile._update_play_button()
        return
    tile.mediaplayer.pause()
    tile._update_play_button()
    _refresh_playlist_play_state(tile)
    _show_playback_status_overlay(tile, tr(tile, "일시정지"))


def toggle_play(tile):
    if tile.is_static_image():
        tile._update_play_button()
        return
    if tile.mediaplayer.is_playing():
        tile.pause()
        return
    if tile.mediaplayer.get_media() is None and tile.playlist:
        if not tile.set_media(tile.playlist[0]):
            return
        tile.current_index = 0
    tile.play()


def stop(tile):
    if tile.is_static_image():
        tile.lbl_time.setText(tr(tile, "이미지"))
        tile._update_play_button()
        return
    if tile.mediaplayer.is_playing():
        tile.mediaplayer.pause()
    tile.mediaplayer.stop()
    tile.lbl_time.setText("00:00 / 00:00")
    _refresh_stop_bookmarks(tile)
    tile._update_play_button()
    _refresh_playlist_play_state(tile)


def _refresh_stop_bookmarks(tile):
    if not hasattr(tile, "refresh_bookmark_marks"):
        return
    try:
        tile.refresh_bookmark_marks(force=True, length_ms=0)
    except Exception:
        pass


def _refresh_playlist_play_state(tile) -> None:
    main = tile._main_window()
    if main is None:
        return
    try:
        if hasattr(main, "request_playlist_refresh"):
            # VLC play/pause state flips asynchronously, so refresh slightly later.
            main.request_playlist_refresh(delay_ms=120)
        else:
            main.update_playlist()
    except Exception:
        pass


def _show_playback_status_overlay(tile, text: str) -> None:
    try:
        media = tile.mediaplayer.get_media()
    except Exception:
        media = None
    if media is None:
        return
    show_overlay = getattr(tile, "_show_status_overlay", None)
    if callable(show_overlay):
        show_overlay(text)
