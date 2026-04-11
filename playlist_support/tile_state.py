from typing import Optional

from PyQt6 import QtGui, QtWidgets
from app_shell.theme import current_app_light_theme_brightness, light_theme_adjust_color


def adjust_tile_current_index_after_row_removal(main, tile, removed_rows: list[int], was_playing_override: Optional[bool] = None):
    cur = _current_playlist_index(tile)
    if cur < 0:
        return
    rows = sorted({int(row) for row in removed_rows})
    shift = sum(1 for row in rows if row < cur)
    if cur in rows:
        _handle_removed_current_entry(tile, cur, shift, was_playing_override)
        return
    new_index = cur - shift
    if new_index != cur:
        tile.current_index = max(0, new_index)


def _current_playlist_index(tile) -> int:
    try:
        return int(getattr(tile, "current_index", -1))
    except Exception:
        return -1


def _handle_removed_current_entry(tile, cur: int, shift: int, was_playing_override: Optional[bool]):
    was_playing = _removed_entry_was_playing(tile, was_playing_override)
    try:
        tile.stop()
    except Exception:
        pass
    playlist = getattr(tile, "playlist", [])
    if playlist:
        _load_next_playlist_entry(tile, playlist, cur, shift, was_playing)
        return
    _clear_tile_playlist_state(tile)


def _removed_entry_was_playing(tile, was_playing_override: Optional[bool]) -> bool:
    if isinstance(was_playing_override, bool):
        return was_playing_override
    try:
        return bool(tile.mediaplayer.is_playing())
    except Exception:
        return False


def _load_next_playlist_entry(tile, playlist, cur: int, shift: int, was_playing: bool):
    next_index = max(0, cur - shift)
    tile.current_index = min(next_index, len(playlist) - 1)
    next_path = playlist[tile.current_index]
    try:
        if tile.set_media(next_path):
            tile._apply_current_playlist_start_position()
            if was_playing:
                tile.play()
    except Exception:
        pass
    try:
        tile._update_play_button()
    except Exception:
        pass


def _clear_tile_playlist_state(tile):
    try:
        tile.clear_playlist()
    except Exception:
        tile.current_index = -1
        try:
            tile.mediaplayer.set_media(None)
        except Exception:
            pass


def playlist_current_path_for_tile(main, tile) -> str:
    try:
        getter = getattr(tile, "_current_playlist_path", None)
        if callable(getter):
            return main._normalize_playlist_path(getter())
    except Exception:
        pass
    try:
        playlist = getattr(tile, "playlist", []) or []
        idx = _current_playlist_index(tile)
        if 0 <= idx < len(playlist):
            return main._normalize_playlist_path(playlist[idx])
    except Exception:
        pass
    return ""


def playlist_tile_is_playing(main, tile) -> bool:
    try:
        return bool(getattr(tile, "mediaplayer", None) and tile.mediaplayer.is_playing())
    except Exception:
        return False


def _playlist_theme(main) -> str:
    app = QtWidgets.QApplication.instance()
    if app is not None:
        try:
            return str(app.property("multiPlayTheme") or "").strip().lower()
        except Exception:
            pass
    try:
        return str(main.current_ui_theme() or "").strip().lower()
    except Exception:
        return ""


def _playlist_palette_is_dark() -> bool:
    app = QtWidgets.QApplication.instance()
    if app is None:
        return True
    try:
        return int(app.palette().color(QtGui.QPalette.ColorRole.Window).lightness()) < 140
    except Exception:
        return True


def _playlist_use_dark_accents(main) -> bool:
    theme = _playlist_theme(main)
    if theme == "black":
        return True
    if theme == "white":
        return False
    return _playlist_palette_is_dark()


def _playlist_current_item_colors(main, is_playing: bool) -> tuple[QtGui.QColor, QtGui.QColor]:
    if _playlist_use_dark_accents(main):
        if is_playing:
            return QtGui.QColor(32, 78, 126), QtGui.QColor(246, 249, 252)
        return QtGui.QColor(56, 64, 78), QtGui.QColor(230, 236, 244)
    brightness = current_app_light_theme_brightness()
    if _playlist_theme(main) == "system":
        bg = QtGui.QColor(214, 232, 255) if is_playing else QtGui.QColor(236, 241, 247)
        fg = QtGui.QColor(12, 24, 39) if is_playing else QtGui.QColor(37, 49, 63)
        return light_theme_adjust_color(bg, brightness), fg
    if is_playing:
        return light_theme_adjust_color(QtGui.QColor(210, 229, 255), brightness), QtGui.QColor(14, 27, 43)
    return light_theme_adjust_color(QtGui.QColor(233, 239, 247), brightness), QtGui.QColor(40, 51, 66)


def _playlist_tile_header_colors(main, is_playing: bool) -> tuple[QtGui.QColor, QtGui.QColor]:
    if _playlist_use_dark_accents(main):
        if is_playing:
            return QtGui.QColor(23, 50, 79), QtGui.QColor(213, 226, 241)
        return QtGui.QColor(34, 40, 50), QtGui.QColor(177, 189, 204)
    brightness = current_app_light_theme_brightness()
    if _playlist_theme(main) == "system":
        bg = QtGui.QColor(230, 239, 250) if is_playing else QtGui.QColor(243, 246, 250)
        fg = QtGui.QColor(24, 40, 58) if is_playing else QtGui.QColor(68, 81, 96)
        return light_theme_adjust_color(bg, brightness), fg
    if is_playing:
        return light_theme_adjust_color(QtGui.QColor(226, 236, 249), brightness), QtGui.QColor(24, 40, 58)
    return light_theme_adjust_color(QtGui.QColor(242, 245, 249), brightness), QtGui.QColor(79, 91, 106)


def _apply_item_brushes(item, bg: QtGui.QColor, fg: QtGui.QColor, columns: tuple[int, ...] = (0, 1)) -> None:
    bg_brush = QtGui.QBrush(bg)
    fg_brush = QtGui.QBrush(fg)
    for column in columns:
        item.setBackground(column, bg_brush)
        item.setForeground(column, fg_brush)


def apply_playlist_tile_header_style(main, item, *, has_current: bool, is_playing: bool):
    font = item.font(0)
    font.setBold(bool(has_current))
    item.setFont(0, font)
    item.setFont(1, font)
    if not has_current:
        return
    label = item.text(0)
    if is_playing and not label.startswith("▶ "):
        item.setText(0, f"▶ {label}")
    bg, fg = _playlist_tile_header_colors(main, is_playing)
    _apply_item_brushes(item, bg, fg)


def apply_playlist_current_item_style(main, leaf, *, is_current: bool, is_playing: bool):
    font = leaf.font(0)
    font.setBold(bool(is_current))
    leaf.setFont(0, font)
    leaf.setFont(1, font)
    if not is_current:
        return
    label = leaf.text(0)
    if is_playing and not label.startswith("▶ "):
        leaf.setText(0, f"▶ {label}")
    bg, fg = _playlist_current_item_colors(main, is_playing)
    _apply_item_brushes(leaf, bg, fg)
