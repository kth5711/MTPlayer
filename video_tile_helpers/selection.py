from PyQt6 import QtGui, QtWidgets


def _normalized_selection_mode(mode) -> str:
    if isinstance(mode, bool):
        mode = "normal" if mode else "off"
    return str(mode) if mode in {"normal", "delete", "off"} else "off"


def _selection_visuals(tile, mode: str) -> tuple[bool, str, str, str]:
    dark_palette = _palette_is_dark(tile)
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
            "border: 1px solid black;",
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
            "border: 4px solid red;",
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
        "border: 1px solid black;",
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
    is_selected, text, label_style, frame_style = _selection_visuals(tile, normalized)
    tile.is_selected = expected_selected if is_selected == expected_selected else is_selected
    tile.lbl_selected.setText(text)
    tile.lbl_selected.setStyleSheet(label_style)
    tile.setStyleSheet(frame_style)


def set_selection(tile, mode="normal") -> None:
    normalized = _normalized_selection_mode(mode)
    if not hasattr(tile, "selection_mode"):
        tile.selection_mode = "off"
    expected_selected = normalized != "off"
    if getattr(tile, "selection_mode", "off") == normalized and bool(getattr(tile, "is_selected", False)) == expected_selected:
        return
    tile.selection_mode = normalized
    refresh_selection_visuals(tile)
