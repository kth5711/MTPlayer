import logging
from typing import Dict, List, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from .interaction_shortcuts import (
    apply_hotkey_action,
    current_shortcuts_or_defaults,
    event_to_shortcut_token,
    handle_seek_key_event,
    handle_shortcut_override_event,
    hotkey_action_for_event,
    normalize_shortcut_mapping,
    normalize_shortcut_token,
    rebind_shortcuts,
    rebuild_seek_hotkeys,
    rebuild_tile_hotkeys,
    register_tile_hotkey,
    seek_step_for_event,
    select_tile_by_index,
    set_action_shortcut,
    should_bypass_global_key_handling,
)
from .interaction_drag import (
    clear_tile_drag_state,
    finish_tile_drag,
    handle_drag_mouse_move,
    handle_drag_mouse_release,
    handle_main_mouse_press,
    move_tile_drag_preview,
    on_tile_drag_preview_ready,
    show_tile_drag_preview,
    start_tile_drag_candidate,
    tile_from_event_source,
    update_tile_drag,
)
from .interaction_ui_state import (
    hide_cursor,
    hide_ui,
    show_cursor,
    show_ui,
    sync_windowed_ui_from_compact_mode,
)

logger = logging.getLogger(__name__)


def cycle_repeat_mode_all_or_selected(main):
    targets = main.canvas.get_controlled_tiles(require_selection=False)
    if not targets:
        return
    for tile in targets:
        tile.cycle_repeat_mode()


def cycle_display_mode_all_or_selected(main):
    targets = main.canvas.get_controlled_tiles(require_selection=False)
    if not targets:
        return
    for tile in targets:
        tile.cycle_display_mode()


def toggle_select_all_tiles(main):
    tiles = list(getattr(main.canvas, "tiles", []))
    if not tiles:
        return
    normal_selected = [
        tile
        for tile in tiles
        if bool(getattr(tile, "is_selected", False)) and getattr(tile, "selection_mode", "") == "normal"
    ]
    select_all = len(normal_selected) != len(tiles)
    if select_all:
        for tile in tiles:
            tile.set_selection("normal")
        main.statusBar().showMessage(f"타일 전체 선택: {len(tiles)}개", 1500)
        return
    for tile in tiles:
        tile.set_selection("off")
    main.statusBar().showMessage("타일 선택 해제", 1500)


def vol_step(main, direction: int):
    selected_tiles = main.canvas.get_selected_tiles()
    spotlight_tile = main.canvas.spotlight_tile() if hasattr(main.canvas, "spotlight_tile") else None
    main.canvas.apply_to_controlled_tiles(lambda tile: tile.adjust_volume_step(direction))
    if not selected_tiles and spotlight_tile is None:
        mv = main.sld_master.value() + (5 * direction)
        main.sld_master.setValue(max(0, min(100, mv)))


def toggle_mute(main):
    selected_tiles = main.canvas.get_selected_tiles()
    spotlight_tile = main.canvas.spotlight_tile() if hasattr(main.canvas, "spotlight_tile") else None
    targets = selected_tiles if selected_tiles else ([spotlight_tile] if spotlight_tile is not None else [])
    if targets:
        all_muted = all(getattr(tile, "tile_muted", False) for tile in targets)
        for tile in targets:
            try:
                tile.set_tile_muted(not all_muted)
            except RuntimeError:
                logger.warning("tile mute toggle failed", exc_info=True)
        return

    if main.sld_master.value() == 0:
        main.sld_master.setValue(getattr(main, "_last_master_before_mute", 100) or 100)
    else:
        main._last_master_before_mute = main.sld_master.value()
        main.sld_master.setValue(0)


