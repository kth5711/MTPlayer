from PyQt6 import QtGui

from i18n import tr
from url_media_resolver import is_probably_url


def add_track_menus(tile, menu):
    source = _current_source(tile)
    is_stream_media = bool(source) and is_probably_url(source)
    audio_menu = menu.addMenu(tr(tile, "오디오 트랙"))
    subtitle_menu = menu.addMenu(tr(tile, "자막 트랙"))
    if is_stream_media:
        disabled = tr(tile, "URL/스트림 재생 중에는 여기서 트랙 조회를 끔")
        audio_menu.addAction(disabled).setEnabled(False)
        subtitle_menu.addAction(disabled).setEnabled(False)
        return
    audio_menu.aboutToShow.connect(lambda: tile._populate_track_menus(audio_menu=audio_menu, subtitle_menu=None))
    subtitle_menu.aboutToShow.connect(lambda: tile._populate_track_menus(audio_menu=None, subtitle_menu=subtitle_menu))


def add_repeat_mode_menu(tile, menu):
    repeat_menu = menu.addMenu(_repeat_mode_label(tile))
    group = QtGui.QActionGroup(repeat_menu)
    group.setExclusive(True)
    for mode, label in _repeat_mode_actions(tile).items():
        action = repeat_menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(getattr(tile, "repeat_mode", "off") == mode)
        action.triggered.connect(lambda _checked=False, m=mode: tile.set_repeat_mode(m))
        group.addAction(action)


def add_export_actions(tile, menu):
    source = _current_source(tile)
    is_stream_media = bool(source) and is_probably_url(source)
    if is_stream_media:
        menu.addSeparator()
        action = menu.addAction(tr(tile, "URL 저장..."))
        action.setEnabled(not bool(getattr(tile, "_export_worker_busy", False)))
        action.triggered.connect(tile._save_url_from_context)
        return
    current_path = tile._current_media_path()
    if not current_path or tile.is_static_image():
        return
    menu.addSeparator()
    menu.addAction(tr(tile, "프레임셋 저장..."), tile.save_frame_set)
    _add_export_audio_action(tile, menu)


def add_export_audio_action(tile, menu):
    current_path = tile._current_media_path()
    if not current_path or tile.is_static_image():
        return
    _add_export_audio_action(tile, menu)


def _add_export_audio_action(tile, menu):
    action = menu.addAction(tr(tile, "오디오 클립 저장..."))
    action.setEnabled(not bool(getattr(tile, "_export_worker_busy", False)))
    if tile.posA is None and tile.posB is None:
        action.setText(tr(tile, "오디오 클립 저장... (A/B 없으면 전체)"))
    action.triggered.connect(tile.export_audio_clip)


def _current_source(tile) -> str:
    if not (tile.playlist and 0 <= tile.current_index < len(tile.playlist)):
        return ""
    try:
        return str(tile.playlist[tile.current_index] or "").strip()
    except Exception:
        return ""


def _repeat_mode_label(tile) -> str:
    return _repeat_mode_actions(tile).get(getattr(tile, "repeat_mode", "off"), tr(tile, "반복: 끔"))


def _repeat_mode_actions(tile):
    return {
        "off": tr(tile, "반복: 끔"),
        "single": tr(tile, "반복: 1개"),
        "playlist": tr(tile, "반복: 목록"),
    }
