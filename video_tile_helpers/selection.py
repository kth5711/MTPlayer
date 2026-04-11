from PyQt6 import QtGui, QtWidgets


def _normalized_selection_mode(mode) -> str:
    if isinstance(mode, bool):
        mode = "normal" if mode else "off"
    return str(mode) if mode in {"normal", "delete", "off"} else "off"


def _selection_visuals(tile, mode: str) -> tuple[bool, str, str, str]:
    dark_palette = _palette_is_dark(tile)
    idle_frame_style = "border: none;"
    selected_frame_style = "border: none;"
    delete_frame_style = "border: 4px solid red;"
    if mode == "normal":
        return (
            True,
            "✓",
            (
                "font-size: 13px; font-weight: 700; padding: 0 4px; border-radius: 5px;"
                "color: #1DB954; border: 1px solid #2e2e2e;"
                "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #2b2b2b, stop:1 #1e1e1e);"
                if dark_palette
                else
                "font-size: 13px; font-weight: 700; padding: 0 4px; border-radius: 5px;"
                "color: #2d7a52; border: 1px solid #c9d9cf;"
                "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f5faf7, stop:1 #e5efe8);"
            ),
            selected_frame_style,
        )
    if mode == "delete":
        return (
            True,
            "✓",
            (
                "font-size: 13px; font-weight: 700; padding: 0 4px; border-radius: 5px;"
                "color: #ff5f56; border: 1px solid #5a1f1f; background: #261616;"
                if dark_palette
                else
                "font-size: 13px; font-weight: 700; padding: 0 4px; border-radius: 5px;"
                "color: #b75c55; border: 1px solid #e6c9c7; background: #faf0ef;"
            ),
            delete_frame_style,
        )
    return (
        False,
        "",
        (
            "font-size: 13px; font-weight: 700; color: transparent;"
            "padding: 0 4px; border-radius: 5px; border: 1px solid #242424; background: #1d1d1d;"
            if dark_palette
            else
                "font-size: 13px; font-weight: 700; color: transparent;"
                "padding: 0 4px; border-radius: 5px; border: 1px solid #dde4eb; background: #f3f6f9;"
        ),
        idle_frame_style,
    )


def _palette_is_dark(tile) -> bool:
    app = QtWidgets.QApplication.instance()
    if app is not None:
        try:
            theme = str(app.property("multiPlayTheme") or "").strip().lower()
        except Exception:
            theme = ""
        if theme == "white":
            return False
        if theme == "black":
            return True
        if theme == "system":
            try:
                return int(app.palette().color(QtGui.QPalette.ColorRole.Window).lightness()) < 140
            except Exception:
                pass
    target = getattr(tile, "lbl_selected", None) or tile
    try:
        return int(target.palette().color(QtGui.QPalette.ColorRole.Window).lightness()) < 140
    except Exception:
        return True


def refresh_selection_visuals(tile) -> None:
    normalized = _normalized_selection_mode(getattr(tile, "selection_mode", "off"))
    expected_selected = normalized != "off"
    chrome_visible = bool(getattr(tile, "_ui_chrome_visible", True))
    is_selected, text, label_style, frame_style = _selection_visuals(tile, normalized)
    tile.is_selected = expected_selected if is_selected == expected_selected else is_selected
    tile.lbl_selected.setText(text if is_selected else "")
    tile.lbl_selected.setStyleSheet(label_style)
    _place_selected_badge(tile)
    tile.lbl_selected.setVisible(chrome_visible)
    if not chrome_visible:
        frame_style = "border: none;"
    elif normalized != "delete" and bool(getattr(tile, "_border_visible", True)):
        frame_style = _idle_tile_border_style(tile)
    tile.setStyleSheet(frame_style)
    refresh_border_frame(tile)


def _idle_tile_border_style(tile) -> str:
    return "border: 1px solid #1f2933;" if _palette_is_dark(tile) else "border: 1px solid #d7dee7;"


