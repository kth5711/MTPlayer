from __future__ import annotations

import math
import os
import urllib.parse
from typing import TYPE_CHECKING, Dict, List, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:
    from canvas import Canvas
    from video_tile import VideoTile


def _palette_is_dark(widget: QtWidgets.QWidget) -> bool:
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
    try:
        return int(widget.palette().color(QtGui.QPalette.ColorRole.Window).lightness()) < 140
    except Exception:
        return True


def _compare_overlay_stylesheet(widget: QtWidgets.QWidget) -> str:
    if _palette_is_dark(widget):
        return """
        QWidget#CompareOverlayController {
            background-color: rgba(18, 22, 28, 220);
            border: 1px solid rgba(255, 255, 255, 34);
            border-radius: 12px;
        }
        QWidget#CompareOverlayController QLabel,
        QWidget#CompareOverlayController QCheckBox {
            color: #e5ecf4;
            background: transparent;
            border: none;
        }
        QWidget#CompareOverlayController QPushButton {
            color: #e8edf3;
            background: rgba(48, 56, 67, 228);
            border: 1px solid rgba(255, 255, 255, 44);
            border-radius: 8px;
            padding: 4px 10px;
        }
        QWidget#CompareOverlayController QPushButton:hover {
            background: rgba(60, 70, 82, 236);
        }
        QWidget#CompareOverlayController QPushButton:pressed {
            background: rgba(42, 50, 60, 236);
        }
        QWidget#CompareOverlayController QDoubleSpinBox {
            color: #eef3f8;
            background: rgba(30, 36, 43, 224);
            border: 1px solid rgba(255, 255, 255, 36);
            border-radius: 8px;
            padding: 3px 8px;
            selection-background-color: #5b8cff;
            selection-color: #ffffff;
        }
        QWidget#CompareOverlayController QSlider::groove:horizontal {
            height: 6px;
            border-radius: 3px;
            background: rgba(255, 255, 255, 42);
        }
        QWidget#CompareOverlayController QSlider::sub-page:horizontal {
            border-radius: 3px;
            background: rgba(103, 150, 255, 210);
        }
        QWidget#CompareOverlayController QSlider::handle:horizontal {
            width: 14px;
            margin: -5px 0;
            border-radius: 7px;
            background: #f4f7fb;
            border: 1px solid rgba(255, 255, 255, 88);
        }
        QWidget#CompareOverlayController QCheckBox::indicator {
            width: 14px;
            height: 14px;
            border-radius: 4px;
            border: 1px solid rgba(255, 255, 255, 52);
            background: rgba(30, 36, 43, 224);
        }
        QWidget#CompareOverlayController QCheckBox::indicator:checked {
            background: #5b8cff;
            border-color: #5b8cff;
        }
        """
    return """
    QWidget#CompareOverlayController {
        background-color: rgba(239, 244, 249, 244);
        border: 1px solid rgba(92, 108, 126, 94);
        border-radius: 12px;
    }
    QWidget#CompareOverlayController QLabel,
    QWidget#CompareOverlayController QCheckBox {
        color: #324250;
        background: transparent;
        border: none;
    }
    QLabel#CompareOverlayTitle {
        color: #18232e;
        font-size: 13px;
        font-weight: 700;
    }
    QLabel#CompareOverlayValue {
        color: #1f2d38;
        font-weight: 700;
        background: rgba(255, 255, 255, 210);
        border: 1px solid rgba(132, 148, 166, 108);
        border-radius: 7px;
        padding: 2px 8px;
    }
    QWidget#CompareOverlayController QPushButton {
        color: #1f2b36;
        background: rgba(224, 231, 239, 244);
        border: 1px solid rgba(132, 148, 166, 120);
        border-radius: 8px;
        padding: 4px 10px;
    }
    QWidget#CompareOverlayController QPushButton:hover {
        background: rgba(213, 223, 234, 248);
    }
    QWidget#CompareOverlayController QPushButton:pressed {
        background: rgba(203, 214, 226, 250);
    }
    QWidget#CompareOverlayController QDoubleSpinBox {
        color: #1d2a35;
        background: rgba(255, 255, 255, 246);
        border: 1px solid rgba(128, 144, 162, 124);
        border-radius: 8px;
        padding: 3px 8px;
        selection-background-color: #356fcb;
        selection-color: #ffffff;
    }
    QWidget#CompareOverlayController QSlider::groove:horizontal {
        height: 6px;
        border-radius: 3px;
        background: rgba(167, 180, 195, 188);
    }
    QWidget#CompareOverlayController QSlider::sub-page:horizontal {
        border-radius: 3px;
        background: rgba(53, 111, 203, 222);
    }
    QWidget#CompareOverlayController QSlider::handle:horizontal {
        width: 14px;
        margin: -5px 0;
        border-radius: 7px;
        background: #ffffff;
        border: 1px solid rgba(109, 124, 142, 140);
    }
    QWidget#CompareOverlayController QCheckBox::indicator {
        width: 14px;
        height: 14px;
        border-radius: 4px;
        border: 1px solid rgba(128, 144, 162, 124);
        background: rgba(255, 255, 255, 240);
    }
    QWidget#CompareOverlayController QCheckBox::indicator:checked {
        background: #356fcb;
        border-color: #356fcb;
    }
    """