def toggle_fullscreen(main):
    try:
        if bool(getattr(main, "is_opacity_mode_active", lambda: False)()):
            if main._is_fullscreen():
                main.exit_fullscreen()
                return
            main._clear_tile_drag_state()
            main._fullscreen_ui_mode = None
            main._fullscreen_ui_tile = None
            main.was_maximized = bool(main.windowState() & QtCore.Qt.WindowState.WindowMaximized)
            main.normal_geometry = main.geometry()
            main.showFullScreen()
            main._show_ui()
            main._restore_window_focus()
            try:
                main.cursor_hide_timer.start()
            except RuntimeError:
                logger.debug("cursor hide timer start skipped after opacity-mode fullscreen enter", exc_info=True)
            return
    except RuntimeError:
        logger.warning("opacity dock fullscreen toggle failed", exc_info=True)
    detached_window = main._detached_window_for_fullscreen_action()
    if detached_window is not None:
        try:
            if detached_window.isFullScreen() or bool(
                detached_window.windowState() & QtCore.Qt.WindowState.WindowFullScreen
            ):
                detached_window.exit_fullscreen_mode()
            else:
                main._clear_tile_drag_state()
                detached_window.enter_fullscreen_mode()
            return
        except RuntimeError:
            logger.warning("detached window fullscreen toggle failed", exc_info=True)
    if bool(main.windowState() & QtCore.Qt.WindowState.WindowFullScreen) or main.isFullScreen():
        main.exit_fullscreen()
        return
    main._clear_tile_drag_state()
    if not main.keep_detached_tiles_for_focus_modes():
        main.canvas.redock_all_detached()
    main._fullscreen_ui_mode = None
    main._fullscreen_ui_tile = None
    main.was_maximized = bool(main.windowState() & QtCore.Qt.WindowState.WindowMaximized)
    main.normal_geometry = main.geometry()
    main.showFullScreen()
    main._show_ui()
    main._restore_window_focus()
    try:
        main.cursor_hide_timer.start()
    except RuntimeError:
        logger.debug("cursor hide timer start skipped after fullscreen enter", exc_info=True)


def restore_window_focus(main):
    def _apply_focus():
        try:
            main.raise_()
        except RuntimeError:
            logger.debug("main window raise skipped during focus restore", exc_info=True)
        try:
            main.activateWindow()
        except RuntimeError:
            logger.debug("main window activateWindow skipped during focus restore", exc_info=True)
        try:
            main.setFocus(QtCore.Qt.FocusReason.ActiveWindowFocusReason)
        except RuntimeError:
            try:
                main.setFocus()
            except RuntimeError:
                logger.debug("main window focus fallback skipped", exc_info=True)

    _apply_focus()
    QtCore.QTimer.singleShot(0, _apply_focus)
    QtCore.QTimer.singleShot(50, _apply_focus)


def capture_managed_focus_window(main):
    try:
        active = QtWidgets.QApplication.activeWindow()
        if main.canvas.is_managed_window(active):
            return active
    except RuntimeError:
        logger.debug("active managed window probe failed", exc_info=True)
    try:
        focus_widget = QtWidgets.QApplication.focusWidget()
        top = focus_widget.window() if focus_widget is not None else None
        if main.canvas.is_managed_window(top):
            return top
    except RuntimeError:
        logger.debug("focused managed window probe failed", exc_info=True)
    try:
        return main.canvas.active_detached_window()
    except RuntimeError:
        logger.debug("active detached window probe failed", exc_info=True)
        return None


def restore_managed_window_focus(main, preferred=None):
    target = preferred
    if target is None:
        target = main._capture_managed_focus_window()
    if target is None or target is main:
        main._restore_window_focus()
        return
    restore = getattr(target, "restore_focus", None)
    if callable(restore):
        try:
            restore()
            return
        except RuntimeError:
            logger.warning("managed window restore_focus failed", exc_info=True)
    try:
        target.raise_()
    except RuntimeError:
        logger.debug("managed window raise skipped during focus restore", exc_info=True)
    try:
        target.activateWindow()
    except RuntimeError:
        logger.debug("managed window activateWindow skipped during focus restore", exc_info=True)


def keep_detached_tiles_for_focus_modes(main) -> bool:
    try:
        return bool(main.keep_detached_focus_mode_action.isChecked())
    except (AttributeError, RuntimeError):
        logger.debug("keep_detached_focus_mode_action probe failed", exc_info=True)
        return False


def detached_window_for_fullscreen_action(main):
    if not main.keep_detached_tiles_for_focus_modes():
        return None
    try:
        active = getattr(main.canvas, "active_detached_window", lambda: None)()
        if active is not None:
            return active
    except RuntimeError:
        logger.debug("active detached window lookup failed for fullscreen action", exc_info=True)
    return None


def is_main_window_active(main) -> bool:
    active = QtWidgets.QApplication.activeWindow()
    return active is main or bool(getattr(main.canvas, "is_managed_window", lambda _w: False)(active))


