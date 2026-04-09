import logging

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)


def _schedule_window_callback(window, delay_ms: int, callback) -> None:
    scheduler = getattr(window, "_schedule_deferred_callback", None)
    if callable(scheduler):
        try:
            if scheduler(delay_ms, callback):
                return
        except RuntimeError:
            logger.debug("detached window deferred scheduler skipped", exc_info=True)
    QtCore.QTimer.singleShot(delay_ms, callback)


def _safe_apply_focus_once(window) -> None:
    try:
        apply_focus_once(window)
    except RuntimeError:
        logger.debug("detached window focus restore skipped for deleted window", exc_info=True)


def prepare_for_app_close(window) -> None:
    window._closing_for_app_exit = True
    cancel = getattr(window, "_cancel_deferred_callbacks", None)
    if callable(cancel):
        try:
            cancel()
        except RuntimeError:
            logger.debug("detached window deferred cancel skipped during app close", exc_info=True)
    try:
        window.hide()
    except RuntimeError:
        logger.debug("detached window hide skipped during app close", exc_info=True)


def enter_fullscreen_mode(window) -> None:
    if window.isFullScreen() or bool(window.windowState() & QtCore.Qt.WindowState.WindowFullScreen):
        return
    try:
        window._pre_fullscreen_maximized = window.isMaximized() or bool(
            window.windowState() & QtCore.Qt.WindowState.WindowMaximized
        )
    except RuntimeError:
        logger.debug("detached window pre-fullscreen maximized snapshot failed", exc_info=True)
        window._pre_fullscreen_maximized = False
    try:
        window._pre_fullscreen_geometry = QtCore.QRect(window.geometry())
    except RuntimeError:
        logger.debug("detached window pre-fullscreen geometry snapshot failed", exc_info=True)
    window._pre_fullscreen_geometry = None
    window._fullscreen_controls_visible = False
    window._fullscreen_hover_pending_pos = None
    try:
        window._fullscreen_ui_hide_timer.stop()
    except RuntimeError:
        logger.debug("detached window fullscreen ui hide timer stop skipped", exc_info=True)
    window.showFullScreen()
    window._sync_tile_ui_for_window_state(force=True)
    window.refresh_media_layout(force_bind=True, delays=(0, 60, 180))
    window._show_fullscreen_ui_transient(
        show_controls=not (window._effective_compact_mode() or window.overlay_is_leader())
    )
    window.restore_focus()
    if window.overlay_is_leader():
        window._request_overlay_restack(delays=(0, 80, 180))


def exit_fullscreen_mode(window) -> None:
    if not (window.isFullScreen() or bool(window.windowState() & QtCore.Qt.WindowState.WindowFullScreen)):
        return
    try:
        window._fullscreen_hover_timer.stop()
    except RuntimeError:
        logger.debug("detached window fullscreen hover timer stop skipped", exc_info=True)
    try:
        window._fullscreen_ui_hide_timer.stop()
    except RuntimeError:
        logger.debug("detached window fullscreen ui hide timer stop skipped", exc_info=True)
    window._fullscreen_hover_pending_pos = None
    window._fullscreen_controls_visible = False
    if window._pre_fullscreen_maximized:
        window.showMaximized()
    else:
        window.showNormal()
        if window._pre_fullscreen_geometry is not None:
            window.setGeometry(window._pre_fullscreen_geometry)
    window._sync_tile_ui_for_window_state(force=True)
    window.refresh_media_layout(force_bind=True, delays=(0, 60, 180))
    window._show_cursor()
    window.restore_focus()
    if window.overlay_is_leader():
        window._request_overlay_restack(delays=(0, 80, 180, 320))


def apply_focus_once(window) -> None:
    if getattr(window, "_dispose_requested", False):
        return
    if window._overlay_click_through:
        return
    if not window.overlay_is_leader():
        try:
            window.raise_()
        except RuntimeError:
            logger.debug("detached window raise skipped during focus restore", exc_info=True)
    try:
        window.activateWindow()
    except RuntimeError:
        logger.debug("detached window activateWindow skipped during focus restore", exc_info=True)
    focus_reason = QtCore.Qt.FocusReason.ActiveWindowFocusReason
    focus_targets = []
    tile = window._tile
    if tile is not None:
        video_widget = getattr(tile, "video_widget", None)
        if isinstance(video_widget, QtWidgets.QWidget):
            focus_targets.append(video_widget)
        focus_targets.append(tile)
    try:
        central = window.centralWidget()
    except RuntimeError:
        logger.debug("detached window centralWidget probe skipped during focus restore", exc_info=True)
        return
    if central is not None:
        focus_targets.append(central)
    focus_targets.append(window)
    for target in focus_targets:
        try:
            target.setFocus(focus_reason)
            return
        except RuntimeError:
            try:
                target.setFocus()
                return
            except RuntimeError:
                logger.debug("detached window focus fallback skipped", exc_info=True)


def restore_focus(window) -> None:
    _safe_apply_focus_once(window)
    _schedule_window_callback(window, 0, lambda window_ref=window: _safe_apply_focus_once(window_ref))
    _schedule_window_callback(window, 50, lambda window_ref=window: _safe_apply_focus_once(window_ref))
    _schedule_window_callback(window, 120, lambda window_ref=window: _safe_apply_focus_once(window_ref))


