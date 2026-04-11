from PyQt6 import QtCore

UI_VISIBILITY_ALWAYS = "always"
UI_VISIBILITY_HIDDEN = "hidden"
UI_VISIBILITY_AUTO = "auto"
WINDOWED_UI_AUTO_HIDE_MS = 1500
WINDOWED_UI_AUTO_HIDE_OPTIONS_MS = (1000, 1500, 2000, 3000, 5000)


def normalize_ui_visibility_mode(raw, fallback: str = UI_VISIBILITY_ALWAYS) -> str:
    text = str(raw or "").strip().lower()
    if text in {"always", "show", "visible"}:
        return UI_VISIBILITY_ALWAYS
    if text in {"hidden", "hide", "compact", "video-only"}:
        return UI_VISIBILITY_HIDDEN
    if text in {"auto", "timer", "timed"}:
        return UI_VISIBILITY_AUTO
    return fallback


def compat_ui_visibility_mode_from_payload(payload, fallback: str = UI_VISIBILITY_ALWAYS) -> str:
    if not isinstance(payload, dict):
        return fallback
    mode = normalize_ui_visibility_mode(payload.get("ui_visibility_mode", ""), fallback="")
    if mode:
        return mode
    if bool(payload.get("compact_mode", False)):
        return UI_VISIBILITY_HIDDEN
    return fallback


def normalize_windowed_ui_auto_hide_ms(raw, fallback: int = WINDOWED_UI_AUTO_HIDE_MS) -> int:
    try:
        value = int(round(float(raw)))
    except (TypeError, ValueError):
        value = int(fallback)
    options = tuple(int(v) for v in WINDOWED_UI_AUTO_HIDE_OPTIONS_MS)
    if not options:
        return int(fallback)
    return min(options, key=lambda candidate: abs(candidate - value))


def hide_cursor(main):
    if main._is_fullscreen():
        if main.cursor().shape() != QtCore.Qt.CursorShape.BlankCursor:
            main.setCursor(QtCore.Qt.CursorShape.BlankCursor)
        main._apply_fullscreen_ui_mode("hidden")


def show_cursor(main):
    if main.cursor().shape() != QtCore.Qt.CursorShape.ArrowCursor:
        main.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
    main.cursor_hide_timer.start()


def hide_ui(main):
    main._show_top_ui(False)
    main._show_all_tile_controls(False)
    main._fullscreen_ui_mode = "hidden"
    main._fullscreen_ui_tile = None


def show_ui(main):
    main._show_top_ui(True)
    main._show_all_tile_controls(True)
    main._fullscreen_ui_mode = "all"
    main._fullscreen_ui_tile = None


def sync_windowed_ui_from_compact_mode(main):
    if main._is_fullscreen():
        return
    mode = main.current_ui_visibility_mode()
    timer = getattr(main, "_windowed_ui_hide_timer", None)
    if mode == UI_VISIBILITY_HIDDEN:
        if timer is not None:
            timer.stop()
        main._show_top_ui(False)
        main._show_all_tile_controls(False)
        main._windowed_ui_mode = "hidden"
        main._windowed_ui_tile = None
        return
    if mode == UI_VISIBILITY_ALWAYS:
        if timer is not None:
            timer.stop()
        main._show_top_ui(True)
        main._show_all_tile_controls(True)
        main._windowed_ui_mode = "all"
        main._windowed_ui_tile = None
        return
    main._apply_windowed_ui_mode("all")
    main._restart_windowed_ui_hide_timer()
