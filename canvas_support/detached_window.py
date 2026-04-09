import logging
from typing import Any, Dict, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from .detached_window_events import (
    change_event as change_event_impl,
    event_filter as event_filter_impl,
    focus_in_event as focus_in_event_impl,
    move_event as move_event_impl,
    resize_event as resize_event_impl,
    show_event as show_event_impl,
)
from .detached_window_lifecycle import (
    apply_focus_once as apply_focus_once_impl,
    close_event as close_event_impl,
    enter_fullscreen_mode as enter_fullscreen_mode_impl,
    exit_fullscreen_mode as exit_fullscreen_mode_impl,
    fit_to_media_size as fit_to_media_size_impl,
    flush_fullscreen_hover as flush_fullscreen_hover_impl,
    prepare_for_app_close as prepare_for_app_close_impl,
    queue_fullscreen_hover as queue_fullscreen_hover_impl,
    restore_focus as restore_focus_impl,
    sync_tile_ui_for_window_state as sync_tile_ui_for_window_state_impl,
    update_fullscreen_hover_at as update_fullscreen_hover_at_impl,
)
from .detached_window_resize import (
    apply_resize_cursor as apply_resize_cursor_impl,
    cursor_for_resize_edges as cursor_for_resize_edges_impl,
    end_resize as end_resize_impl,
    event_pos_in_window as event_pos_in_window_impl,
    frame_resize_enabled as frame_resize_enabled_impl,
    install_resize_filters as install_resize_filters_impl,
    minimum_resize_size as minimum_resize_size_impl,
    resize_edges_for_pos as resize_edges_for_pos_impl,
    resized_geometry as resized_geometry_impl,
)
from video_tile import VideoTile

logger = logging.getLogger(__name__)