def focused_text_input_widget(main):
    try:
        widget = QtWidgets.QApplication.focusWidget()
        if widget is None:
            return None
        if isinstance(
            widget,
            (
                QtWidgets.QLineEdit,
                QtWidgets.QTextEdit,
                QtWidgets.QPlainTextEdit,
                QtWidgets.QAbstractSpinBox,
            ),
        ):
            return widget
        if isinstance(widget, QtWidgets.QComboBox) and widget.isEditable():
            return widget
    except RuntimeError:
        logger.debug("focused text input probe failed", exc_info=True)
        return None
    return None


def _set_bookmark_marker_select_mode(main, active: bool) -> None:
    main._bookmark_marker_select_mode = bool(active)
    for tile in list(getattr(getattr(main, "canvas", None), "tiles", []) or []):
        try:
            if hasattr(tile, "_sync_bookmark_marker_select_mode_from_cursor"):
                tile._sync_bookmark_marker_select_mode_from_cursor()
        except RuntimeError:
            logger.debug("bookmark marker select mode sync failed", exc_info=True)


def handle_key_press_event(main, event: QtGui.QKeyEvent) -> bool:
    try:
        if main._should_bypass_global_key_handling():
            return False
        if int(event.key()) == int(QtCore.Qt.Key.Key_S):
            if not bool(event.isAutoRepeat()):
                _set_bookmark_marker_select_mode(main, True)
            return False
        if int(event.key()) == int(QtCore.Qt.Key.Key_Escape):
            main._handle_escape()
            return True
        if main._is_main_window_active():
            if main._handle_seek_key_event(event):
                return True
            action = main._hotkey_action_for_event(event)
            if action is not None and main._apply_hotkey_action(action):
                return True
    except RuntimeError:
        logger.warning("key press handling failed", exc_info=True)
        return False
    return False


def handle_key_release_event(main, event: QtGui.QKeyEvent) -> bool:
    try:
        if int(event.key()) == int(QtCore.Qt.Key.Key_S) and not bool(event.isAutoRepeat()):
            _set_bookmark_marker_select_mode(main, False)
    except RuntimeError:
        logger.warning("key release handling failed", exc_info=True)
    return False


def fullscreen_hover_tile_at_global(main, pos: QtCore.QPoint):
    hover_tile = None
    try:
        sp_idx = getattr(main.canvas, "spotlight_index", None)
        if sp_idx is not None and 0 <= sp_idx < len(main.canvas.tiles):
            tile = main.canvas.tiles[sp_idx]
            rect = tile.rect()
            grect = QtCore.QRect(tile.mapToGlobal(rect.topLeft()), tile.mapToGlobal(rect.bottomRight()))
            if grect.contains(pos):
                hover_tile = tile
        else:
            for tile in main.canvas.tiles:
                rect = tile.rect()
                grect = QtCore.QRect(tile.mapToGlobal(rect.topLeft()), tile.mapToGlobal(rect.bottomRight()))
                if grect.contains(pos):
                    hover_tile = tile
                    break
    except RuntimeError:
        logger.debug("fullscreen hover tile hit-test failed", exc_info=True)
        hover_tile = None
    return hover_tile


def queue_fullscreen_hover(main, pos: QtCore.QPoint):
    if not main._is_fullscreen():
        return
    main._fullscreen_hover_pending_pos = QtCore.QPoint(pos)
    if main._fullscreen_hover_timer.isActive():
        return
    main._flush_fullscreen_hover()
    main._fullscreen_hover_timer.start()


def flush_fullscreen_hover(main):
    pos = main._fullscreen_hover_pending_pos
    main._fullscreen_hover_pending_pos = None
    if pos is None or not main._is_fullscreen():
        return
    main._handle_fullscreen_hover_at(pos)


def refresh_fullscreen_hover_from_cursor(main):
    if not main._is_fullscreen():
        return
    try:
        pos = QtGui.QCursor.pos()
    except RuntimeError:
        logger.debug("cursor position probe failed for fullscreen hover refresh", exc_info=True)
        return
    try:
        win_geom = main.frameGeometry()
    except RuntimeError:
        logger.debug("frameGeometry probe failed for fullscreen hover refresh", exc_info=True)
        win_geom = main.geometry()
    if not win_geom.contains(pos):
        main._apply_fullscreen_ui_mode("hidden")
        try:
            main.cursor_hide_timer.start()
        except RuntimeError:
            logger.debug("cursor hide timer start skipped while hiding fullscreen UI", exc_info=True)
        return
    main._fullscreen_hover_pending_pos = QtCore.QPoint(pos)
    main._flush_fullscreen_hover_preserving_hidden_cursor()