def refresh_border_frame(tile) -> None:
    frame = getattr(tile, "_border_frame", None)
    if frame is None:
        _place_selected_badge(tile)
        for name in (
            "controls_container",
            "add_button",
            "add_hint_label",
            "lbl_selected",
            "mute_overlay",
            "volume_overlay",
            "seek_overlay",
            "rate_overlay",
            "status_overlay",
        ):
            widget = getattr(tile, name, None)
            if widget is None:
                continue
            try:
                widget.raise_()
            except Exception:
                pass
        return
    rect = tile.rect()
    try:
        frame.setGeometry(rect.adjusted(0, 0, -1, -1))
    except Exception:
        pass
    try:
        frame.setVisible(
            bool(getattr(tile, "_border_visible", True))
            and bool(getattr(tile, "_ui_chrome_visible", True))
        )
    except Exception:
        pass
    try:
        frame.raise_()
    except Exception:
        pass
    _place_selected_badge(tile)
    for name in (
        "controls_container",
        "add_button",
        "add_hint_label",
        "lbl_selected",
        "mute_overlay",
        "volume_overlay",
        "seek_overlay",
        "rate_overlay",
        "status_overlay",
    ):
        widget = getattr(tile, name, None)
        if widget is None:
            continue
        try:
            widget.raise_()
        except Exception:
            pass


def _place_selected_badge(tile) -> None:
    badge = getattr(tile, "lbl_selected", None)
    if badge is None:
        return
    try:
        if badge.parentWidget() is getattr(tile, "control_bar", None):
            badge.setFixedSize(24, 20)
            return
        badge.adjustSize()
        controls = getattr(tile, "controls_container", None)
        controls_height = 0
        if controls is not None and controls.isVisible():
            controls_height = int(controls.height())
        x = 8
        y = max(8, int(tile.height()) - controls_height - int(badge.height()) - 8)
        badge.move(x, y)
    except Exception:
        pass


def set_selection(tile, mode="normal") -> None:
    normalized = _normalized_selection_mode(mode)
    if not hasattr(tile, "selection_mode"):
        tile.selection_mode = "off"
    expected_selected = normalized != "off"
    if getattr(tile, "selection_mode", "off") == normalized and bool(getattr(tile, "is_selected", False)) == expected_selected:
        return
    tile.selection_mode = normalized
    refresh_selection_visuals(tile)
    _update_selection_badge_timer(tile, normalized)


def _update_selection_badge_timer(tile, mode: str) -> None:
    tile._selection_badge_visible = True
    timer = getattr(tile, "_selection_badge_hide_timer", None)
    if timer is not None:
        try:
            timer.stop()
        except Exception:
            pass
    refresh_selection_visuals(tile)


def _selection_badge_targets(tile) -> list:
    mainwin = tile._main_window() if hasattr(tile, "_main_window") else None
    canvas = getattr(mainwin, "canvas", None) if mainwin is not None else None
    if canvas is None:
        return [tile]
    try:
        selected_tiles = [
            candidate
            for candidate in getattr(canvas, "tiles", [])
            if getattr(candidate, "selection_mode", "off") != "off"
        ]
    except Exception:
        selected_tiles = []
    if len(selected_tiles) >= 2:
        return selected_tiles
    return [tile]


def _show_selection_badge_with_timer(tile) -> None:
    timer = getattr(tile, "_selection_badge_hide_timer", None)
    tile._selection_badge_visible = True
    if timer is None:
        refresh_selection_visuals(tile)
        return
    mainwin = tile._main_window() if hasattr(tile, "_main_window") else None
    if _selection_badge_should_persist(mainwin):
        try:
            timer.stop()
        except Exception:
            pass
        refresh_selection_visuals(tile)
        return
    try:
        timer.timeout.disconnect()
    except Exception:
        pass
    timer.timeout.connect(lambda t=tile: _hide_selection_badge(t))
    duration_ms = 1500
    if mainwin is not None and hasattr(mainwin, "current_windowed_ui_auto_hide_ms"):
        try:
            duration_ms = int(mainwin.current_windowed_ui_auto_hide_ms())
        except Exception:
            duration_ms = 1500
    try:
        timer.start(max(250, duration_ms))
    except Exception:
        pass
    refresh_selection_visuals(tile)


def _hide_selection_badge(tile) -> None:
    tile._selection_badge_visible = True
    refresh_selection_visuals(tile)


def _selection_badge_should_persist(mainwin) -> bool:
    if mainwin is None:
        return False
    try:
        mode = str(mainwin.current_ui_visibility_mode())
    except Exception:
        return False
    return mode == "always"