class DetachedTileWindow(QtWidgets.QMainWindow):
    redockRequested = QtCore.pyqtSignal(object)
    overlayGeometryChanged = QtCore.pyqtSignal(object, object)
    overlayRestackRequested = QtCore.pyqtSignal(object)
    _RESIZE_LEFT = 1
    _RESIZE_TOP = 2
    _RESIZE_RIGHT = 4
    _RESIZE_BOTTOM = 8
    _FULLSCREEN_UI_HIDE_MS = 1400

    def __init__(self, tile: VideoTile, *, always_on_top: bool = False, compact_mode: bool = False):
        super().__init__(None)
        self._tile = tile
        self._always_on_top = bool(always_on_top)
        self._compact_mode = bool(compact_mode)
        self._closing_for_app_exit = False
        self._dispose_requested = False
        self._pre_fullscreen_geometry: Optional[QtCore.QRect] = None
        self._pre_fullscreen_maximized = False
        self._resize_margin = 8
        self._resize_edges = 0
        self._resize_active = False
        self._resize_start_global = QtCore.QPoint()
        self._resize_start_geometry = QtCore.QRect()
        self._fullscreen_hover_pending_pos: Optional[QtCore.QPoint] = None
        self._fullscreen_controls_visible = False
        self._overlay_group_id = ""
        self._overlay_order = 0
        self._overlay_is_leader = False
        self._overlay_click_through = False
        self._overlay_force_compact = False
        self._group_title_bar_hidden = False
        self._window_opacity = 1.0
        self._overlay_opacity = 1.0
        self._overlay_audio_mode = "leader"
        self._overlay_restore_tile_muted: Optional[bool] = None
        self._overlay_restore_window_opacity: Optional[float] = None
        self._overlay_restack_token = 0
        self._overlay_geometry_sync_depth = 0
        self._deferred_timers: list[QtCore.QTimer] = []
        self._fullscreen_hover_timer = QtCore.QTimer(self)
        self._fullscreen_hover_timer.setSingleShot(True)
        self._fullscreen_hover_timer.setInterval(40)
        self._fullscreen_hover_timer.timeout.connect(self._flush_fullscreen_hover)
        self._fullscreen_ui_hide_timer = QtCore.QTimer(self)
        self._fullscreen_ui_hide_timer.setSingleShot(True)
        self._fullscreen_ui_hide_timer.setInterval(self._FULLSCREEN_UI_HIDE_MS)
        self._fullscreen_ui_hide_timer.timeout.connect(self._hide_fullscreen_ui)
        self.setMinimumSize(0, 0)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        host = QtWidgets.QWidget(self)
        host.setMinimumSize(0, 0)
        host.setMouseTracking(True)
        host.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        host.installEventFilter(self)
        layout = QtWidgets.QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setCentralWidget(host)
        self.installEventFilter(self)
        self._apply_window_style()
        self.attach_tile(tile)

    def attach_tile(self, tile: VideoTile):
        self._tile = tile
        self._dispose_requested = False
        try:
            tile.setMinimumSize(0, 0)
        except RuntimeError:
            logger.debug("detached window tile minimum size reset skipped", exc_info=True)
        try:
            tile.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        except RuntimeError:
            logger.debug("detached window tile focus policy reset skipped", exc_info=True)
        try:
            if isinstance(getattr(tile, "video_widget", None), QtWidgets.QWidget):
                tile.video_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        except RuntimeError:
            logger.debug("detached window video widget focus policy reset skipped", exc_info=True)
        self._install_resize_filters(tile, True)
        self.centralWidget().layout().addWidget(tile)
        self.refresh_title()

    def take_tile(self) -> Optional[VideoTile]:
        tile = self._tile
        if tile is None:
            return None
        self._cancel_deferred_callbacks()
        self._install_resize_filters(tile, False)
        try:
            self.centralWidget().layout().removeWidget(tile)
        except (AttributeError, RuntimeError):
            logger.debug("detached window removeWidget skipped", exc_info=True)
        self._tile = None
        return tile

    def refresh_title(self):
        tile = self._tile
        if tile is None:
            self.setWindowTitle("Detached Tile")
            return
        text = ""
        try:
            text = tile.title.toolTip() or tile.title.text()
        except (AttributeError, RuntimeError):
            logger.debug("detached window title refresh skipped", exc_info=True)
        self.setWindowTitle(text or "Detached Tile")

    def _apply_window_style(self, *, restore_focus: bool = True):
        was_visible = self.isVisible()
        was_maximized = self.isMaximized()
        was_fullscreen = self.isFullScreen()
        geom = self.geometry()
        flags = QtCore.Qt.WindowType.Window
        if self._effective_compact_mode() or self._group_title_bar_hidden:
            flags |= QtCore.Qt.WindowType.FramelessWindowHint
        if self._always_on_top:
            flags |= QtCore.Qt.WindowType.WindowStaysOnTopHint
        if self._overlay_click_through:
            transparent_flag = getattr(QtCore.Qt.WindowType, "WindowTransparentForInput", None)
            if transparent_flag is not None:
                flags |= transparent_flag
            no_focus_flag = getattr(QtCore.Qt.WindowType, "WindowDoesNotAcceptFocus", None)
            if no_focus_flag is not None:
                flags |= no_focus_flag
        self.setWindowFlags(flags)
        if was_fullscreen:
            self.showFullScreen()
        elif was_maximized:
            self.showMaximized()
        elif was_visible:
            self.showNormal()
            self.setGeometry(geom)
        else:
            self.setGeometry(geom)
        if self._tile is not None:
            try:
                self._tile.show()
            except RuntimeError:
                logger.warning("detached window tile show failed during style apply", exc_info=True)
            self._schedule_deferred_callback(0, self._tile.bind_hwnd)
        self._apply_window_opacity()
        if restore_focus and was_visible and not self._overlay_click_through:
            self.restore_focus()

    def _show_cursor(self):
        try:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        except RuntimeError:
            logger.debug("detached window cursor restore skipped", exc_info=True)

    def _restart_fullscreen_ui_hide_timer(self):
        try:
            self._fullscreen_ui_hide_timer.start()
        except RuntimeError:
            logger.debug("detached window fullscreen ui hide timer restart skipped", exc_info=True)

    def _show_fullscreen_ui_transient(self, *, show_controls: bool):
        if not (self.isFullScreen() or bool(self.windowState() & QtCore.Qt.WindowState.WindowFullScreen)):
            return
        self._show_cursor()
        if bool(show_controls) != bool(self._fullscreen_controls_visible):
            self._fullscreen_controls_visible = bool(show_controls)
            self._sync_tile_ui_for_window_state(force=True)
        self._restart_fullscreen_ui_hide_timer()

    def _hide_fullscreen_ui(self):
        if not (self.isFullScreen() or bool(self.windowState() & QtCore.Qt.WindowState.WindowFullScreen)):
            return
        self._fullscreen_controls_visible = False
        self._sync_tile_ui_for_window_state(force=True)
        try:
            self.setCursor(QtCore.Qt.CursorShape.BlankCursor)
        except RuntimeError:
            logger.debug("detached window cursor hide skipped", exc_info=True)

    def set_always_on_top(self, enabled: bool):
        self._always_on_top = bool(enabled)
        self._apply_window_style()

    def set_compact_mode(self, enabled: bool):
        self._compact_mode = bool(enabled)
        if not self._effective_compact_mode():
            self._end_resize()
        self._apply_window_style()
        self._sync_tile_ui_for_window_state()
        if not self._overlay_click_through:
            self.restore_focus()

    def set_group_title_bar_hidden(self, enabled: bool):
        enabled = bool(enabled)
        if self._group_title_bar_hidden == enabled:
            return
        self._group_title_bar_hidden = enabled
        self._apply_window_style(restore_focus=False)

    def _effective_compact_mode(self) -> bool:
        return False if (self.overlay_active() and self.overlay_is_leader()) else bool(self._compact_mode or self._overlay_force_compact)

    def overlay_active(self) -> bool:
        return bool(self._overlay_group_id)

    def overlay_group_id(self) -> str:
        return str(self._overlay_group_id or "")

    def overlay_is_leader(self) -> bool:
        return bool(self.overlay_active() and self._overlay_is_leader)

    def overlay_order(self) -> int:
        return int(self._overlay_order)

    def overlay_opacity(self) -> float:
        try:
            return max(0.01, min(1.0, float(self._overlay_opacity)))
        except (TypeError, ValueError):
            return 1.0

    def overlay_audio_mode(self) -> str:
        return "preserve" if str(getattr(self, "_overlay_audio_mode", "leader") or "").strip().lower() == "preserve" else "leader"

    def set_overlay_audio_mode(self, mode: str):
        self._overlay_audio_mode = "preserve" if str(mode or "").strip().lower() == "preserve" else "leader"

    def window_opacity_value(self) -> float:
        try:
            if self.overlay_active():
                return self.overlay_opacity()
            return max(0.01, min(1.0, float(self._window_opacity)))
        except (TypeError, ValueError):
            return 1.0

    def overlay_state_payload(self) -> Optional[Dict[str, Any]]:
        if not self.overlay_active():
            return None
        return {
            "group_id": self.overlay_group_id(),
            "order": int(self._overlay_order),
            "leader": bool(self._overlay_is_leader),
            "opacity": float(self.window_opacity_value()),
            "audio_mode": self.overlay_audio_mode(),
        }

    def _apply_window_opacity(self):
        try:
            self.setWindowOpacity(self.window_opacity_value())
        except RuntimeError:
            logger.debug("detached window opacity update skipped", exc_info=True)

    def set_window_opacity_value(self, opacity: float, *, update_tile: bool = True):
        try:
            normalized = max(0.01, min(1.0, float(opacity)))
        except (TypeError, ValueError):
            normalized = 1.0
        if self.overlay_active():
            self._overlay_opacity = normalized
        else:
            self._window_opacity = normalized
        persist_tile_opacity = bool(update_tile and self._tile is not None and not self.overlay_active())
        if persist_tile_opacity:
            try:
                self._tile.detached_window_opacity = float(self._window_opacity)
            except Exception:
                logger.debug("detached window opacity sync to tile skipped", exc_info=True)
        self._apply_window_opacity()

    def set_overlay_state(self, group_id: Optional[str], *, order: int = 0, leader: bool = False, opacity: Optional[float] = None, emit_sync: bool = True, restore_focus: bool = True):
        normalized_group_id = str(group_id or "").strip()
        self._overlay_group_id = normalized_group_id
        self._overlay_order = max(0, int(order))
        self._overlay_is_leader = bool(normalized_group_id and leader)
        self._overlay_click_through = bool(normalized_group_id) and not self._overlay_is_leader
        self._overlay_force_compact = bool(normalized_group_id) and not self._overlay_is_leader
        if opacity is not None:
            self.set_window_opacity_value(opacity)
        self._apply_window_style(restore_focus=restore_focus)
        self._sync_tile_ui_for_window_state(force=True)
        if emit_sync and self._overlay_is_leader:
            self.overlayGeometryChanged.emit(self._tile, QtCore.QRect(self.geometry()))
            self.overlayRestackRequested.emit(self._tile)

    def _request_overlay_restack(self, *, immediate: bool = False, delays: tuple[int, ...] = (0, 60)):
        if not self.overlay_is_leader():
            return
        self._overlay_restack_token += 1
        token = int(self._overlay_restack_token)
        if immediate:
            self.overlayRestackRequested.emit(self._tile)
        for delay_ms in delays:
            self._schedule_deferred_callback(
                delay_ms,
                lambda tile=self._tile, expected=token, self_ref=self: self_ref._emit_overlay_restack_if_current(tile, expected),
            )

    def _emit_overlay_restack_if_current(self, tile: Optional[VideoTile], expected_token: int):
        if self._dispose_requested:
            return
        if tile is not None and int(getattr(self, "_overlay_restack_token", 0)) == int(expected_token) and self.overlay_is_leader():
            self.overlayRestackRequested.emit(tile)

    def refresh_media_layout(self, *, force_bind: bool = False, delays: tuple[int, ...] = (0, 40, 120)):
        self._refresh_media_layout_step(force_bind=force_bind)
        for delay_ms in tuple(int(delay) for delay in delays if int(delay) > 0):
            self._schedule_deferred_callback(
                delay_ms,
                lambda self_ref=self, force_bind=force_bind: self_ref._refresh_media_layout_step(force_bind=force_bind),
            )

    def _refresh_media_layout_step(self, *, force_bind: bool = False):
        tile = self._tile
        if tile is None or self._dispose_requested:
            return
        try:
            host = self.centralWidget()
        except RuntimeError:
            logger.debug("detached window central widget probe skipped", exc_info=True)
            host = None
        if host is not None:
            try:
                layout = host.layout()
                if layout is not None:
                    layout.activate()
            except RuntimeError:
                logger.debug("detached window host layout activate skipped", exc_info=True)
            try:
                target_size = host.contentsRect().size()
            except RuntimeError:
                logger.debug("detached window host contentsRect probe skipped", exc_info=True)
                target_size = QtCore.QSize()
            if target_size.width() > 0 and target_size.height() > 0:
                try:
                    tile.updateGeometry()
                except Exception:
                    logger.debug("detached window tile updateGeometry skipped", exc_info=True)
                try:
                    if tile.size() != target_size:
                        tile.resize(target_size)
                except Exception:
                    logger.debug("detached window tile resize sync skipped", exc_info=True)
        try:
            tile._refresh_image_display()
        except Exception:
            logger.debug("detached window image refresh skipped", exc_info=True)
        try:
            tile._apply_display_mode()
        except Exception:
            logger.debug("detached window display mode refresh skipped", exc_info=True)
        binder = getattr(tile, "bind_hwnd", None)
        if callable(binder):
            try:
                binder(force=force_bind)
            except Exception:
                logger.debug("detached window bind_hwnd refresh skipped", exc_info=True)

    def _cancel_deferred_callbacks(self):
        self._dispose_requested = True
        timers = list(getattr(self, "_deferred_timers", []))
        self._deferred_timers.clear()
        for timer in timers:
            try:
                timer.stop()
            except RuntimeError:
                logger.debug("detached window deferred timer stop skipped", exc_info=True)
            try:
                timer.deleteLater()
            except RuntimeError:
                logger.debug("detached window deferred timer deleteLater skipped", exc_info=True)

    def _schedule_deferred_callback(self, delay_ms: int, callback) -> bool:
        if self._dispose_requested:
            return False
        try:
            timer = QtCore.QTimer(self)
        except RuntimeError:
            logger.debug("detached window deferred timer creation skipped", exc_info=True)
            return False
        timer.setSingleShot(True)
        self._deferred_timers.append(timer)

        def _run():
            try:
                if timer in self._deferred_timers:
                    self._deferred_timers.remove(timer)
            except RuntimeError:
                logger.debug("detached window deferred timer removal skipped", exc_info=True)
            if self._dispose_requested:
                return
            try:
                callback()
            except RuntimeError:
                logger.debug("detached window deferred callback skipped", exc_info=True)
            finally:
                try:
                    timer.deleteLater()
                except RuntimeError:
                    logger.debug("detached window deferred timer final deleteLater skipped", exc_info=True)

        timer.timeout.connect(_run)
        timer.start(max(0, int(delay_ms)))
        return True

    def _set_geometry_from_overlay_sync(self, geometry: QtCore.QRect):
        self._overlay_geometry_sync_depth += 1
        try:
            self.setGeometry(QtCore.QRect(geometry))
        finally:
            self._overlay_geometry_sync_depth = max(0, int(self._overlay_geometry_sync_depth) - 1)

    def _run_overlay_sync_action(self, action):
        self._overlay_geometry_sync_depth += 1
        try:
            action()
        finally:
            self._overlay_geometry_sync_depth = max(0, int(self._overlay_geometry_sync_depth) - 1)

    def clear_overlay_state(self, *, emit_sync: bool = False, restore_focus: bool = True):
        restore_opacity = self._overlay_restore_window_opacity
        self._overlay_restore_window_opacity = None
        if restore_opacity is not None:
            try:
                self._window_opacity = max(0.01, min(1.0, float(restore_opacity)))
            except (TypeError, ValueError):
                self._window_opacity = 1.0
        self.set_overlay_state(None, emit_sync=emit_sync, restore_focus=restore_focus)
        if restore_opacity is not None:
            self.set_window_opacity_value(float(restore_opacity))

    def prepare_for_app_close(self):
        prepare_for_app_close_impl(self)

    def enter_fullscreen_mode(self):
        enter_fullscreen_mode_impl(self)

    def exit_fullscreen_mode(self):
        exit_fullscreen_mode_impl(self)

    def _apply_focus_once(self):
        apply_focus_once_impl(self)

    def restore_focus(self):
        restore_focus_impl(self)

    def fit_to_media_size(self) -> bool:
        return fit_to_media_size_impl(self)

    def closeEvent(self, event: QtGui.QCloseEvent):
        close_event_impl(self, event)

    def _sync_tile_ui_for_window_state(self, force: bool = False):
        sync_tile_ui_for_window_state_impl(self, force=force)

    def _queue_fullscreen_hover(self, global_pos: QtCore.QPoint):
        queue_fullscreen_hover_impl(self, global_pos)

    def _flush_fullscreen_hover(self):
        flush_fullscreen_hover_impl(self)

    def _update_fullscreen_hover_at(self, global_pos: QtCore.QPoint):
        update_fullscreen_hover_at_impl(self, global_pos)

    def _install_resize_filters(self, tile: Optional[VideoTile], enable: bool):
        install_resize_filters_impl(self, tile, enable)

    def _frame_resize_enabled(self) -> bool:
        return frame_resize_enabled_impl(self)

    def _event_pos_in_window(self, watched, event: QtGui.QMouseEvent):
        return event_pos_in_window_impl(self, watched, event)

    def _resize_edges_for_pos(self, pos: QtCore.QPoint) -> int:
        return resize_edges_for_pos_impl(self, pos)

    def _cursor_for_resize_edges(self, edges: int) -> QtCore.Qt.CursorShape:
        return cursor_for_resize_edges_impl(self, edges)

    def _apply_resize_cursor(self, edges: int):
        apply_resize_cursor_impl(self, edges)

    def _end_resize(self):
        end_resize_impl(self)

    def _minimum_resize_size(self) -> QtCore.QSize:
        return minimum_resize_size_impl(self)

    def minimumSizeHint(self) -> QtCore.QSize:
        return self._minimum_resize_size()

    def _resized_geometry(self, delta: QtCore.QPoint) -> QtCore.QRect:
        return resized_geometry_impl(self, delta)

    def eventFilter(self, watched, event):
        return event_filter_impl(self, watched, event)

    def moveEvent(self, event: QtGui.QMoveEvent):
        move_event_impl(self, event)

    def resizeEvent(self, event: QtGui.QResizeEvent):
        resize_event_impl(self, event)

    def changeEvent(self, event: QtCore.QEvent):
        change_event_impl(self, event)

    def focusInEvent(self, event: QtGui.QFocusEvent):
        focus_in_event_impl(self, event)

    def showEvent(self, event: QtGui.QShowEvent):
        show_event_impl(self, event)
