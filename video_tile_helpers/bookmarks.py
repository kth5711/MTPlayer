from typing import TYPE_CHECKING, Optional

from PyQt6 import QtCore, QtGui

if TYPE_CHECKING:
    from video_tile import VideoTile


class _PreviewProxy:
    def __init__(self, point: QtCore.QPoint):
        self._point = point

    def pos(self) -> QtCore.QPoint:
        return self._point


def bookmark_marker_select_mode_active(tile: "VideoTile") -> bool:
    mainwin = tile._main_window()
    if mainwin is None:
        return False
    return bool(getattr(mainwin, "_bookmark_marker_select_mode", False))


def _slider_hover_x(slider) -> Optional[int]:
    try:
        local_pos = slider.mapFromGlobal(QtGui.QCursor.pos())
        hit_rect = slider.rect().adjusted(-4, -10, 4, 10)
    except Exception:
        return None
    if not hit_rect.contains(local_pos):
        return None
    return int(local_pos.x())


def sync_bookmark_marker_select_mode_from_cursor(tile: "VideoTile"):
    slider = getattr(tile, "sld_pos", None)
    if slider is None or not hasattr(slider, "set_local_spread_state"):
        return
    active = bookmark_marker_select_mode_active(tile)
    slider.set_local_spread_state(active, _slider_hover_x(slider) if active else None)


def bookmark_snap_ms_for_slider_x(
    tile: "VideoTile",
    x: int,
    tolerance_px: int = 12,
) -> Optional[int]:
    slider = getattr(tile, "sld_pos", None)
    if slider is None or not hasattr(slider, "bookmark_positions_near_x"):
        return None
    positions = slider.bookmark_positions_near_x(int(x), tolerance_px=max(2, int(tolerance_px)))
    if not positions:
        return None
    return int(positions[0])


def show_preview_for_slider_x(tile: "VideoTile", position_ms: int, y: int = 0):
    slider = getattr(tile, "sld_pos", None)
    if slider is None or not hasattr(slider, "bookmark_x_for_ms"):
        return
    marker_x = slider.bookmark_x_for_ms(int(position_ms))
    if marker_x is None:
        return
    tile.show_preview(_PreviewProxy(QtCore.QPoint(int(marker_x), max(0, int(y)))))


def activate_bookmark_marker_positions(
    tile: "VideoTile",
    positions,
    *,
    avoid_repeat: bool = False,
):
    if not positions:
        return
    target_ms = int(positions[0])
    if avoid_repeat and target_ms == getattr(tile, "_last_bookmark_snap_ms", None):
        return
    tile._last_bookmark_snap_ms = target_ms
    mainwin = tile._main_window()
    path = _current_media_path(tile)
    if path and mainwin is not None and hasattr(mainwin, "_select_bookmarks_for_path_positions"):
        mainwin._select_bookmarks_for_path_positions(path, positions)
    try:
        tile.safe_seek_from_ui(target_ms)
    except Exception:
        pass


def _current_media_path(tile: "VideoTile") -> Optional[str]:
    try:
        return tile._current_media_path()
    except Exception:
        return None


def handle_bookmark_marker_click(tile: "VideoTile", event: QtGui.QMouseEvent) -> bool:
    if not bookmark_marker_select_mode_active(tile):
        return False
    target_ms = bookmark_snap_ms_for_slider_x(tile, event.position().toPoint().x(), tolerance_px=14)
    if target_ms is None:
        return True
    activate_bookmark_marker_positions(tile, [target_ms])
    return True


def _bookmark_marks_host(tile: "VideoTile"):
    slider = getattr(tile, "sld_pos", None)
    if slider is None or not hasattr(slider, "set_bookmark_marks"):
        return None, None, None
    return slider, tile._main_window(), _current_media_path(tile)


def _bookmark_marks_visible(mainwin) -> bool:
    try:
        return bool(mainwin.bookmark_marks_visible())
    except Exception:
        getter = getattr(getattr(mainwin, "config", {}), "get", lambda *_args: True)
        return bool(getter("bookmark_marks_visible", True))


def _bookmark_positions(mainwin, path: str):
    try:
        positions = list(mainwin._bookmark_positions_for_path(path))
    except Exception:
        positions = []
    try:
        selected = list(mainwin._selected_bookmark_positions_for_path(path))
    except Exception:
        selected = []
    return positions, selected


def _resolve_bookmark_length(tile: "VideoTile", length_ms: Optional[int]) -> int:
    if length_ms is not None:
        return max(0, int(length_ms))
    try:
        return max(0, int(tile.mediaplayer.get_length() or 0))
    except Exception:
        return 0


def refresh_bookmark_marks(
    tile: "VideoTile",
    *,
    force: bool = False,
    length_ms: Optional[int] = None,
):
    slider, mainwin, path = _bookmark_marks_host(tile)
    if slider is None:
        return
    if mainwin is None or not path or not hasattr(mainwin, "_bookmark_positions_for_path"):
        tile._bookmark_marks_state = None
        slider.clear_bookmark_marks()
        return
    visible = _bookmark_marks_visible(mainwin)
    positions, selected = _bookmark_positions(mainwin, path)
    bookmark_length_ms = _resolve_bookmark_length(tile, length_ms)
    state = (str(path), tuple(positions), tuple(selected), bookmark_length_ms, visible)
    if not force and state == getattr(tile, "_bookmark_marks_state", None):
        return
    tile._bookmark_marks_state = state
    slider.set_bookmark_marks(positions, length_ms=bookmark_length_ms, visible=visible)
    if hasattr(slider, "set_selected_bookmark_positions"):
        slider.set_selected_bookmark_positions(selected)
