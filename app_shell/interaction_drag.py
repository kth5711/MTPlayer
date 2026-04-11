import logging
from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)


def _dock_contains_global_point(dock: QtWidgets.QDockWidget, gp: QtCore.QPoint) -> bool:
    try:
        if dock is None or not dock.isVisible():
            return False
        rect = dock.rect()
        global_rect = QtCore.QRect(dock.mapToGlobal(rect.topLeft()), dock.mapToGlobal(rect.bottomRight()))
        return global_rect.contains(gp)
    except RuntimeError:
        logger.debug("aux dock global hit-test failed", exc_info=True)
        return False


def _belongs_to_aux_dock(main, obj, gp: Optional[QtCore.QPoint] = None) -> bool:
    widget = obj if isinstance(obj, QtWidgets.QWidget) else None
    playlist_dock = getattr(main, "playlist_dock", None)
    bookmark_dock = getattr(main, "bookmark_dock", None)
    while widget is not None:
        if widget is playlist_dock or widget is bookmark_dock:
            return True
        widget = widget.parentWidget()
    if gp is not None:
        if _dock_contains_global_point(playlist_dock, gp) or _dock_contains_global_point(bookmark_dock, gp):
            return True
    return False


def tile_from_event_source(main, obj, gp: Optional[QtCore.QPoint] = None):
    tiles = set(getattr(main.canvas, "tiles", []))
    widget = obj if isinstance(obj, QtWidgets.QWidget) else None
    source_window = widget.window() if widget is not None else None
    while widget is not None:
        if widget in tiles:
            return widget
        widget = widget.parentWidget()
    if gp is not None:
        return main._tile_at_global(gp, preferred_window=source_window)
    return None


def clear_tile_drag_state(main):
    drag = main._tile_drag
    if drag is not None:
        tile = drag.get("tile")
        if tile is not None and hasattr(tile, "dragPreviewReady"):
            try:
                tile.dragPreviewReady.disconnect(main._on_tile_drag_preview_ready)
            except (RuntimeError, TypeError):
                logger.debug("tile drag preview disconnect skipped", exc_info=True)
    main._tile_drag = None
    if main._tile_drag_preview is not None:
        try:
            main._tile_drag_preview.hide()
        except RuntimeError:
            logger.debug("tile drag preview hide skipped", exc_info=True)
        try:
            main._tile_drag_preview.deleteLater()
        except RuntimeError:
            logger.debug("tile drag preview deleteLater skipped", exc_info=True)
        main._tile_drag_preview = None
    if main._tile_drag_cursor:
        try:
            QtWidgets.QApplication.restoreOverrideCursor()
        except RuntimeError:
            logger.debug("restoreOverrideCursor skipped", exc_info=True)
        main._tile_drag_cursor = False


