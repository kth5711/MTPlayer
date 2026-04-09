import logging

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)


def _base_event_filter(window, watched, event):
    return QtWidgets.QMainWindow.eventFilter(window, watched, event)


def _event_global_pos(event):
    getter = getattr(event, "globalPosition", None)
    if callable(getter):
        try:
            return getter().toPoint()
        except Exception:
            return None
    getter = getattr(event, "globalPos", None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            return None
    return None


def _handle_fullscreen_leave(window) -> bool:
    if not (window.isFullScreen() or bool(window.windowState() & QtCore.Qt.WindowState.WindowFullScreen)):
        return False
    window._fullscreen_controls_visible = False
    window._fullscreen_hover_pending_pos = None
    try:
        window._fullscreen_hover_timer.stop()
    except RuntimeError:
        logger.debug("detached window hover timer stop skipped on leave", exc_info=True)
    try:
        window._fullscreen_ui_hide_timer.stop()
    except RuntimeError:
        logger.debug("detached window ui hide timer stop skipped on leave", exc_info=True)
    window._sync_tile_ui_for_window_state(force=True)
    window._hide_fullscreen_ui()
    if not window._resize_active:
        window._apply_resize_cursor(0)
    return True


def _handle_resize_press(window, event: QtGui.QMouseEvent, pos) -> bool:
    if window.overlay_is_leader() and event.button() == QtCore.Qt.MouseButton.LeftButton:
        window._request_overlay_restack(delays=(0, 100))
    if event.button() != QtCore.Qt.MouseButton.LeftButton:
        return False
    edges = window._resize_edges_for_pos(pos)
    if not edges:
        return False
    window._resize_active = True
    window._resize_edges = edges
    window._resize_start_global = event.globalPosition().toPoint()
    window._resize_start_geometry = window.geometry()
    window._apply_resize_cursor(edges)
    event.accept()
    return True


def _handle_resize_move(window, event: QtGui.QMouseEvent, pos) -> bool:
    if window._resize_active and (event.buttons() & QtCore.Qt.MouseButton.LeftButton):
        delta = event.globalPosition().toPoint() - window._resize_start_global
        window.setGeometry(window._resized_geometry(delta))
        event.accept()
        return True
    window._apply_resize_cursor(window._resize_edges_for_pos(pos))
    return False


def _handle_resize_release(window, event: QtGui.QMouseEvent) -> bool:
    if window._resize_active:
        window._end_resize()
        event.accept()
        return True
    if window.overlay_is_leader() and event.button() == QtCore.Qt.MouseButton.LeftButton:
        window._request_overlay_restack(delays=(0, 80))
    return False


def _event_resize_pos(window, watched, event: QtGui.QMouseEvent):
    if not window._frame_resize_enabled():
        if not window._resize_active:
            window._apply_resize_cursor(0)
        return None
    if event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier:
        if not window._resize_active:
            window._apply_resize_cursor(0)
        return None
    return window._event_pos_in_window(watched, event)


def event_filter(window, watched, event):
    if window._closing_for_app_exit:
        return _base_event_filter(window, watched, event)
    et = event.type()
    if et == QtCore.QEvent.Type.Leave and _handle_fullscreen_leave(window):
        return False
    if et in (
        QtCore.QEvent.Type.MouseMove,
        QtCore.QEvent.Type.MouseButtonPress,
        QtCore.QEvent.Type.MouseButtonRelease,
        QtCore.QEvent.Type.Wheel,
        QtCore.QEvent.Type.Enter,
        QtCore.QEvent.Type.HoverMove,
    ):
        try:
            global_pos = _event_global_pos(event)
            if global_pos is None:
                global_pos = QtGui.QCursor.pos()
            window._queue_fullscreen_hover(global_pos)
        except RuntimeError:
            logger.debug("detached window queue_fullscreen_hover skipped", exc_info=True)
    if et == QtCore.QEvent.Type.Leave and not window._resize_active:
        window._apply_resize_cursor(0)
        return False
    if et not in (QtCore.QEvent.Type.MouseMove, QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.MouseButtonRelease):
        return _base_event_filter(window, watched, event)
    if not isinstance(event, QtGui.QMouseEvent):
        return _base_event_filter(window, watched, event)
    pos = _event_resize_pos(window, watched, event)
    if pos is None:
        return _base_event_filter(window, watched, event)
    if et == QtCore.QEvent.Type.MouseButtonPress:
        if _handle_resize_press(window, event, pos):
            return True
        return _base_event_filter(window, watched, event)
    if et == QtCore.QEvent.Type.MouseMove:
        return _handle_resize_move(window, event, pos)
    if et == QtCore.QEvent.Type.MouseButtonRelease and _handle_resize_release(window, event):
        return True
    return _base_event_filter(window, watched, event)


def move_event(window, event: QtGui.QMoveEvent) -> None:
    QtWidgets.QMainWindow.moveEvent(window, event)
    if int(getattr(window, "_overlay_geometry_sync_depth", 0)) <= 0 and window.overlay_active():
        window.overlayGeometryChanged.emit(window._tile, QtCore.QRect(window.geometry()))


def resize_event(window, event: QtGui.QResizeEvent) -> None:
    QtWidgets.QMainWindow.resizeEvent(window, event)
    try:
        window.refresh_media_layout(force_bind=True)
    except RuntimeError:
        logger.debug("detached window media layout refresh skipped on resize", exc_info=True)
    if int(getattr(window, "_overlay_geometry_sync_depth", 0)) <= 0 and window.overlay_active():
        window.overlayGeometryChanged.emit(window._tile, QtCore.QRect(window.geometry()))


def change_event(window, event: QtCore.QEvent) -> None:
    QtWidgets.QMainWindow.changeEvent(window, event)
    if event.type() == QtCore.QEvent.Type.ActivationChange and window.overlay_is_leader() and window.isActiveWindow():
        window._request_overlay_restack(immediate=True, delays=(0, 100, 220, 380, 560))


def focus_in_event(window, event: QtGui.QFocusEvent) -> None:
    QtWidgets.QMainWindow.focusInEvent(window, event)
    tile = getattr(window, "_tile", None)
    main = tile._main_window() if tile is not None and hasattr(tile, "_main_window") else None
    if main is not None and hasattr(main, "canvas"):
        setattr(main.canvas, "_last_active_detached_window", window)
    window._request_overlay_restack(immediate=True, delays=(0, 80))


def show_event(window, event: QtGui.QShowEvent) -> None:
    QtWidgets.QMainWindow.showEvent(window, event)
    tile = getattr(window, "_tile", None)
    main = tile._main_window() if tile is not None and hasattr(tile, "_main_window") else None
    if main is not None and hasattr(main, "canvas"):
        setattr(main.canvas, "_last_active_detached_window", window)
    try:
        window.refresh_media_layout(force_bind=True)
    except RuntimeError:
        logger.debug("detached window media layout refresh skipped on show", exc_info=True)
    window._request_overlay_restack(immediate=True, delays=(0, 80))