class DetachedTilesOpacityWidget(QtWidgets.QWidget):
    closed = QtCore.pyqtSignal()
    sharedPercentChanged = QtCore.pyqtSignal(int)
    fullscreenChanged = QtCore.pyqtSignal(bool)
    _FULLSCREEN_OVERLAY_HIDE_MS = 1400
    _FULLSCREEN_CURSOR_HIDE_MS = 1400

    def __init__(
        self,
        canvas: "Canvas",
        tiles: List["VideoTile"],
        *,
        parent: Optional[QtWidgets.QWidget] = None,
        title: str = "타일 투명도",
        initial_percent: int = 100,
    ):
        super().__init__(parent)
        self._canvas = canvas
        self._tiles = [tile for tile in list(dict.fromkeys(list(tiles or []))) if tile in getattr(canvas, "tiles", [])]
        self._restoring = False
        self._closing_requested = False
        self._shared_percent = max(1, min(100, int(initial_percent)))
        self._app = QtWidgets.QApplication.instance()
        self._host_restore_opacity = 1.0
        self._host_pre_fullscreen_geometry: Optional[QtCore.QRect] = None
        self._host_pre_fullscreen_maximized = False
        self._roller_offset_px = 0.0
        self._roller_last_tick_ms = 0
        self._roller_state_signature: tuple[str, int, bool, int] | None = None
        self._defer_canvas_sync = False
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(str(title or "타일 투명도"))
        self.resize(1200, 760)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._body = QtWidgets.QWidget(self)
        self._body.setMouseTracking(True)
        self._grid = QtWidgets.QGridLayout(self._body)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(6)
        outer.addWidget(self._body, 1)

        self._control_overlay = QtWidgets.QFrame(self)
        self._control_overlay.setObjectName("OpacityDockOverlay")
        self._control_overlay.setMouseTracking(True)
        self._control_overlay.setStyleSheet(
            """
            QFrame#OpacityDockOverlay {
                background-color: rgba(20, 24, 30, 190);
                border: 1px solid rgba(255, 255, 255, 36);
                border-radius: 12px;
            }
            """
        )
        top_layout = QtWidgets.QHBoxLayout(self._control_overlay)
        top_layout.setContentsMargins(12, 10, 12, 10)
        top_layout.setSpacing(8)

        self._title_label = QtWidgets.QLabel(self.windowTitle(), self._control_overlay)
        self._title_label.setObjectName("AuxDockLabel")
        top_layout.addWidget(self._title_label, 1)

        self._opacity_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, self._control_overlay)
        self._opacity_slider.setRange(1, 100)
        self._opacity_slider.setSingleStep(1)
        self._opacity_slider.setPageStep(5)
        self._opacity_slider.setFixedWidth(180)
        top_layout.addWidget(self._opacity_slider)

        self._opacity_label = QtWidgets.QLabel("100%", self._control_overlay)
        self._opacity_label.setObjectName("AuxDockLabel")
        self._opacity_label.setMinimumWidth(48)
        self._opacity_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        top_layout.addWidget(self._opacity_label)

        self._fullscreen_button = QtWidgets.QPushButton("전체화면", self._control_overlay)
        self._fullscreen_button.setObjectName("AuxDockButton")
        top_layout.addWidget(self._fullscreen_button)

        self._redock_button = QtWidgets.QPushButton("타일로 복귀", self._control_overlay)
        self._redock_button.setObjectName("AuxDockButton")
        top_layout.addWidget(self._redock_button)

        self._overlay_hide_timer = QtCore.QTimer(self)
        self._overlay_hide_timer.setSingleShot(True)
        self._overlay_hide_timer.timeout.connect(self._hide_overlay_if_fullscreen)
        self._cursor_hide_timer = QtCore.QTimer(self)
        self._cursor_hide_timer.setSingleShot(True)
        self._cursor_hide_timer.timeout.connect(self._hide_cursor_if_fullscreen)
        self._roller_timer = QtCore.QTimer(self)
        self._roller_timer.setInterval(30)
        self._roller_timer.timeout.connect(self._advance_roller)
        self._canvas_sync_timer = QtCore.QTimer(self)
        self._canvas_sync_timer.setSingleShot(True)
        self._canvas_sync_timer.timeout.connect(self._run_deferred_canvas_sync)
        self._opacity_slider.valueChanged.connect(self._handle_opacity_changed)
        self._fullscreen_button.clicked.connect(self._toggle_fullscreen)
        self._redock_button.clicked.connect(self.close)

        self._host_restore_opacity = self._current_host_opacity()
        self._adopt_tiles()
        self._sync_opacity_widgets()
        if self._app is not None:
            try:
                self._app.installEventFilter(self)
            except Exception:
                pass
        QtCore.QTimer.singleShot(0, self._bind_all_tiles)
        QtCore.QTimer.singleShot(0, self._sync_control_overlay_geometry)
        QtCore.QTimer.singleShot(0, self._show_overlay_transient)

    def shared_percent(self) -> int:
        return int(self._shared_percent)

    def set_shared_percent(self, percent: int) -> None:
        self._shared_percent = max(1, min(100, int(percent)))
        self._sync_opacity_widgets()

    def contains_global_point(self, gp: QtCore.QPoint) -> bool:
        host = self._host_window()
        try:
            if host is None or not host.isVisible():
                return False
        except Exception:
            return False
        rect = QtCore.QRect(self.mapToGlobal(QtCore.QPoint(0, 0)), self.size())
        return rect.contains(gp)

    def docked_tile_at_global(
        self, gp: QtCore.QPoint, exclude: Optional["VideoTile"] = None
    ) -> Optional["VideoTile"]:
        if not self.contains_global_point(gp):
            return None
        for tile in self._display_tiles():
            if tile is exclude:
                continue
            rect = QtCore.QRect(tile.mapToGlobal(QtCore.QPoint(0, 0)), tile.size())
            if rect.contains(gp):
                return tile
        return None

    def sync_from_canvas_state(self) -> None:
        self._sync_roller_state_signature()
        spotlight_tile = None
        try:
            spotlight_tile = self._canvas.spotlight_tile()
        except Exception:
            spotlight_tile = None
        display_tiles = self._display_tiles()
        if spotlight_tile is None or spotlight_tile not in display_tiles:
            self._rebuild_grid()
            return
        self._set_roller_running(False)
        self._sync_grid_widgets([spotlight_tile], cols=1)
        self._title_label.setText(f"{self.windowTitle()} ({len(display_tiles)}개)")
        self._sync_control_overlay_geometry()

    def schedule_sync_from_canvas_state(self, delay_ms: int = 0) -> None:
        self._defer_canvas_sync = True
        self._canvas_sync_timer.start(max(0, int(delay_ms)))

    def _run_deferred_canvas_sync(self) -> None:
        self._defer_canvas_sync = False
        self.sync_from_canvas_state()

    def _host_window(self) -> QtWidgets.QWidget:
        try:
            host = self.window()
        except Exception:
            host = None
        return host if host is not None else self

    def _current_host_opacity(self) -> float:
        host = self._host_window()
        try:
            value = float(host.windowOpacity())
        except Exception:
            value = 1.0
        return max(0.01, min(1.0, value))

    def _set_host_chrome_visible(self, visible: bool) -> None:
        host = self._host_window()
        visible = bool(visible)
        try:
            menu_bar_getter = getattr(host, "menuBar", None)
            if callable(menu_bar_getter):
                menu_bar = menu_bar_getter()
                if menu_bar is not None:
                    menu_bar.setVisible(visible)
        except Exception:
            pass
        try:
            toolbar = getattr(host, "control_toolbar", None)
            if toolbar is not None:
                toolbar.setVisible(visible)
        except Exception:
            pass
        try:
            status_bar_getter = getattr(host, "statusBar", None)
            if callable(status_bar_getter):
                status_bar = status_bar_getter()
                if status_bar is not None:
                    status_bar.setVisible(visible)
        except Exception:
            pass

    def _sync_host_chrome_for_fullscreen(self) -> None:
        self._set_host_chrome_visible(not self._is_host_fullscreen())

    def _is_host_fullscreen(self) -> bool:
        host = self._host_window()
        try:
            return bool(
                host.isFullScreen()
                or bool(host.windowState() & QtCore.Qt.WindowState.WindowFullScreen)
            )
        except Exception:
            try:
                return bool(self.isFullScreen())
            except Exception:
                return False

    def _grid_dimensions(self, count: int) -> tuple[int, int]:
        count = max(0, int(count))
        if count <= 0:
            return 0, 0
        getter = getattr(self._canvas, "_grid_dimensions_for_count", None)
        if callable(getter):
            try:
                cols, rows = getter(count)
                return int(cols), int(rows)
            except Exception:
                pass
        try:
            mode = self._canvas.normalize_layout_mode(getattr(self._canvas, "_layout_mode", None))
        except Exception:
            mode = "auto"
        if mode in {getattr(self._canvas, "LAYOUT_ROW", "row")}:
            return count, 1
        if mode in {getattr(self._canvas, "LAYOUT_COLUMN", "column")}:
            return 1, count
        cols = max(1, int(math.ceil(math.sqrt(count))))
        rows = int(math.ceil(count / cols))
        return cols, rows

    def _clear_grid(self, *, hide: bool = True) -> None:
        while self._grid.count() > 0:
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self._grid.removeWidget(widget)
                if hide:
                    widget.hide()

    def _sync_grid_widgets(self, display_tiles: list["VideoTile"], *, cols: int) -> None:
        keep = set(display_tiles)
        for index in range(self._grid.count() - 1, -1, -1):
            item = self._grid.itemAt(index)
            widget = item.widget()
            if widget is None:
                continue
            if widget not in keep:
                self._grid.removeWidget(widget)
                widget.hide()
        for index, tile in enumerate(display_tiles):
            row = index // max(1, cols)
            col = index % max(1, cols)
            tile.setParent(self._body)
            self._grid.addWidget(tile, row, col)
            tile.show()
            try:
                tile.setMouseTracking(True)
            except Exception:
                pass

    def _display_tiles(self) -> list["VideoTile"]:
        return [
            tile for tile in self._tiles
            if tile in getattr(self._canvas, "tiles", []) and tile not in getattr(self._canvas, "detached_windows", {})
        ]

    def _remove_from_grid(self, tile: "VideoTile") -> None:
        for index in range(self._grid.count() - 1, -1, -1):
            item = self._grid.itemAt(index)
            widget = item.widget()
            if widget is tile:
                self._grid.removeWidget(tile)
                tile.hide()
                break

    def _rebuild_grid(self) -> None:
        display_tiles = self._display_tiles()
        if self._apply_roller_layout(display_tiles):
            return
        cols, rows = self._grid_dimensions(len(display_tiles))
        if cols <= 0 or rows <= 0:
            self._set_roller_running(False)
            self._clear_grid()
            self._title_label.setText(f"{self.windowTitle()} (0개)")
            self._sync_control_overlay_geometry()
            return
        self._set_roller_running(False)
        self._sync_grid_widgets(display_tiles, cols=cols)
        self._title_label.setText(f"{self.windowTitle()} ({len(display_tiles)}개)")
        self._sync_control_overlay_geometry()

    def _layout_mode(self) -> str:
        getter = getattr(self._canvas, "layout_mode", None)
        if callable(getter):
            try:
                return str(getter())
            except Exception:
                pass
        normalize = getattr(self._canvas, "normalize_layout_mode", None)
        if callable(normalize):
            try:
                return str(normalize(getattr(self._canvas, "_layout_mode", None)))
            except Exception:
                pass
        return "auto"

    def _roller_mode(self) -> Optional[str]:
        mode = self._layout_mode()
        roller_row = getattr(self._canvas, "LAYOUT_ROLLER_ROW", "roller_row")
        roller_col = getattr(self._canvas, "LAYOUT_ROLLER_COLUMN", "roller_column")
        if mode in {roller_row, roller_col}:
            return mode
        return None

    def _roller_visible_count(self) -> int:
        getter = getattr(self._canvas, "roller_visible_count", None)
        if callable(getter):
            try:
                return max(1, int(getter()))
            except Exception:
                pass
        return 3

    def _roller_speed_px_per_sec(self) -> int:
        getter = getattr(self._canvas, "roller_speed_px_per_sec", None)
        if callable(getter):
            try:
                return max(1, int(getter()))
            except Exception:
                pass
        return 90

    def _roller_paused(self) -> bool:
        getter = getattr(self._canvas, "roller_paused", None)
        if callable(getter):
            try:
                return bool(getter())
            except Exception:
                pass
        return False

    def _sync_roller_state_signature(self) -> None:
        signature = (
            self._layout_mode(),
            self._roller_visible_count(),
            self._roller_paused(),
            self._roller_speed_px_per_sec(),
        )
        if signature == self._roller_state_signature:
            return
        previous = self._roller_state_signature
        self._roller_state_signature = signature
        if previous is None:
            return
        if previous[0] != signature[0] or previous[1] != signature[1]:
            self._roller_offset_px = 0.0
        self._roller_last_tick_ms = 0

    def _set_roller_running(self, enabled: bool) -> None:
        if enabled:
            if not self._roller_timer.isActive():
                self._roller_last_tick_ms = QtCore.QDateTime.currentMSecsSinceEpoch()
                self._roller_timer.start()
            return
        if self._roller_timer.isActive():
            self._roller_timer.stop()
        self._roller_last_tick_ms = 0

    def _roller_has_media(self, display_tiles: list["VideoTile"]) -> bool:
        checker = getattr(self._canvas, "_roller_has_media", None)
        if callable(checker):
            try:
                return bool(checker(display_tiles))
            except Exception:
                pass
        for tile in display_tiles:
            if tile is None:
                continue
            try:
                if bool(getattr(tile, "playlist", None)):
                    return True
                player = getattr(tile, "mediaplayer", None)
                if player is not None and player.get_media() is not None:
                    return True
            except Exception:
                continue
        return False

    def _roller_metrics(self, mode: str, count: int) -> tuple[str, int, int]:
        getter = getattr(self._canvas, "_roller_metrics", None)
        width = max(1, self._body.width())
        height = max(1, self._body.height())
        if callable(getter):
            try:
                axis, step, total = getter(mode, count, width, height)
                return str(axis), int(step), int(total)
            except Exception:
                pass
        if mode == getattr(self._canvas, "LAYOUT_ROLLER_COLUMN", "roller_column"):
            step = max(1, height // max(1, min(self._roller_visible_count(), count)))
            return "y", step, step * count
        step = max(1, width // max(1, min(self._roller_visible_count(), count)))
        return "x", step, step * count

    def _apply_roller_layout(self, display_tiles: list["VideoTile"]) -> bool:
        mode = self._roller_mode()
        count = len(display_tiles)
        if mode is None or count <= 1:
            self._set_roller_running(False)
            return False
        self._clear_grid(hide=False)
        width = self._body.width()
        height = self._body.height()
        if width <= 0 or height <= 0:
            self._set_roller_running(False)
            return False
        if self._roller_paused() or not self._roller_has_media(display_tiles):
            self._set_roller_running(False)
        axis, step, total = self._roller_metrics(mode, count)
        if total <= 0:
            self._set_roller_running(False)
            return False
        offset = float(self._roller_offset_px) % float(total)
        for idx, tile in enumerate(display_tiles):
            tile.setParent(self._body)
            pos = float(idx * step) - offset
            while pos <= -float(step):
                pos += float(total)
            if axis == "y":
                rect = QtCore.QRect(0, int(round(pos)), width, step)
            else:
                rect = QtCore.QRect(int(round(pos)), 0, step, height)
            tile.setGeometry(rect)
            tile.show()
        self._title_label.setText(f"{self.windowTitle()} ({len(display_tiles)}개)")
        self._sync_control_overlay_geometry()
        self._set_roller_running(not self._roller_paused() and self._roller_has_media(display_tiles))
        return True

    def _advance_roller(self) -> None:
        mode = self._roller_mode()
        display_tiles = self._display_tiles()
        count = len(display_tiles)
        if (
            mode is None
            or count <= 1
            or self._roller_paused()
            or not self._roller_has_media(display_tiles)
            or self._body.width() <= 0
            or self._body.height() <= 0
        ):
            self._set_roller_running(False)
            return
        _axis, _step, total = self._roller_metrics(mode, count)
        if total <= 0:
            self._set_roller_running(False)
            return
        now_ms = QtCore.QDateTime.currentMSecsSinceEpoch()
        last_ms = self._roller_last_tick_ms or now_ms
        self._roller_last_tick_ms = now_ms
        delta_ms = max(0, int(now_ms - last_ms))
        if delta_ms <= 0:
            return
        delta_px = (float(delta_ms) / 1000.0) * float(self._roller_speed_px_per_sec())
        self._roller_offset_px = (float(self._roller_offset_px) + delta_px) % float(total)
        self._apply_roller_layout(display_tiles)

    def _adopt_tiles(self) -> None:
        self._canvas.mark_tiles_in_opacity_dock(self._tiles)
        mainwin = self._canvas.window()
        for tile in self._tiles:
            try:
                setattr(tile, "_main_window_owner", mainwin)
            except Exception:
                pass
            try:
                setattr(tile, "_opacity_dock_owner", self)
            except Exception:
                pass
        self._rebuild_grid()

    def release_tile_to_detached(self, tile: "VideoTile") -> None:
        if tile not in self._tiles:
            return
        self._canvas.unmark_tiles_in_opacity_dock([tile])
        self._remove_from_grid(tile)
        self._title_label.setText(f"{self.windowTitle()} ({len(self._display_tiles())}개)")

    def accept_redocked_tile(self, tile: "VideoTile") -> bool:
        if self._restoring or self._closing_requested or tile not in getattr(self._canvas, "tiles", []):
            return False
        self._opacity_slider.blockSignals(True)
        try:
            if tile not in self._tiles:
                self._tiles.append(tile)
            try:
                setattr(tile, "_opacity_dock_owner", self)
            except Exception:
                pass
            self._canvas.mark_tiles_in_opacity_dock([tile])
            tile.setParent(self._body)
            tile.show()
            self._rebuild_grid()
            QtCore.QTimer.singleShot(0, lambda current=tile: current.bind_hwnd())
            if not self.isVisible():
                self.show()
            self.raise_()
            self.activateWindow()
            self._show_overlay_transient()
        finally:
            self._opacity_slider.blockSignals(False)
        return True

    def _restore_tiles(self) -> None:
        if self._restoring:
            return
        self._restoring = True
        try:
            self._clear_grid()
            for tile in self._tiles:
                try:
                    if getattr(tile, "_opacity_dock_owner", None) is self:
                        setattr(tile, "_opacity_dock_owner", None)
                except Exception:
                    pass
                if tile not in getattr(self._canvas, "tiles", []):
                    continue
                if tile in getattr(self._canvas, "detached_windows", {}):
                    continue
                tile.setParent(self._canvas)
                tile.show()
            self._canvas.unmark_tiles_in_opacity_dock(self._tiles)
            self._canvas.relayout()
            QtCore.QTimer.singleShot(0, self._bind_all_tiles)
        finally:
            self._restoring = False

    def _bind_all_tiles(self) -> None:
        for tile in self._tiles:
            if tile not in getattr(self._canvas, "tiles", []):
                continue
            try:
                tile.bind_hwnd()
            except Exception:
                pass

    def _set_display_tiles_controls_visible(self, visible: bool) -> None:
        for tile in self._display_tiles():
            try:
                tile.show_controls(bool(visible))
            except Exception:
                pass

    def _sync_opacity_widgets(self) -> None:
        with QtCore.QSignalBlocker(self._opacity_slider):
            self._opacity_slider.setValue(self._shared_percent)
        self._opacity_label.setText(f"{self._shared_percent}%")
        opacity = max(0.01, min(1.0, float(self._shared_percent) / 100.0))
        host = self._host_window()
        try:
            host.setWindowOpacity(opacity)
        except Exception:
            try:
                self.setWindowOpacity(opacity)
            except Exception:
                pass
        self._sync_control_overlay_geometry()
        self.sharedPercentChanged.emit(int(self._shared_percent))

    def _handle_opacity_changed(self, value: int) -> None:
        self._shared_percent = max(1, min(100, int(value)))
        self._sync_opacity_widgets()
        self._show_overlay_transient()

    def _toggle_fullscreen(self) -> None:
        host = self._host_window()
        try:
            if host is not None and host is not self and bool(getattr(host, "is_opacity_mode_active", lambda: False)()):
                host.toggle_fullscreen()
                return
        except Exception:
            pass
        try:
            fullscreen = bool(
                host.isFullScreen()
                or bool(host.windowState() & QtCore.Qt.WindowState.WindowFullScreen)
            )
        except Exception:
            fullscreen = False
        try:
            if fullscreen:
                if self._host_pre_fullscreen_maximized:
                    host.showNormal()
                    if self._host_pre_fullscreen_geometry is not None:
                        host.setGeometry(self._host_pre_fullscreen_geometry)
                    host.showMaximized()
                else:
                    if self._host_pre_fullscreen_geometry is not None:
                        host.setGeometry(self._host_pre_fullscreen_geometry)
                    host.showNormal()
            else:
                self._host_pre_fullscreen_geometry = QtCore.QRect(host.geometry())
                self._host_pre_fullscreen_maximized = bool(
                    host.isMaximized()
                    or bool(host.windowState() & QtCore.Qt.WindowState.WindowMaximized)
                )
                host.showFullScreen()
        except Exception:
            try:
                if fullscreen:
                    self.showNormal()
                else:
                    self.showFullScreen()
            except Exception:
                pass
        self._sync_host_chrome_for_fullscreen()
        self.fullscreenChanged.emit(bool(self._is_host_fullscreen()))
        self._show_overlay_transient()

    def _exit_fullscreen_if_needed(self) -> None:
        host = self._host_window()
        try:
            if host is not None and host is not self and bool(getattr(host, "is_opacity_mode_active", lambda: False)()):
                if bool(getattr(host, "_is_fullscreen", lambda: False)()):
                    host.exit_fullscreen()
                return
        except Exception:
            pass
        if self._is_host_fullscreen():
            self._toggle_fullscreen()

    def _show_overlay_transient(self) -> None:
        if self._is_host_fullscreen():
            self._control_overlay.hide()
            self._overlay_hide_timer.stop()
            self._cursor_hide_timer.stop()
        else:
            self._control_overlay.hide()
            self._overlay_hide_timer.stop()
            self._cursor_hide_timer.stop()
            self._set_display_tiles_controls_visible(True)
            self._show_cursor()

    def _hide_overlay_if_fullscreen(self) -> None:
        if self._is_host_fullscreen():
            self._control_overlay.hide()
            self._set_display_tiles_controls_visible(False)

    def _show_cursor(self) -> None:
        try:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        except Exception:
            pass

    def _hide_cursor_if_fullscreen(self) -> None:
        if not self._is_host_fullscreen():
            return
        try:
            self.setCursor(QtCore.Qt.CursorShape.BlankCursor)
        except Exception:
            pass

    def _sync_control_overlay_geometry(self) -> None:
        hint = self._control_overlay.sizeHint()
        width = min(max(hint.width(), 420), max(420, self.width() - 24))
        self._control_overlay.resize(width, hint.height())
        x = max(12, (self.width() - self._control_overlay.width()) // 2)
        y = 12
        self._control_overlay.move(x, y)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._sync_control_overlay_geometry()
        if not self._defer_canvas_sync:
            self.sync_from_canvas_state()

    def changeEvent(self, event: QtCore.QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.Type.WindowStateChange:
            self._sync_host_chrome_for_fullscreen()
            self.fullscreenChanged.emit(bool(self._is_host_fullscreen()))
            self._show_overlay_transient()
            if not self._is_host_fullscreen():
                self._show_cursor()
                self._set_display_tiles_controls_visible(True)
                self.schedule_sync_from_canvas_state(90)

    def _event_global_pos(self, event: QtCore.QEvent) -> QtCore.QPoint | None:
        getter = getattr(event, "globalPosition", None)
        if callable(getter):
            try:
                return getter().toPoint()
            except Exception:
                return None
        getter = getattr(event, "globalPos", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                return None
        return None

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        host = self._host_window()
        if watched is host and event.type() == QtCore.QEvent.Type.WindowStateChange:
            self._show_overlay_transient()
        if self.isVisible() and event.type() in {
            QtCore.QEvent.Type.MouseMove,
            QtCore.QEvent.Type.MouseButtonPress,
            QtCore.QEvent.Type.Wheel,
            QtCore.QEvent.Type.Enter,
            QtCore.QEvent.Type.HoverMove,
        }:
            global_pos = self._event_global_pos(event)
            if global_pos is None:
                try:
                    global_pos = QtGui.QCursor.pos()
                except Exception:
                    global_pos = None
            try:
                if global_pos is not None and host.frameGeometry().contains(global_pos):
                    self._show_overlay_transient()
            except Exception:
                pass
        return super().eventFilter(watched, event)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._sync_host_chrome_for_fullscreen()
        self.fullscreenChanged.emit(bool(self._is_host_fullscreen()))
        self._show_overlay_transient()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._overlay_hide_timer.stop()
        self._cursor_hide_timer.stop()
        self._roller_timer.stop()
        self._canvas_sync_timer.stop()
        self._show_cursor()
        self._set_host_chrome_visible(True)
        if self._app is not None:
            try:
                self._app.removeEventFilter(self)
            except Exception:
                pass
        try:
            self._host_window().setWindowOpacity(float(self._host_restore_opacity))
        except Exception:
            pass
        self._restore_tiles()
        self.closed.emit()
        super().closeEvent(event)


DetachedTilesOpacityDockWindow = DetachedTilesOpacityWidget


class _CompareCloneWindow(QtWidgets.QWidget):
    def __init__(self, tile: "VideoTile", *, parent: Optional[QtWidgets.QWidget] = None):
        flags = (
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        if hasattr(QtCore.Qt.WindowType, "WindowDoesNotAcceptFocus"):
            flags |= QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
        if hasattr(QtCore.Qt.WindowType, "WindowTransparentForInput"):
            flags |= QtCore.Qt.WindowType.WindowTransparentForInput
        super().__init__(parent, flags)
        self._tile = tile
        self._path = ""
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if hasattr(QtCore.Qt.WidgetAttribute, "WA_TranslucentBackground"):
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(False)
        self.setStyleSheet("background: transparent; border: none;")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(tile, 1)
        self._playback_sync_ready_after_ms = 0

    @property
    def tile(self) -> "VideoTile":
        return self._tile

    @property
    def media_path(self) -> str:
        return self._path

    @media_path.setter
    def media_path(self, value: str) -> None:
        self._path = str(value or "")

    def defer_playback_sync(self, delay_ms: int = 450) -> None:
        self._playback_sync_ready_after_ms = (
            QtCore.QDateTime.currentMSecsSinceEpoch() + max(0, int(delay_ms))
        )

    def playback_sync_ready(self) -> bool:
        return QtCore.QDateTime.currentMSecsSinceEpoch() >= int(
            self._playback_sync_ready_after_ms or 0
        )


class DetachedTilesCompareOverlayController(QtWidgets.QWidget):
    closed = QtCore.pyqtSignal()
    sharedPercentChanged = QtCore.pyqtSignal(int)
    fullscreenChanged = QtCore.pyqtSignal(bool)
    _POLL_INTERVAL_MS = 140
    _DEFAULT_OFFSET_MS = -1000
    _FULLSCREEN_OVERLAY_HIDE_MS = 1400
    _OPACITY_LABEL_TEXT = "투명도"

    def __init__(
        self,
        canvas: "Canvas",
        tiles: List["VideoTile"],
        *,
        parent: Optional[QtWidgets.QWidget] = None,
        title: str = "비교 오버레이",
        initial_percent: int = 100,
        initial_offset_ms: Optional[int] = None,
    ):
        flags = (
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(parent, flags)
        self._canvas = canvas
        self._host = canvas.window()
        self._title = str(title or "비교 오버레이")
        self._shared_percent = max(1, min(100, int(initial_percent)))
        if initial_offset_ms is None:
            initial_offset_ms = self._DEFAULT_OFFSET_MS
        self._offset_ms = int(initial_offset_ms)
        self._audio_enabled = False
        self._sources: List["VideoTile"] = []
        self._clone_windows: Dict[int, _CompareCloneWindow] = {}
        self._last_debug_state: Dict[int, str] = {}
        self._host_always_on_top_suspended = False
        self._app = QtWidgets.QApplication.instance()
        self._sync_timer = QtCore.QTimer(self)
        self._sync_timer.setInterval(self._POLL_INTERVAL_MS)
        self._sync_timer.timeout.connect(self._poll_sync)
        self._defer_sync_timer = QtCore.QTimer(self)
        self._defer_sync_timer.setSingleShot(True)
        self._defer_sync_timer.timeout.connect(self._poll_sync)
        self._overlay_hide_timer = QtCore.QTimer(self)
        self._overlay_hide_timer.setSingleShot(True)
        self._overlay_hide_timer.timeout.connect(self._hide_overlay_if_fullscreen)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle(self._title)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setObjectName("CompareOverlayController")
        self._build_ui()
        self.refresh_theme_styles()
        self._set_sources(tiles)
        if self._host is not None:
            try:
                self._host.installEventFilter(self)
            except Exception:
                pass
        if self._app is not None:
            try:
                self._app.installEventFilter(self)
            except Exception:
                pass
        self._suspend_host_always_on_top_if_needed()
        self._sync_timer.start()
        QtCore.QTimer.singleShot(0, self._initial_show)

    def shared_percent(self) -> int:
        return int(self._shared_percent)

    def set_shared_percent(self, percent: int) -> None:
        normalized = max(1, min(100, int(percent)))
        if normalized == self._shared_percent:
            return
        self._shared_percent = normalized
        with QtCore.QSignalBlocker(self._opacity_slider):
            self._opacity_slider.setValue(normalized)
        self._opacity_value_label.setText(f"{normalized}%")
        self._apply_clone_opacity()
        self.sharedPercentChanged.emit(int(normalized))

    def schedule_sync_from_canvas_state(self, delay_ms: int = 0) -> None:
        self._defer_sync_timer.start(max(0, int(delay_ms)))

    def sync_from_canvas_state(self) -> None:
        self._poll_sync()

    def accept_redocked_tile(self, _tile: "VideoTile") -> bool:
        self.schedule_sync_from_canvas_state(0)
        return False

    def contains_global_point(self, gp: QtCore.QPoint) -> bool:
        controller_rect = QtCore.QRect(self.mapToGlobal(QtCore.QPoint(0, 0)), self.size())
        if controller_rect.contains(gp):
            return True
        for window in self._clone_windows.values():
            try:
                if window.isVisible() and window.frameGeometry().contains(gp):
                    return True
            except Exception:
                continue
        return False

    def docked_tile_at_global(
        self, gp: QtCore.QPoint, exclude: Optional["VideoTile"] = None
    ) -> Optional["VideoTile"]:
        for source in self._current_source_tiles():
            if source is exclude:
                continue
            rect = self._source_global_rect(source)
            if rect is not None and rect.contains(gp):
                return source
        return None

    def _initial_show(self) -> None:
        self._position_near_host()
        self.show()
        self.raise_()
        self._poll_sync()
        QtCore.QTimer.singleShot(120, self._poll_sync)
        QtCore.QTimer.singleShot(280, self._poll_sync)

    def _build_ui(self) -> None:
        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(8)

        self._title_label = QtWidgets.QLabel(self._OPACITY_LABEL_TEXT, self)
        self._title_label.setObjectName("CompareOverlayTitle")
        outer.addWidget(self._title_label, 1)

        self._opacity_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, self)
        self._opacity_slider.setRange(1, 100)
        self._opacity_slider.setSingleStep(1)
        self._opacity_slider.setPageStep(5)
        self._opacity_slider.setFixedWidth(160)
        self._opacity_slider.setValue(self._shared_percent)
        outer.addWidget(self._opacity_slider, 0)

        self._opacity_value_label = QtWidgets.QLabel(f"{self._shared_percent}%", self)
        self._opacity_value_label.setObjectName("CompareOverlayValue")
        self._opacity_value_label.setMinimumWidth(44)
        self._opacity_value_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        outer.addWidget(self._opacity_value_label, 0)

        self._offset_spin = QtWidgets.QDoubleSpinBox(self)
        self._offset_spin.setRange(-60.0, 60.0)
        self._offset_spin.setDecimals(3)
        self._offset_spin.setSingleStep(0.001)
        self._offset_spin.setSuffix(" s")
        self._offset_spin.setValue(float(self._offset_ms) / 1000.0)
        self._offset_spin.setToolTip("메인 타일 기준 시간 오프셋")
        outer.addWidget(self._offset_spin, 0)

        self._audio_toggle = QtWidgets.QCheckBox("오디오", self)
        self._audio_toggle.setChecked(False)
        outer.addWidget(self._audio_toggle, 0)

        self._close_button = QtWidgets.QPushButton("복귀", self)
        outer.addWidget(self._close_button, 0)

        self._opacity_slider.valueChanged.connect(self.set_shared_percent)
        self._offset_spin.valueChanged.connect(self._handle_offset_changed)
        self._audio_toggle.toggled.connect(self._handle_audio_toggled)
        self._close_button.clicked.connect(self.close)

    def refresh_theme_styles(self) -> None:
        self.setStyleSheet(_compare_overlay_stylesheet(self))
        for widget in [self, *self.findChildren(QtWidgets.QWidget)]:
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

    def _set_sources(self, tiles: List["VideoTile"]) -> None:
        unique: List["VideoTile"] = []
        seen: set[int] = set()
        for tile in list(tiles or []):
            if tile not in getattr(self._canvas, "tiles", []):
                continue
            marker = id(tile)
            if marker in seen:
                continue
            seen.add(marker)
            unique.append(tile)
        self._sources = unique

    def _current_source_tiles(self) -> List["VideoTile"]:
        if self._sources:
            current = [tile for tile in self._sources if tile in getattr(self._canvas, "tiles", [])]
        else:
            current = []
        for tile in getattr(self._canvas, "tiles", []):
            if tile in current:
                continue
            current.append(tile)
        return current

    def _poll_sync(self) -> None:
        self._sync_sources()
        self._sync_controller_title()
        self._position_near_host()
        self._apply_clone_opacity()
        self._restack_compare_windows()

    def _sync_sources(self) -> None:
        current_sources = self._current_source_tiles()
        current_ids = {id(tile) for tile in current_sources}
        for source_id in list(self._clone_windows.keys()):
            if source_id not in current_ids:
                self._destroy_clone_window(source_id)
        for source_id in list(self._last_debug_state.keys()):
            if source_id not in current_ids:
                self._last_debug_state.pop(source_id, None)
        for source in current_sources:
            source_id = id(source)
            window = self._clone_windows.get(source_id)
            if window is None:
                window = self._create_clone_window(source)
                self._clone_windows[source_id] = window
            self._sync_clone_window(source, window)

    def _sync_controller_title(self) -> None:
        self._title_label.setText(self._OPACITY_LABEL_TEXT)

    def _create_clone_window(self, source: "VideoTile") -> _CompareCloneWindow:
        from video_tile import VideoTile

        clone_tile = VideoTile(None, vlc_instance=None)
        try:
            clone_tile._main_window_owner = self._host
        except Exception:
            pass
        try:
            clone_tile._compare_overlay_clone = True
        except Exception:
            pass
        try:
            clone_tile._should_use_hw_accel = lambda: False
        except Exception:
            pass
        try:
            clone_tile._apply_media_hw_options = lambda _media: None
        except Exception:
            pass
        try:
            clone_tile.set_border_visible(False)
        except Exception:
            pass
        try:
            clone_tile.set_compact_mode(True)
        except Exception:
            pass
        try:
            clone_tile.show_controls(False)
        except Exception:
            pass
        clone_tile.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        window = _CompareCloneWindow(clone_tile, parent=None)
        window.setWindowTitle(str(getattr(source, "lbl_title", None).text() if getattr(source, "lbl_title", None) is not None else self._title))
        try:
            window.setWindowOpacity(max(0.01, min(1.0, float(self._shared_percent) / 100.0)))
        except Exception:
            pass
        return window

    def _destroy_clone_window(self, source_id: int) -> None:
        window = self._clone_windows.pop(source_id, None)
        if window is None:
            return
        clone_tile = window.tile
        try:
            clone_tile.shutdown()
        except Exception:
            pass
        try:
            clone_tile.setParent(None)
        except Exception:
            pass
        try:
            clone_tile.deleteLater()
        except Exception:
            pass
        try:
            window.close()
        except Exception:
            pass
        try:
            window.deleteLater()
        except Exception:
            pass

    def _resolve_source_path(self, source: "VideoTile") -> str:
        for getter_name in ("_current_playlist_path", "_current_media_path"):
            getter = getattr(source, getter_name, None)
            if not callable(getter):
                continue
            try:
                path = self._normalize_source_candidate(getter())
            except Exception:
                path = ""
            if not path:
                continue
            return path
        playlist = list(getattr(source, "playlist", []) or [])
        current_index = int(getattr(source, "current_index", -1) or -1)
        candidate_indices = []
        if 0 <= current_index < len(playlist):
            candidate_indices.append(current_index)
        candidate_indices.extend(idx for idx in range(len(playlist)) if idx != current_index)
        for idx in candidate_indices:
            try:
                path = self._normalize_source_candidate(playlist[idx])
            except Exception:
                path = ""
            if path:
                return path
        try:
            title_widget = getattr(source, "title", None)
            tooltip = str(title_widget.toolTip() if title_widget is not None else "").strip()
        except Exception:
            tooltip = ""
        path = self._normalize_source_candidate(tooltip)
        if path:
            return path
        path = self._resolve_source_path_from_mrl(source)
        if path:
            return path
        return ""

    def _normalize_source_candidate(self, candidate) -> str:
        path = str(candidate or "").strip()
        if not path:
            return ""
        if "://" in path:
            return path
        normalized = os.path.normpath(path)
        if os.path.exists(normalized):
            return normalized
        if os.path.isabs(normalized):
            return normalized
        return ""

    def _resolve_source_path_from_mrl(self, source: "VideoTile") -> str:
        try:
            media = source.mediaplayer.get_media()
            mrl = str(media.get_mrl() or "").strip() if media is not None else ""
        except Exception:
            mrl = ""
        if not mrl:
            return ""
        if mrl.startswith("file:///"):
            raw = urllib.parse.unquote(mrl[8:])
            if os.name == "nt":
                raw = raw.replace("/", "\\")
            return self._normalize_source_candidate(raw)
        return self._normalize_source_candidate(mrl)

    def _source_global_rect(self, source: "VideoTile") -> Optional[QtCore.QRect]:
        try:
            if not source.isVisible():
                return None
            video_widget = getattr(source, "video_widget", None)
            if video_widget is not None and video_widget.isVisible():
                if video_widget.width() > 1 and video_widget.height() > 1:
                    top_left = video_widget.mapToGlobal(QtCore.QPoint(0, 0))
                    return QtCore.QRect(top_left, video_widget.size())
            if source.width() <= 1 or source.height() <= 1:
                return None
            top_left = source.mapToGlobal(QtCore.QPoint(0, 0))
            return QtCore.QRect(top_left, source.size())
        except Exception:
            return None

    def _sync_clone_window(self, source: "VideoTile", window: _CompareCloneWindow) -> None:
        source_id = id(source)
        rect = self._source_global_rect(source)
        path = self._resolve_source_path(source)
        if rect is None or not path:
            reason = "source hidden or invalid geometry" if rect is None else "source path unavailable"
            self._debug_once(source_id, reason)
            window.hide()
            return
        self._last_debug_state.pop(source_id, None)
        if window.geometry() != rect:
            window.setGeometry(rect)
        if not window.isVisible():
            window.show()
            window.raise_()
        if path != window.media_path:
            self._open_clone_media(window, source, path)
        self._sync_clone_visual_state(source, window.tile)
        self._sync_clone_audio_state(source, window.tile)
        if not window.playback_sync_ready():
            return
        self._sync_clone_playback_state(source, window.tile)

    def _open_clone_media(self, window: _CompareCloneWindow, source: "VideoTile", path: str) -> None:
        clone = window.tile
        source_id = id(source)
        try:
            clone.clear_playlist()
        except Exception:
            pass
        try:
            clone.playlist = [path]
            clone.current_index = 0
        except Exception:
            pass
        try:
            clone.external_subtitles = dict(getattr(source, "external_subtitles", {}) or {})
        except Exception:
            pass
        try:
            try:
                clone.bind_hwnd(force=True)
            except Exception:
                pass
            opened = bool(clone.set_media(path, show_error_dialog=False))
            if opened:
                self._debug_once(source_id, f"open ok: {path}")
                window.media_path = path
                window.defer_playback_sync(450)
                try:
                    if bool(source.mediaplayer.is_playing()):
                        clone.play()
                except Exception:
                    pass
                QtCore.QTimer.singleShot(0, self._restack_compare_windows)
                QtCore.QTimer.singleShot(
                    420,
                    lambda current_window=window, current_source=source: self._prime_clone_after_open(
                        current_source, current_window
                    ),
                )
                QtCore.QTimer.singleShot(120, self._poll_sync)
                QtCore.QTimer.singleShot(480, self._poll_sync)
                QtCore.QTimer.singleShot(820, self._poll_sync)
            else:
                self._debug_once(source_id, f"open returned false: {path}")
                window.media_path = ""
        except Exception:
            self._debug_once(source_id, f"open failed: {path}")
            window.media_path = ""

    def _debug_once(self, source_id: int, message: str) -> None:
        message = str(message or "")
        if self._last_debug_state.get(source_id) == message:
            return
        self._last_debug_state[source_id] = message
        print(f"[compare-overlay] {message}")

    def _sync_clone_visual_state(self, source: "VideoTile", clone: "VideoTile") -> None:
        display_mode = str(getattr(source, "display_mode", "fit") or "fit")
        if str(getattr(clone, "display_mode", "fit") or "fit") != display_mode:
            try:
                clone.set_display_mode(display_mode)
            except Exception:
                pass
        transform_mode = str(getattr(source, "transform_mode", "none") or "none")
        if str(getattr(clone, "transform_mode", "none") or "none") != transform_mode:
            try:
                clone.set_transform_mode(transform_mode)
            except Exception:
                pass
        source_rate = float(getattr(source, "playback_rate", 1.0) or 1.0)
        if abs(float(getattr(clone, "playback_rate", 1.0) or 1.0) - source_rate) > 1e-3:
            try:
                clone.playback_rate = source_rate
                clone.mediaplayer.set_rate(source_rate)
            except Exception:
                pass

    def _sync_clone_audio_state(self, source: "VideoTile", clone: "VideoTile") -> None:
        try:
            clone.tile_volume = int(getattr(source, "tile_volume", 120))
        except Exception:
            pass
        clone_muted = (not self._audio_enabled) or bool(getattr(source, "tile_muted", False))
        try:
            clone.set_tile_muted(clone_muted)
        except Exception:
            pass

    def _sync_clone_playback_state(self, source: "VideoTile", clone: "VideoTile") -> None:
        if bool(getattr(source, "is_static_image", lambda: False)()):
            return
        target_ms = self._target_clone_ms(source, clone)
        try:
            clone_ms = int(clone.current_playback_ms())
        except Exception:
            clone_ms = 0
        try:
            source_playing = bool(source.mediaplayer.is_playing())
        except Exception:
            source_playing = False
        drift = abs(int(clone_ms) - int(target_ms))
        if source_playing:
            if drift > 250:
                try:
                    clone.seek_ms(target_ms, play=True, show_overlay=False)
                except Exception:
                    pass
            else:
                try:
                    if not bool(clone.mediaplayer.is_playing()):
                        clone.play()
                except Exception:
                    pass
            return
        if drift > 80:
            try:
                clone.seek_ms(target_ms, play=False, show_overlay=False)
            except Exception:
                pass
        else:
            try:
                clone.pause()
            except Exception:
                pass

    def _target_clone_ms(self, source: "VideoTile", clone: "VideoTile") -> int:
        try:
            source_ms = int(source.current_playback_ms())
        except Exception:
            source_ms = 0
        target_ms = int(source_ms + self._offset_ms)
        try:
            clone_length = int(clone.mediaplayer.get_length() or 0)
        except Exception:
            clone_length = 0
        if clone_length > 0:
            return max(0, min(target_ms, max(0, clone_length - 500)))
        return max(0, target_ms)

    def _prime_clone_after_open(
        self, source: "VideoTile", window: _CompareCloneWindow
    ) -> None:
        if not bool(window.media_path):
            return
        clone = window.tile
        target_ms = self._target_clone_ms(source, clone)
        try:
            source_playing = bool(source.mediaplayer.is_playing())
        except Exception:
            source_playing = False
        try:
            clone.seek_ms(target_ms, play=source_playing, show_overlay=False)
        except Exception:
            pass
        self._restack_compare_windows()

    def _apply_clone_opacity(self) -> None:
        opacity = max(0.01, min(1.0, float(self._shared_percent) / 100.0))
        for window in self._clone_windows.values():
            try:
                window.setWindowOpacity(opacity)
            except Exception:
                pass

    def _handle_offset_changed(self, value: float) -> None:
        self._offset_ms = int(round(float(value) * 1000.0))
        self.schedule_sync_from_canvas_state(0)

    def _handle_audio_toggled(self, checked: bool) -> None:
        self._audio_enabled = bool(checked)
        self.schedule_sync_from_canvas_state(0)

    def _position_near_host(self) -> None:
        host = self._host
        if host is None:
            return
        try:
            geom = host.frameGeometry()
        except Exception:
            return
        if geom.width() <= 0 or geom.height() <= 0:
            return
        size = self.sizeHint()
        width = max(size.width(), 560)
        self.resize(width, self.sizeHint().height())
        x = geom.left() + max(20, (geom.width() - self.width()) // 2)
        y = geom.top() + 16
        self.move(x, y)

    def _is_host_fullscreen(self) -> bool:
        host = self._host
        if host is None:
            return False
        try:
            return bool(
                host.isFullScreen()
                or bool(host.windowState() & QtCore.Qt.WindowState.WindowFullScreen)
                or bool(getattr(host, "_is_fullscreen", lambda: False)())
            )
        except Exception:
            return False

    def _hide_overlay_if_fullscreen(self) -> None:
        if not self._is_host_fullscreen():
            return
        try:
            self.hide()
        except Exception:
            pass

    def _toggle_fullscreen(self) -> None:
        host = self._host
        if host is None:
            return
        toggle = getattr(host, "toggle_fullscreen", None)
        if callable(toggle):
            try:
                toggle()
            except Exception:
                pass

    def _restack_compare_windows(self) -> None:
        for window in self._clone_windows.values():
            try:
                if window.isVisible():
                    window.raise_()
            except Exception:
                pass
        try:
            if self.isVisible():
                self.raise_()
        except Exception:
            pass

    def _set_host_topmost(self, enabled: bool) -> None:
        host = self._host
        if host is None:
            return
        try:
            was_visible = host.isVisible()
            was_maximized = host.isMaximized()
            was_fullscreen = host.isFullScreen() or bool(
                host.windowState() & QtCore.Qt.WindowState.WindowFullScreen
            )
            geom = host.geometry()
            flags = host.windowFlags()
            if enabled:
                host.setWindowFlags(flags | QtCore.Qt.WindowType.WindowStaysOnTopHint)
            else:
                host.setWindowFlags(flags & ~QtCore.Qt.WindowType.WindowStaysOnTopHint)
            if was_fullscreen:
                host.showFullScreen()
            elif was_maximized:
                host.showMaximized()
            elif was_visible:
                host.showNormal()
                host.setGeometry(geom)
            else:
                host.setGeometry(geom)
            if was_visible:
                try:
                    host.raise_()
                except Exception:
                    pass
        except Exception:
            pass

    def _suspend_host_always_on_top_if_needed(self) -> None:
        host = self._host
        if host is None:
            return
        try:
            checked = bool(getattr(host, "always_on_top_action", None).isChecked())
        except Exception:
            checked = False
        if not checked:
            return
        self._host_always_on_top_suspended = True
        self._set_host_topmost(False)

    def _restore_host_always_on_top_if_needed(self) -> None:
        if not self._host_always_on_top_suspended:
            return
        self._host_always_on_top_suspended = False
        self._set_host_topmost(True)

    def _show_overlay_transient(self) -> None:
        if self._is_host_fullscreen():
            try:
                self.show()
                self.raise_()
            except Exception:
                pass
            self._overlay_hide_timer.stop()
            self._overlay_hide_timer.start(self._FULLSCREEN_OVERLAY_HIDE_MS)
            return
        self._overlay_hide_timer.stop()
        try:
            self.show()
            self.raise_()
        except Exception:
            pass

    def _event_global_pos(self, event: QtCore.QEvent) -> QtCore.QPoint | None:
        getter = getattr(event, "globalPosition", None)
        if callable(getter):
            try:
                return getter().toPoint()
            except Exception:
                return None
        getter = getattr(event, "globalPos", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                return None
        return None

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if watched is self._host:
            event_type = event.type()
            if event_type in {
                QtCore.QEvent.Type.Move,
                QtCore.QEvent.Type.Resize,
                QtCore.QEvent.Type.Show,
                QtCore.QEvent.Type.WindowStateChange,
            }:
                self._position_near_host()
                self.schedule_sync_from_canvas_state(0)
                QtCore.QTimer.singleShot(0, self._restack_compare_windows)
                QtCore.QTimer.singleShot(50, self._restack_compare_windows)
                self.fullscreenChanged.emit(
                    bool(getattr(self._host, "_is_fullscreen", lambda: False)())
                )
            elif event_type in {
                QtCore.QEvent.Type.ActivationChange,
                QtCore.QEvent.Type.MouseButtonPress,
            }:
                QtCore.QTimer.singleShot(0, self._restack_compare_windows)
                QtCore.QTimer.singleShot(50, self._restack_compare_windows)
        if event.type() in {
            QtCore.QEvent.Type.MouseMove,
            QtCore.QEvent.Type.MouseButtonPress,
            QtCore.QEvent.Type.Wheel,
            QtCore.QEvent.Type.Enter,
            QtCore.QEvent.Type.HoverMove,
            QtCore.QEvent.Type.KeyPress,
        }:
            global_pos = self._event_global_pos(event)
            if global_pos is None:
                try:
                    global_pos = QtGui.QCursor.pos()
                except Exception:
                    global_pos = None
            host = self._host
            try:
                if host is not None and global_pos is not None and host.frameGeometry().contains(global_pos):
                    self._show_overlay_transient()
            except Exception:
                pass
        return super().eventFilter(watched, event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._sync_timer.stop()
        self._defer_sync_timer.stop()
        self._overlay_hide_timer.stop()
        if self._host is not None:
            try:
                self._host.removeEventFilter(self)
            except Exception:
                pass
        if self._app is not None:
            try:
                self._app.removeEventFilter(self)
            except Exception:
                pass
        self._restore_host_always_on_top_if_needed()
        for source_id in list(self._clone_windows.keys()):
            self._destroy_clone_window(source_id)
        self.closed.emit()
        super().closeEvent(event)