def on_tile_drag_preview_ready(main, pixmap):
    drag = main._tile_drag
    preview = main._tile_drag_preview
    if not drag or preview is None:
        return
    try:
        sender = main.sender()
    except RuntimeError:
        logger.debug("tile drag preview sender lookup failed", exc_info=True)
        sender = None
    if sender is not drag.get("tile") or pixmap is None or pixmap.isNull():
        return
    preview.setPixmap(pixmap)
    preview.resize(pixmap.size())
    center_offset = QtCore.QPoint(preview.width() // 2, preview.height() // 2)
    preview.move(QtGui.QCursor.pos() - center_offset)
    try:
        preview.raise_()
    except RuntimeError:
        logger.debug("tile drag preview raise skipped", exc_info=True)


def show_tile_drag_preview(main, tile, gp: QtCore.QPoint, grab_offset: QtCore.QPoint):
    try:
        pixmap = tile.build_drag_preview_pixmap() if hasattr(tile, "build_drag_preview_pixmap") else None
    except Exception:
        logger.warning("build_drag_preview_pixmap failed; falling back to widget grab", exc_info=True)
        pixmap = None
    if pixmap is None or pixmap.isNull():
        try:
            pixmap = tile.grab()
        except RuntimeError:
            logger.debug("tile.grab() failed for drag preview", exc_info=True)
            pixmap = QtGui.QPixmap()
    if pixmap.isNull():
        return
    preview = main._tile_drag_preview
    if preview is None:
        preview = QtWidgets.QLabel(None)
        preview.setWindowFlags(
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        preview.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        preview.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        preview.setStyleSheet("background: transparent;")
        main._tile_drag_preview = preview
    preview.setPixmap(pixmap)
    preview.resize(pixmap.size())
    preview.setWindowOpacity(0.82)
    center_offset = QtCore.QPoint(preview.width() // 2, preview.height() // 2)
    preview.move(gp - center_offset)
    preview.show()


def move_tile_drag_preview(main, gp: QtCore.QPoint, grab_offset: QtCore.QPoint):
    preview = main._tile_drag_preview
    if preview is None:
        return
    center_offset = QtCore.QPoint(preview.width() // 2, preview.height() // 2)
    preview.move(gp - center_offset)
    try:
        preview.raise_()
    except RuntimeError:
        logger.debug("tile drag preview raise skipped during move", exc_info=True)


def start_tile_drag_candidate(main, tile, gp: QtCore.QPoint):
    if tile is None:
        return
    if hasattr(tile, "dragPreviewReady"):
        try:
            tile.dragPreviewReady.disconnect(main._on_tile_drag_preview_ready)
        except (RuntimeError, TypeError):
            logger.debug("tile dragPreviewReady disconnect skipped", exc_info=True)
        try:
            tile.dragPreviewReady.connect(main._on_tile_drag_preview_ready)
        except RuntimeError:
            logger.warning("tile dragPreviewReady connect failed", exc_info=True)
    tile_top_left = tile.mapToGlobal(QtCore.QPoint(0, 0))
    window = tile.window()
    if getattr(main.canvas, "is_detached", lambda _tile: False)(tile) and isinstance(window, QtWidgets.QWidget):
        grab_offset = gp - window.frameGeometry().topLeft()
    else:
        grab_offset = gp - tile_top_left
    main._tile_drag = {
        "tile": tile,
        "start": gp,
        "grab_offset": grab_offset,
        "was_detached": bool(getattr(main.canvas, "is_detached", lambda _tile: False)(tile)),
        "active": False,
    }


def update_tile_drag(main, gp: QtCore.QPoint) -> bool:
    drag = main._tile_drag
    if not drag:
        return False
    if not drag["active"]:
        if (gp - drag["start"]).manhattanLength() < QtWidgets.QApplication.startDragDistance():
            return True
        drag["active"] = True
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            main._tile_drag_cursor = True
        except RuntimeError:
            logger.debug("override cursor setup skipped for tile drag", exc_info=True)
            main._tile_drag_cursor = False
        if not drag["was_detached"]:
            main._show_tile_drag_preview(drag["tile"], gp, drag["grab_offset"])
    if drag["was_detached"]:
        window = main.canvas.detached_window_for_tile(drag["tile"])
        if window is not None:
            window.move(gp - drag["grab_offset"])
            try:
                window.raise_()
            except RuntimeError:
                logger.debug("detached window raise skipped during drag", exc_info=True)
    else:
        main._move_tile_drag_preview(gp, drag["grab_offset"])
    return True


def finish_tile_drag(main, gp: QtCore.QPoint) -> bool:
    drag = main._tile_drag
    if not drag:
        return False
    tile = drag["tile"]
    was_detached = bool(drag["was_detached"])
    was_active = bool(drag["active"])
    grab_offset = drag["grab_offset"]
    main._clear_tile_drag_state()

    if not was_active:
        source_window = tile.window() if isinstance(tile, QtWidgets.QWidget) else None
        main._select_by_global_point(
            gp,
            QtCore.Qt.KeyboardModifier.ShiftModifier,
            toggle_single_off=False,
            source_window=source_window,
        )
        return True

    if was_detached:
        opacity_host = getattr(main, "active_opacity_mode_widget", lambda: None)()
        target_tile = None
        if opacity_host is not None and hasattr(opacity_host, "docked_tile_at_global"):
            target_tile = opacity_host.docked_tile_at_global(gp, exclude=tile)
        if target_tile is None:
            target_tile = main.canvas.docked_tile_at_global(gp, exclude=tile)
        dropped_on_opacity_host = bool(
            opacity_host is not None
            and hasattr(opacity_host, "contains_global_point")
            and opacity_host.contains_global_point(gp)
        )
        if dropped_on_opacity_host:
            try:
                setattr(tile, "_opacity_dock_owner", opacity_host)
            except Exception:
                logger.debug("opacity mode owner assignment skipped during drag redock", exc_info=True)
        if dropped_on_opacity_host or main.canvas.contains_global_point(gp):
            main.canvas.redock_tile(tile, target_tile=target_tile)
            main._restore_window_focus()
        else:
            window = main.canvas.detached_window_for_tile(tile)
            if window is not None:
                window.move(gp - grab_offset)
        return True

    target_tile = main.canvas.docked_tile_at_global(gp, exclude=tile)
    if target_tile is not None:
        main.canvas.swap_tiles(tile, target_tile)
        main._restore_window_focus()
        return True
    if not main.canvas.contains_global_point(gp):
        main.canvas.detach_tile(tile, global_pos=gp, grab_offset=grab_offset)
    return True


def handle_drag_mouse_move(main, event: QtGui.QMouseEvent) -> bool:
    if main._tile_drag is None:
        return False
    try:
        if not (event.buttons() & QtCore.Qt.MouseButton.LeftButton):
            main._clear_tile_drag_state()
            return False
        gp = event.globalPosition().toPoint()
        return bool(main._update_tile_drag(gp))
    except RuntimeError:
        logger.warning("tile drag mouse-move handling failed", exc_info=True)
        main._clear_tile_drag_state()
        return False


def handle_drag_mouse_release(main, event: QtGui.QMouseEvent) -> bool:
    if main._tile_drag is None:
        return False
    try:
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return False
        gp = event.globalPosition().toPoint()
        return bool(main._finish_tile_drag(gp))
    except RuntimeError:
        logger.warning("tile drag mouse-release handling failed", exc_info=True)
        main._clear_tile_drag_state()
        return False


def handle_main_mouse_press(main, obj, event: QtGui.QMouseEvent) -> bool:
    try:
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return False
        gp = event.globalPosition().toPoint()
        if _belongs_to_aux_dock(main, obj, gp):
            return False
        source_window = obj.window() if isinstance(obj, QtWidgets.QWidget) else None
        if main._should_bypass_global_mouse_handling(gp, source_window=source_window):
            return False
        tile = main._tile_from_event_source(obj, gp)
        mods = event.modifiers() | QtWidgets.QApplication.keyboardModifiers()
        if (mods & QtCore.Qt.KeyboardModifier.ControlModifier) and tile is not None:
            _toggle_tile_multi_selection(main, tile)
            return True
        if (mods & QtCore.Qt.KeyboardModifier.ShiftModifier) and tile is not None:
            main._start_tile_drag_candidate(tile, gp)
            return True
        if main._is_main_window_click_source(obj, gp):
            main._select_by_global_point(
                gp,
                mods,
                toggle_single_off=False,
                source_window=source_window,
            )
    except RuntimeError:
        logger.warning("main mouse-press handling failed", exc_info=True)
        return False
    return False


def _toggle_tile_multi_selection(main, tile) -> None:
    selected_now = bool(getattr(tile, "is_selected", False))
    tile.set_selection("off" if selected_now else "normal")
    try:
        main._last_sel_idx = list(getattr(main.canvas, "tiles", [])).index(tile)
    except Exception:
        pass