def flush_fullscreen_hover_preserving_hidden_cursor(main):
    pos = main._fullscreen_hover_pending_pos
    main._fullscreen_hover_pending_pos = None
    if pos is None or not main._is_fullscreen():
        return
    main._handle_fullscreen_hover_at(pos, preserve_hidden_cursor=True)


def schedule_fullscreen_hover_refresh_from_cursor(main):
    if not main._is_fullscreen():
        return
    main._refresh_fullscreen_hover_from_cursor()
    QtCore.QTimer.singleShot(0, main._refresh_fullscreen_hover_from_cursor)
    QtCore.QTimer.singleShot(50, main._refresh_fullscreen_hover_from_cursor)
    QtCore.QTimer.singleShot(120, main._refresh_fullscreen_hover_from_cursor)


def handle_fullscreen_hover_at(
    main, pos: QtCore.QPoint, *, preserve_hidden_cursor: bool = False
) -> bool:
    if not main._is_fullscreen():
        return False
    cursor_was_hidden = False
    if preserve_hidden_cursor:
        try:
            cursor_was_hidden = main.cursor().shape() == QtCore.Qt.CursorShape.BlankCursor
        except RuntimeError:
            logger.debug("cursor hidden-state probe failed", exc_info=True)
            cursor_was_hidden = False
    hover_tile = main._fullscreen_hover_tile_at_global(pos)

    desired_mode = "hidden"
    desired_tile = None
    if hover_tile is not None and not main._is_compact_mode():
        try:
            local = hover_tile.mapFromGlobal(pos)
            height = hover_tile.rect().height()
            if local.y() >= (height - 80):
                desired_mode = "tile"
                desired_tile = hover_tile
        except RuntimeError:
            logger.debug("fullscreen hover tile local position probe failed", exc_info=True)

    if desired_mode != "tile":
        y = pos.y()
        win_geom = main.geometry()
        if y <= win_geom.top() + 100:
            desired_mode = "top"
        else:
            try:
                main.cursor_hide_timer.start()
            except RuntimeError:
                logger.debug("cursor hide timer start skipped in fullscreen hover", exc_info=True)
            desired_mode = "hidden"

    main._apply_fullscreen_ui_mode(desired_mode, desired_tile)
    if preserve_hidden_cursor and cursor_was_hidden and desired_mode == "hidden":
        try:
            main.cursor_hide_timer.start()
        except RuntimeError:
            logger.debug("cursor hide timer restart skipped while preserving hidden cursor", exc_info=True)
        return False
    main._show_cursor()
    return False


def event_filter(main, obj, event):
    et = event.type()
    if et == QtCore.QEvent.Type.ApplicationDeactivate:
        _set_bookmark_marker_select_mode(main, False)
    if et == QtCore.QEvent.Type.MouseMove and main._handle_drag_mouse_move(event):
        return True
    if et == QtCore.QEvent.Type.MouseButtonRelease and main._handle_drag_mouse_release(event):
        return True
    if et == QtCore.QEvent.Type.MouseButtonPress and main._handle_main_mouse_press(obj, event):
        return True
    if et == QtCore.QEvent.Type.ShortcutOverride and main._handle_shortcut_override_event(event):
        return True
    if et == QtCore.QEvent.Type.KeyPress and main._handle_key_press_event(event):
        return True
    if et == QtCore.QEvent.Type.KeyRelease and main._handle_key_release_event(event):
        return True
    if et == QtCore.QEvent.Type.MouseMove:
        try:
            main._queue_fullscreen_hover(event.globalPosition().toPoint())
        except RuntimeError:
            logger.debug("queue_fullscreen_hover skipped from eventFilter", exc_info=True)
    return super(type(main), main).eventFilter(obj, event)


def show_top_ui(main, visible: bool):
    try:
        main.menuBar().setVisible(visible)
        for toolbar in main.findChildren(QtWidgets.QToolBar):
            toolbar.setVisible(visible)
        status_bar = main.statusBar() if hasattr(main, "statusBar") else None
        if status_bar is not None:
            status_bar.setVisible(visible)
    except RuntimeError:
        logger.debug("top UI visibility update skipped", exc_info=True)


