from typing import TYPE_CHECKING, Optional

from PyQt6 import QtCore, QtGui

if TYPE_CHECKING:
    from video_tile import VideoTile


def event_filter(tile: "VideoTile", obj, event) -> Optional[bool]:
    if obj is tile.video_widget:
        return _handle_video_widget_event(tile, event)
    slider = getattr(tile, "sld_pos", None)
    if slider is not None and obj is slider:
        return _handle_seek_slider_event(tile, slider, event)
    if obj is tile.title and event.type() == QtCore.QEvent.Type.Wheel:
        return handle_volume_wheel_event(tile, event)
    return None


def _handle_video_widget_event(tile: "VideoTile", event) -> bool:
    event_type = event.type()
    if event_type == QtCore.QEvent.Type.MouseButtonDblClick:
        return _handle_video_widget_double_click(tile, event)
    if event_type == QtCore.QEvent.Type.MouseButtonPress:
        return _handle_video_widget_press(tile, event)
    if event_type == QtCore.QEvent.Type.MouseButtonRelease:
        return _handle_video_widget_release(tile, event)
    if event_type == QtCore.QEvent.Type.Wheel:
        return handle_volume_wheel_event(tile, event)
    return False


def _handle_video_widget_double_click(tile: "VideoTile", event) -> bool:
    if event.button() != QtCore.Qt.MouseButton.LeftButton:
        return False
    tile.double_clicked.emit(tile)
    return True


def _handle_video_widget_press(tile: "VideoTile", event) -> bool:
    if event.button() == QtCore.Qt.MouseButton.MiddleButton:
        _accept_event(event)
        return True
    if event.button() != QtCore.Qt.MouseButton.RightButton:
        return False
    _accept_event(event)
    return True


def _handle_video_widget_release(tile: "VideoTile", event) -> bool:
    if event.button() == QtCore.Qt.MouseButton.MiddleButton:
        _toggle_tile_selection(tile)
        _accept_event(event)
        return True
    if event.button() != QtCore.Qt.MouseButton.RightButton:
        return False
    try:
        release_pos = event.position().toPoint()
    except Exception:
        release_pos = event.pos()
    tile._show_tile_context_menu(tile.video_widget.mapToGlobal(release_pos))
    _accept_event(event)
    return True


def _handle_seek_slider_event(tile: "VideoTile", slider, event) -> bool:
    event_type = event.type()
    if event_type == QtCore.QEvent.Type.MouseMove:
        return _handle_seek_slider_mouse_move(tile, slider, event)
    if event_type == QtCore.QEvent.Type.Leave:
        return _handle_seek_slider_leave(tile, slider)
    if event_type == QtCore.QEvent.Type.MouseButtonPress:
        return _handle_seek_slider_press(tile, slider, event)
    if event_type == QtCore.QEvent.Type.MouseButtonRelease:
        return _handle_seek_slider_release(tile, slider, event)
    return False


def _handle_seek_slider_mouse_move(tile: "VideoTile", slider, event) -> bool:
    _update_slider_spread_state(tile, slider, event.pos().x())
    if _handle_bookmark_hover_preview(tile, event):
        return True
    tile.show_preview(event)
    return False


def _handle_bookmark_hover_preview(tile: "VideoTile", event) -> bool:
    if not tile._bookmark_marker_select_mode_active():
        return False
    snap_ms = tile._bookmark_snap_ms_for_slider_x(event.pos().x(), tolerance_px=14)
    if snap_ms is None:
        return False
    tile._show_preview_for_slider_x(snap_ms, event.pos().y())
    if event.buttons() & QtCore.Qt.MouseButton.LeftButton:
        tile._activate_bookmark_marker_positions([snap_ms], avoid_repeat=True)
    return True


def _handle_seek_slider_leave(tile: "VideoTile", slider) -> bool:
    tile._last_bookmark_snap_ms = None
    _update_slider_spread_state(tile, slider, None)
    tile._cancel_seek_preview_request()
    tile.preview_label.hide()
    return False


def _handle_seek_slider_press(tile: "VideoTile", slider, event) -> bool:
    if event.button() != QtCore.Qt.MouseButton.LeftButton:
        return False
    _update_slider_spread_state(tile, slider, event.position().toPoint().x())
    if tile._handle_bookmark_marker_click(event):
        return True
    jump_to_click(tile, event.pos())
    return False


def _handle_seek_slider_release(tile: "VideoTile", slider, event) -> bool:
    if event.button() != QtCore.Qt.MouseButton.LeftButton:
        return False
    tile._last_bookmark_snap_ms = None
    _update_slider_spread_state(tile, slider, event.position().toPoint().x())
    if tile._bookmark_marker_select_mode_active():
        return True
    jump_to_click(tile, event.pos())
    return False


def _update_slider_spread_state(tile: "VideoTile", slider, hover_x: Optional[int]):
    if hasattr(slider, "set_local_spread_state"):
        slider.set_local_spread_state(tile._bookmark_marker_select_mode_active(), hover_x)


def handle_volume_wheel_event(tile: "VideoTile", event: QtGui.QWheelEvent) -> bool:
    delta_y = _wheel_delta_y(event)
    if delta_y == 0:
        return False
    tile.adjust_volume_step(1 if delta_y > 0 else -1)
    _accept_event(event)
    return True


def _toggle_tile_selection(tile: "VideoTile"):
    selected_now = bool(getattr(tile, "is_selected", False)) and getattr(tile, "selection_mode", "off") == "normal"
    tile.set_selection("off" if selected_now else "normal")
    mainwin = getattr(tile, "_main_window", lambda: None)()
    canvas = getattr(tile, "_canvas_host", lambda: None)()
    if mainwin is None or canvas is None:
        return
    try:
        tile_index = list(getattr(canvas, "tiles", [])).index(tile)
    except Exception:
        return
    try:
        if selected_now and getattr(mainwin, "_last_sel_idx", None) == tile_index:
            mainwin._last_sel_idx = None
        elif not selected_now:
            mainwin._last_sel_idx = tile_index
    except Exception:
        pass


def _wheel_delta_y(event: QtGui.QWheelEvent) -> int:
    try:
        delta_y = int(event.angleDelta().y())
    except Exception:
        delta_y = 0
    if delta_y != 0:
        return delta_y
    try:
        return int(event.pixelDelta().y())
    except Exception:
        return 0


def jump_to_click(tile: "VideoTile", pos: QtCore.QPoint):
    slider = getattr(tile, "sld_pos", None)
    if slider is None:
        return
    width = slider.width()
    if width <= 0:
        return
    ratio = max(0.0, min(1.0, pos.x() / width))
    new_value = int(ratio * slider.maximum())
    if slider.value() != new_value:
        slider.setValue(new_value)
    tile.set_position(new_value / float(max(1, slider.maximum())))


def on_seek_slider_moved(tile: "VideoTile", value: int):
    slider = getattr(tile, "sld_pos", None)
    if slider is None:
        return
    tile.set_position(value / float(max(1, slider.maximum())))


def _accept_event(event):
    try:
        event.accept()
    except Exception:
        pass
