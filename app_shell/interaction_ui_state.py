from PyQt6 import QtCore


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
    if main._is_compact_mode():
        main._show_top_ui(False)
        main._show_all_tile_controls(False)
        return
    main._show_ui()
