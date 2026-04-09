import logging

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)


def install_resize_filters(window, tile, enable: bool) -> None:
    widgets: list[QtWidgets.QWidget] = []
    if tile is not None:
        widgets.append(tile)
        for attr_name in ("video_widget", "title", "add_button", "controls_container", "control_bar", "sld_pos"):
            widget = getattr(tile, attr_name, None)
            if isinstance(widget, QtWidgets.QWidget):
                widgets.append(widget)
    for widget in widgets:
        try:
            widget.setMouseTracking(True)
        except RuntimeError:
            logger.debug("detached window mouse tracking update skipped", exc_info=True)
        try:
            if enable:
                widget.installEventFilter(window)
            else:
                widget.removeEventFilter(window)
        except RuntimeError:
            logger.debug("detached window eventFilter update skipped", exc_info=True)


def frame_resize_enabled(window) -> bool:
    return bool(window._effective_compact_mode()) and not window.isMaximized() and not window.isFullScreen()


def event_pos_in_window(window, watched, event: QtGui.QMouseEvent):
    try:
        local = event.position().toPoint()
    except AttributeError:
        try:
            local = event.pos()
        except AttributeError:
            return None
    if isinstance(watched, QtWidgets.QWidget) and watched is not window:
        try:
            return watched.mapTo(window, local)
        except RuntimeError:
            logger.debug("detached window local position mapTo skipped", exc_info=True)
            return None
    return local


def resize_edges_for_pos(window, pos: QtCore.QPoint) -> int:
    if not window._frame_resize_enabled():
        return 0
    rect = window.rect()
    if rect.width() <= 0 or rect.height() <= 0:
        return 0
    margin = max(4, int(window._resize_margin))
    mask = 0
    if pos.x() <= margin:
        mask |= window._RESIZE_LEFT
    elif pos.x() >= rect.width() - margin:
        mask |= window._RESIZE_RIGHT
    if pos.y() <= margin:
        mask |= window._RESIZE_TOP
    elif pos.y() >= rect.height() - margin:
        mask |= window._RESIZE_BOTTOM
    return mask


def cursor_for_resize_edges(window, edges: int) -> QtCore.Qt.CursorShape:
    if edges in (window._RESIZE_LEFT | window._RESIZE_TOP, window._RESIZE_RIGHT | window._RESIZE_BOTTOM):
        return QtCore.Qt.CursorShape.SizeFDiagCursor
    if edges in (window._RESIZE_RIGHT | window._RESIZE_TOP, window._RESIZE_LEFT | window._RESIZE_BOTTOM):
        return QtCore.Qt.CursorShape.SizeBDiagCursor
    if edges & (window._RESIZE_LEFT | window._RESIZE_RIGHT):
        return QtCore.Qt.CursorShape.SizeHorCursor
    if edges & (window._RESIZE_TOP | window._RESIZE_BOTTOM):
        return QtCore.Qt.CursorShape.SizeVerCursor
    return QtCore.Qt.CursorShape.ArrowCursor


def apply_resize_cursor(window, edges: int) -> None:
    cursor = window._cursor_for_resize_edges(edges)
    widgets: list[QtWidgets.QWidget] = [window, window.centralWidget()]
    tile = window._tile
    if tile is not None:
        widgets.append(tile)
        for attr_name in ("video_widget", "title", "add_button"):
            widget = getattr(tile, attr_name, None)
            if isinstance(widget, QtWidgets.QWidget):
                widgets.append(widget)
    for widget in widgets:
        if widget is None:
            continue
        try:
            widget.setCursor(cursor)
        except RuntimeError:
            logger.debug("detached window resize cursor update skipped", exc_info=True)


def end_resize(window) -> None:
    window._resize_active = False
    window._resize_edges = 0
    window._apply_resize_cursor(0)


def minimum_resize_size(window) -> QtCore.QSize:
    tile = window._tile
    controls_hidden = False
    if tile is not None:
        try:
            controls_hidden = bool(getattr(tile, "controls_container").isHidden())
        except (AttributeError, RuntimeError):
            logger.debug("detached window controls hidden-state probe failed", exc_info=True)
    if ((window._effective_compact_mode() and not window.overlay_is_leader()) or window.isFullScreen() or controls_hidden):
        min_w, min_h = 160, 90
    else:
        min_w, min_h = 220, 120
    try:
        min_w = max(min_w, int(window.minimumWidth()))
    except RuntimeError:
        logger.debug("detached window minimumWidth probe failed", exc_info=True)
    try:
        min_h = max(min_h, int(window.minimumHeight()))
    except RuntimeError:
        logger.debug("detached window minimumHeight probe failed", exc_info=True)
    return QtCore.QSize(min_w, min_h)


def resized_geometry(window, delta: QtCore.QPoint) -> QtCore.QRect:
    geom = QtCore.QRect(window._resize_start_geometry)
    min_size = window._minimum_resize_size()
    min_w = int(min_size.width())
    min_h = int(min_size.height())
    x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()
    if window._resize_edges & window._RESIZE_LEFT:
        x += delta.x()
        w -= delta.x()
    elif window._resize_edges & window._RESIZE_RIGHT:
        w += delta.x()
    if window._resize_edges & window._RESIZE_TOP:
        y += delta.y()
        h -= delta.y()
    elif window._resize_edges & window._RESIZE_BOTTOM:
        h += delta.y()
    if w < min_w:
        if window._resize_edges & window._RESIZE_LEFT and not (window._resize_edges & window._RESIZE_RIGHT):
            x = geom.x() + geom.width() - min_w
        w = min_w
    if h < min_h:
        if window._resize_edges & window._RESIZE_TOP and not (window._resize_edges & window._RESIZE_BOTTOM):
            y = geom.y() + geom.height() - min_h
        h = min_h
    return QtCore.QRect(x, y, w, h)
