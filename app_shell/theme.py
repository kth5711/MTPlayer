from PyQt6 import QtGui, QtWidgets


SUPPORTED_UI_THEMES = ("system", "white", "black")

_SYSTEM_STYLE_NAME: str | None = None
_SYSTEM_PALETTE: QtGui.QPalette | None = None
_THEME_LABELS = {
    "system": "시스템",
    "white": "화이트",
    "black": "블랙",
}


def normalize_ui_theme(value) -> str:
    theme = str(value or "").strip().lower()
    if theme not in SUPPORTED_UI_THEMES:
        return "black"
    return theme


def theme_label_key(theme: str) -> str:
    return _THEME_LABELS.get(normalize_ui_theme(theme), "블랙")


def remember_system_theme(app: QtWidgets.QApplication) -> None:
    global _SYSTEM_STYLE_NAME, _SYSTEM_PALETTE
    if _SYSTEM_STYLE_NAME is None:
        _SYSTEM_STYLE_NAME = str(app.style().objectName() or "")
    if _SYSTEM_PALETTE is None:
        _SYSTEM_PALETTE = QtGui.QPalette(app.palette())


def apply_ui_theme(app: QtWidgets.QApplication, theme: str) -> str:
    normalized = normalize_ui_theme(theme)
    remember_system_theme(app)
    app.setProperty("multiPlayTheme", normalized)
    if normalized == "system":
        if _SYSTEM_STYLE_NAME:
            try:
                app.setStyle(_SYSTEM_STYLE_NAME)
            except Exception:
                pass
        if _SYSTEM_PALETTE is not None:
            app.setPalette(QtGui.QPalette(_SYSTEM_PALETTE))
        else:
            app.setPalette(app.style().standardPalette())
        _refresh_app_widgets(app)
        return normalized
    app.setStyle("Fusion")
    app.setPalette(_light_palette() if normalized == "white" else _dark_palette())
    _refresh_app_widgets(app)
    return normalized


def is_dark_palette(palette: QtGui.QPalette) -> bool:
    try:
        return int(palette.color(QtGui.QPalette.ColorRole.Window).lightness()) < 140
    except Exception:
        return True


def _dark_palette() -> QtGui.QPalette:
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(30, 30, 30))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("white"))
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(25, 25, 25))
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(37, 37, 37))
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("white"))
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(45, 45, 45))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor("white"))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(45, 45, 45))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor("white"))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(80, 80, 255))
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("black"))
    return palette


def _light_palette() -> QtGui.QPalette:
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(246, 247, 249))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(20, 24, 28))
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(242, 245, 248))
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(20, 24, 28))
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(236, 239, 243))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(20, 24, 28))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor(20, 24, 28))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(49, 112, 227))
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("white"))
    return palette


def _refresh_app_widgets(app: QtWidgets.QApplication) -> None:
    for widget in list(app.allWidgets()):
        try:
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)
        except Exception:
            pass
        try:
            widget.update()
        except Exception:
            pass