def show_all_tile_controls(main, visible: bool):
    try:
        if main._is_compact_mode():
            visible = False
        for tile in main.canvas.tiles:
            tile.show_controls(visible)
    except RuntimeError:
        logger.debug("tile control visibility update skipped", exc_info=True)


def apply_fullscreen_ui_mode(main, mode: str, tile=None):
    if mode == main._fullscreen_ui_mode:
        if mode != "tile" or tile is main._fullscreen_ui_tile:
            return

    if mode == "tile":
        main._show_tile_ui(tile)
        main._fullscreen_ui_mode = "tile"
        main._fullscreen_ui_tile = tile
        return

    if mode == "top":
        main._show_top_ui(True)
        main._show_all_tile_controls(False)
        main._fullscreen_ui_mode = "top"
        main._fullscreen_ui_tile = None
        return

    main._show_top_ui(False)
    main._show_all_tile_controls(False)
    main._fullscreen_ui_mode = "hidden"
    main._fullscreen_ui_tile = None


def key_press_event(main, event: QtGui.QKeyEvent):
    key = event.key()
    if key == QtCore.Qt.Key.Key_Escape:
        main._handle_escape()
        event.accept()
        return

    if main._handle_seek_key_event(event):
        event.accept()
        return

    super(type(main), main).keyPressEvent(event)


def exit_fullscreen(main):
    if not main._is_fullscreen():
        return
    opacity_mode_active = False
    try:
        opacity_mode_active = bool(getattr(main, "is_opacity_mode_active", lambda: False)())
    except RuntimeError:
        logger.debug("opacity mode probe failed on fullscreen exit", exc_info=True)
    try:
        main.cursor_hide_timer.stop()
    except RuntimeError:
        logger.debug("cursor hide timer stop skipped on fullscreen exit", exc_info=True)
    try:
        main._fullscreen_hover_timer.stop()
    except RuntimeError:
        logger.debug("fullscreen hover timer stop skipped on fullscreen exit", exc_info=True)
    main._fullscreen_hover_pending_pos = None
    main.setUpdatesEnabled(False)
    if getattr(main, "was_maximized", False):
        target_state = main.windowState()
        target_state &= ~QtCore.Qt.WindowState.WindowFullScreen
        target_state &= ~QtCore.Qt.WindowState.WindowMaximized
        main.setWindowState(target_state)
        if getattr(main, "normal_geometry", None):
            main.setGeometry(main.normal_geometry)
        target_state = main.windowState()
        target_state |= QtCore.Qt.WindowState.WindowMaximized
        main.setWindowState(target_state)
        main.show()
    else:
        target_state = main.windowState()
        target_state &= ~QtCore.Qt.WindowState.WindowFullScreen
        target_state &= ~QtCore.Qt.WindowState.WindowMaximized
        main.setWindowState(target_state)
        if getattr(main, "normal_geometry", None):
            main.setGeometry(main.normal_geometry)
        main.showNormal()
    try:
        if opacity_mode_active:
            pass
        elif not getattr(main, "compact_action", None) or not main.compact_action.isChecked():
            main._show_ui()
        else:
            main._show_top_ui(False)
            main._show_all_tile_controls(False)
        main._fullscreen_ui_mode = None
        main._fullscreen_ui_tile = None
        main._show_cursor()
        main._restore_window_focus()
    except RuntimeError:
        logger.warning("fullscreen exit UI restore failed", exc_info=True)
    main.setUpdatesEnabled(True)
    if opacity_mode_active:
        def _restore_opacity_mode_ui_once():
            try:
                if not bool(getattr(main, "is_opacity_mode_active", lambda: False)()):
                    return
                main._set_opacity_mode_chrome_visible(True)
                main._sync_opacity_mode_button_state()
                main._sync_opacity_mode_corner_controls()
                active = getattr(main, "active_opacity_mode_widget", lambda: None)()
                if active is not None:
                    schedule_sync = getattr(active, "schedule_sync_from_canvas_state", None)
                    if callable(schedule_sync):
                        schedule_sync(80)
                    else:
                        active.sync_from_canvas_state()
                    active._show_overlay_transient()
                main._show_cursor()
                main._restore_window_focus()
            except RuntimeError:
                logger.debug("opacity mode UI restore skipped after fullscreen exit", exc_info=True)

        QtCore.QTimer.singleShot(0, _restore_opacity_mode_ui_once)
        QtCore.QTimer.singleShot(60, _restore_opacity_mode_ui_once)
