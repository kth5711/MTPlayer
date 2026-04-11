from PyQt6 import QtGui, QtWidgets


SUPPORTED_UI_THEMES = ("system", "white", "black")
LIGHT_THEME_BRIGHTNESS_OPTIONS = (80, 90, 100, 110, 120)
DEFAULT_LIGHT_THEME_BRIGHTNESS = 100

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


def normalize_light_theme_brightness(value) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = DEFAULT_LIGHT_THEME_BRIGHTNESS
    if normalized not in LIGHT_THEME_BRIGHTNESS_OPTIONS:
        normalized = min(
            LIGHT_THEME_BRIGHTNESS_OPTIONS,
            key=lambda option: abs(int(option) - int(normalized)),
        )
    return int(normalized)


def current_app_light_theme_brightness(app: QtWidgets.QApplication | None = None) -> int:
    if app is None:
        app = QtWidgets.QApplication.instance()
    if app is None:
        return DEFAULT_LIGHT_THEME_BRIGHTNESS
    try:
        return normalize_light_theme_brightness(app.property("multiPlayLightBrightness"))
    except Exception:
        return DEFAULT_LIGHT_THEME_BRIGHTNESS


def remember_system_theme(app: QtWidgets.QApplication) -> None:
    global _SYSTEM_STYLE_NAME, _SYSTEM_PALETTE
    if _SYSTEM_STYLE_NAME is None:
        _SYSTEM_STYLE_NAME = str(app.style().objectName() or "")
    if _SYSTEM_PALETTE is None:
        _SYSTEM_PALETTE = QtGui.QPalette(app.palette())


def apply_ui_theme(app: QtWidgets.QApplication, theme: str, light_brightness: int = DEFAULT_LIGHT_THEME_BRIGHTNESS) -> str:
    normalized = normalize_ui_theme(theme)
    light_brightness = normalize_light_theme_brightness(light_brightness)
    remember_system_theme(app)
    app.setProperty("multiPlayTheme", normalized)
    app.setProperty("multiPlayLightBrightness", light_brightness)
    if normalized == "system":
        if _SYSTEM_STYLE_NAME:
            try:
                app.setStyle(_SYSTEM_STYLE_NAME)
            except Exception:
                pass
        if _SYSTEM_PALETTE is not None:
            palette = QtGui.QPalette(_SYSTEM_PALETTE)
        else:
            palette = app.style().standardPalette()
        if not is_dark_palette(palette):
            palette = _adjust_palette_for_light_brightness(palette, light_brightness)
        app.setPalette(palette)
        _refresh_app_widgets(app)
        return normalized
    app.setStyle("Fusion")
    app.setPalette(_light_palette(light_brightness) if normalized == "white" else _dark_palette())
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


def light_theme_adjust_color(color: QtGui.QColor, brightness: int | None = None) -> QtGui.QColor:
    normalized = normalize_light_theme_brightness(
        current_app_light_theme_brightness() if brightness is None else brightness
    )
    if normalized == DEFAULT_LIGHT_THEME_BRIGHTNESS:
        return QtGui.QColor(color)
    base = QtGui.QColor(color)
    alpha = base.alpha()
    if normalized > DEFAULT_LIGHT_THEME_BRIGHTNESS:
        ratio = min(1.0, float(normalized - DEFAULT_LIGHT_THEME_BRIGHTNESS) / 20.0)
        channels = [
            int(round(channel + (255 - channel) * ratio))
            for channel in (base.red(), base.green(), base.blue())
        ]
    else:
        factor = max(0.0, float(normalized) / float(DEFAULT_LIGHT_THEME_BRIGHTNESS))
        channels = [
            int(round(channel * factor))
            for channel in (base.red(), base.green(), base.blue())
        ]
    return QtGui.QColor(
        max(0, min(255, channels[0])),
        max(0, min(255, channels[1])),
        max(0, min(255, channels[2])),
        alpha,
    )


def _adjust_palette_for_light_brightness(
    palette: QtGui.QPalette,
    brightness: int,
) -> QtGui.QPalette:
    adjusted = QtGui.QPalette(palette)
    for role in (
        QtGui.QPalette.ColorRole.Window,
        QtGui.QPalette.ColorRole.Base,
        QtGui.QPalette.ColorRole.AlternateBase,
        QtGui.QPalette.ColorRole.Button,
        QtGui.QPalette.ColorRole.ToolTipBase,
        QtGui.QPalette.ColorRole.Highlight,
    ):
        adjusted.setColor(role, light_theme_adjust_color(adjusted.color(role), brightness))
    return adjusted


def _light_palette(brightness: int = DEFAULT_LIGHT_THEME_BRIGHTNESS) -> QtGui.QPalette:
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
    return _adjust_palette_for_light_brightness(palette, brightness)


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
