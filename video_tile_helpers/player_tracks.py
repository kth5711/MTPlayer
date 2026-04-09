from PyQt6 import QtGui

from i18n import tr


def populate_track_menus(tile, audio_menu=None, subtitle_menu=None):
    audio_menu = _clear_menu(audio_menu or getattr(tile, "audio_menu", None))
    subtitle_menu = _clear_menu(subtitle_menu or getattr(tile, "subtitle_menu", None))
    if not _player_has_media(tile):
        _add_empty_action(tile, audio_menu, "사용 가능한 오디오 트랙 없음")
        _add_empty_action(tile, subtitle_menu, "사용 가능한 자막 트랙 없음")
        return False
    _populate_audio_menu(tile, audio_menu)
    _populate_subtitle_menu(tile, subtitle_menu)
    return True


def _clear_menu(menu):
    try:
        if menu is not None:
            menu.clear()
    except Exception:
        return None
    return menu


def _player_has_media(tile) -> bool:
    try:
        return tile.mediaplayer.get_media() is not None
    except Exception:
        return False


def _add_empty_action(tile, menu, label: str):
    if menu is None:
        return
    menu.addAction(tr(tile, label)).setEnabled(False)


def _populate_audio_menu(tile, menu):
    current_audio = _safe_track_id(tile.mediaplayer.audio_get_track, -1)
    descriptions = _safe_descriptions(tile.mediaplayer.audio_get_track_description)
    _populate_track_menu(tile, menu, descriptions, current_audio, tile.set_audio_track, "Track")
    if not descriptions:
        _add_empty_action(tile, menu, "사용 가능한 오디오 트랙 없음")


def _populate_subtitle_menu(tile, menu):
    current_spu = _safe_track_id(tile.mediaplayer.video_get_spu, -1)
    descriptions = _safe_descriptions(tile.mediaplayer.video_get_spu_description)
    _populate_track_menu(tile, menu, descriptions, current_spu, tile.set_subtitle_track, "Subtitle")
    if not descriptions:
        _add_empty_action(tile, menu, "사용 가능한 자막 트랙 없음")


def _safe_track_id(getter, fallback: int) -> int:
    try:
        return int(getter())
    except Exception:
        return fallback


def _safe_descriptions(getter):
    try:
        return getter() or []
    except Exception:
        return []


def _populate_track_menu(tile, menu, descriptions, current_id, handler, fallback_prefix: str):
    if menu is None:
        return
    group = QtGui.QActionGroup(menu)
    group.setExclusive(True)
    for track in descriptions:
        track_id, track_name = _parse_track_entry(track, fallback_prefix)
        action = menu.addAction(track_name)
        action.setCheckable(True)
        action.setChecked(track_id == current_id)
        action.triggered.connect(lambda _c=False, tid=track_id: handler(tid))
        group.addAction(action)


def refresh_track_menus(tile):
    media_exists = populate_track_menus(tile, getattr(tile, "audio_menu", None), getattr(tile, "subtitle_menu", None))
    _set_track_button_enabled(getattr(tile, "btn_audio_tracks", None), media_exists)
    _set_track_button_enabled(getattr(tile, "btn_subtitle_tracks", None), media_exists)


def _set_track_button_enabled(button, enabled: bool):
    try:
        button.setEnabled(bool(enabled))
    except Exception:
        pass


def set_audio_track(tile, track_id: int):
    try:
        tile.mediaplayer.audio_set_track(int(track_id))
    except Exception:
        pass
    tile.refresh_track_menus()


def set_subtitle_track(tile, track_id: int):
    try:
        tile.mediaplayer.video_set_spu(int(track_id))
    except Exception:
        pass
    tile.refresh_track_menus()


def _parse_track_entry(track, fallback_prefix: str = "Track") -> tuple[int, str]:
    track_id = -1
    track_name = ""
    if isinstance(track, (tuple, list)) and len(track) >= 2:
        raw_id, raw_name = track[0], track[1]
    else:
        raw_id, raw_name = getattr(track, "id", -1), getattr(track, "name", "")
    try:
        track_id = int(raw_id)
    except Exception:
        track_id = -1
    track_name = _track_name_text(raw_name).strip()
    if not track_name:
        track_name = f"{fallback_prefix} {track_id}"
    return track_id, track_name


def _track_name_text(value) -> str:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return str(value)
    return str(value or "")