def fit_to_media_size(window) -> bool:
    tile = window._tile
    if tile is None:
        return False
    size_getter = getattr(tile, "target_video_size_for_window_fit", None)
    if not callable(size_getter):
        return False
    media_size = size_getter()
    if media_size is None or media_size.width() <= 0 or media_size.height() <= 0:
        return False
    if window.isFullScreen() or bool(window.windowState() & QtCore.Qt.WindowState.WindowFullScreen):
        window.exit_fullscreen_mode()
    elif bool(window.windowState() & QtCore.Qt.WindowState.WindowMaximized):
        window.showNormal()

    current_window_size = window.size()
    current_video_size = getattr(tile, "video_widget", None).size() if getattr(tile, "video_widget", None) is not None else QtCore.QSize()
    extra_w = max(0, int(current_window_size.width()) - int(current_video_size.width()))
    extra_h = max(0, int(current_window_size.height()) - int(current_video_size.height()))

    screen = window.screen()
    if screen is None:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            screen = app.screenAt(window.frameGeometry().center())
        if screen is None and app is not None:
            screen = app.primaryScreen()
    available = screen.availableGeometry() if screen is not None else QtCore.QRect(0, 0, 1920, 1080)
    display_mode = str(getattr(tile, "display_mode", "fit") or "fit")
    safety_margin = 96 if display_mode == "original" else 48
    max_video_w = max(160, int(available.width()) - extra_w - safety_margin)
    max_video_h = max(120, int(available.height()) - extra_h - safety_margin)

    target_video = QtCore.QSize(int(media_size.width()), int(media_size.height()))
    if target_video.width() > max_video_w or target_video.height() > max_video_h:
        target_video.scale(max_video_w, max_video_h, QtCore.Qt.AspectRatioMode.KeepAspectRatio)

    target_window_size = QtCore.QSize(
        max(window.minimumWidth(), int(target_video.width()) + extra_w),
        max(window.minimumHeight(), int(target_video.height()) + extra_h),
    )
    current_center = window.frameGeometry().center()
    top_left = QtCore.QPoint(
        int(current_center.x() - target_window_size.width() / 2),
        int(current_center.y() - target_window_size.height() / 2),
    )
    target_rect = QtCore.QRect(top_left, target_window_size)
    if target_rect.left() < available.left():
        target_rect.moveLeft(available.left())
    if target_rect.top() < available.top():
        target_rect.moveTop(available.top())
    if target_rect.right() > available.right():
        target_rect.moveRight(available.right())
    if target_rect.bottom() > available.bottom():
        target_rect.moveBottom(available.bottom())
    window.setGeometry(target_rect)
    window.restore_focus()
    return True


def close_event(window, event: QtGui.QCloseEvent) -> None:
    if window._closing_for_app_exit:
        event.accept()
        return
    cancel = getattr(window, "_cancel_deferred_callbacks", None)
    if callable(cancel):
        try:
            cancel()
        except RuntimeError:
            logger.debug("detached window deferred cancel skipped during close", exc_info=True)
    tile = window._tile
    if tile is None:
        event.accept()
        return
    window.redockRequested.emit(tile)
    event.ignore()


def sync_tile_ui_for_window_state(window, force: bool = False) -> None:
    tile = window._tile
    if tile is None:
        return
    overlay_leader_window_mode = bool(window.overlay_active() and window.overlay_is_leader())
    if window.isFullScreen() or bool(window.windowState() & QtCore.Qt.WindowState.WindowFullScreen):
        visible = False if (window._effective_compact_mode() or overlay_leader_window_mode) else bool(window._fullscreen_controls_visible)
    else:
        visible = False if overlay_leader_window_mode else not window._effective_compact_mode()
    if force or bool(getattr(tile, "_controls_requested_visible", True)) != bool(visible):
        try:
            tile.show_controls(bool(visible))
        except RuntimeError:
            logger.warning("detached window control visibility sync failed", exc_info=True)


def queue_fullscreen_hover(window, global_pos: QtCore.QPoint) -> None:
    if not (window.isFullScreen() or bool(window.windowState() & QtCore.Qt.WindowState.WindowFullScreen)):
        return
    window._fullscreen_hover_pending_pos = QtCore.QPoint(global_pos)
    if window._fullscreen_hover_timer.isActive():
        return
    flush_fullscreen_hover(window)
    window._fullscreen_hover_timer.start()


def flush_fullscreen_hover(window) -> None:
    pos = window._fullscreen_hover_pending_pos
    window._fullscreen_hover_pending_pos = None
    if pos is not None:
        update_fullscreen_hover_at(window, pos)


def update_fullscreen_hover_at(window, global_pos: QtCore.QPoint) -> None:
    if not (window.isFullScreen() or bool(window.windowState() & QtCore.Qt.WindowState.WindowFullScreen)):
        return
    tile = window._tile
    if tile is None:
        return
    visible = False if (window._effective_compact_mode() or window.overlay_is_leader()) else True
    window._show_fullscreen_ui_transient(show_controls=visible)
