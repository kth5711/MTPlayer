from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:
    from canvas import Canvas
    from video_tile import VideoTile


class DetachedTilesGroupFrame(QtWidgets.QWidget):
    def __init__(
        self,
        canvas: "Canvas",
        tiles: List["VideoTile"],
        *,
        title: str = "분리 타일 묶음",
        restore_opacities: Optional[Dict["VideoTile", float]] = None,
    ):
        flags = (
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(None, flags)
        self._canvas = canvas
        self._tiles = list(dict.fromkeys(list(tiles or [])))
        self._title_base = str(title or "분리 타일 묶음")
        self._pad = 6
        self._header_height = 34
        self._drag_active = False
        self._resize_active = False
        self._resize_edges = 0
        self._resize_margin = 10
        self._drag_start_global = QtCore.QPoint()
        self._drag_start_geometry = QtCore.QRect()
        self._resize_start_global = QtCore.QPoint()
        self._resize_start_geometry = QtCore.QRect()
        self._resize_start_union = QtCore.QRect()
        self._drag_member_geometries: dict["VideoTile", QtCore.QRect] = {}
        self._resize_member_geometries: dict["VideoTile", QtCore.QRect] = {}
        self._restore_opacities: dict["VideoTile", float] = {}
        self._header_rect = QtCore.QRect()
        self._hole_rect = QtCore.QRect()
        self._observed_windows: set[QtWidgets.QWidget] = set()
        self._visual_opacity_percent = 100
        for tile, opacity in dict(restore_opacities or {}).items():
            try:
                self._restore_opacities[tile] = max(0.01, min(1.0, float(opacity)))
            except (TypeError, ValueError):
                self._restore_opacities[tile] = 1.0

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setMouseTracking(True)

        self.header = QtWidgets.QWidget(self)
        self.header.setObjectName("detachedGroupHeader")
        self.header.setMouseTracking(True)
        header_layout = QtWidgets.QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 6, 10, 6)
        header_layout.setSpacing(8)

        self.title_label = QtWidgets.QLabel(self._title_base, self.header)
        self.title_label.installEventFilter(self)
        self.title_label.setStyleSheet("color: white; font-weight: 600;")
        header_layout.addWidget(self.title_label, 1)
        self.header.installEventFilter(self)

        self.opacity_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, self.header)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setSingleStep(1)
        self.opacity_slider.setPageStep(5)
        self.opacity_slider.setFixedWidth(140)
        header_layout.addWidget(self.opacity_slider)

        self.opacity_label = QtWidgets.QLabel("100%", self.header)
        self.opacity_label.setMinimumWidth(44)
        self.opacity_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.opacity_label.setStyleSheet("color: white;")
        header_layout.addWidget(self.opacity_label)

        self.redock_button = QtWidgets.QPushButton("타일로 복귀", self.header)
        self.redock_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self.redock_button)

        self.close_button = QtWidgets.QToolButton(self.header)
        self.close_button.setText("×")
        self.close_button.setAutoRaise(True)
        self.close_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.close_button.setStyleSheet("color: white; font-size: 16px; font-weight: 700;")
        header_layout.addWidget(self.close_button)

        self.opacity_slider.valueChanged.connect(self._handle_opacity_changed)
        self.redock_button.clicked.connect(self._redock_all)
        self.close_button.clicked.connect(self.close)

        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setInterval(120)
        self._refresh_timer.timeout.connect(self.refresh_from_tiles)
        self._refresh_timer.start()
        self._queued_refresh_timer = QtCore.QTimer(self)
        self._queued_refresh_timer.setSingleShot(True)
        self._queued_refresh_timer.setInterval(0)
        self._queued_refresh_timer.timeout.connect(self.refresh_from_tiles)

        self.refresh_from_tiles(force=True)

    _RESIZE_LEFT = 1
    _RESIZE_TOP = 2
    _RESIZE_RIGHT = 4
    _RESIZE_BOTTOM = 8

    def _active_tiles(self) -> list["VideoTile"]:
        active: list["VideoTile"] = []
        for tile in self._tiles:
            if tile not in self._canvas.tiles:
                continue
            if not self._canvas.is_detached(tile):
                continue
            if self._canvas.detached_window_for_tile(tile) is None:
                continue
            active.append(tile)
        return active

    def _active_union_rect(self) -> QtCore.QRect | None:
        rect: QtCore.QRect | None = None
        for tile in self._active_tiles():
            window = self._canvas.detached_window_for_tile(tile)
            if window is None:
                continue
            geometry = QtCore.QRect(window.frameGeometry())
            rect = geometry if rect is None else rect.united(geometry)
        return rect

    def _any_fullscreen_tile(self, active: list["VideoTile"]) -> bool:
        for tile in active:
            window = self._canvas.detached_window_for_tile(tile)
            if window is None:
                continue
            try:
                if window.isFullScreen() or bool(
                    window.windowState() & QtCore.Qt.WindowState.WindowFullScreen
                ):
                    return True
            except Exception:
                continue
        return False

    def _sync_window_observers(self, active: list["VideoTile"]) -> None:
        active_windows: set[QtWidgets.QWidget] = set()
        for tile in active:
            window = self._canvas.detached_window_for_tile(tile)
            if window is not None:
                active_windows.add(window)
        stale = [window for window in self._observed_windows if window not in active_windows]
        for window in stale:
            setter = getattr(window, "set_group_title_bar_hidden", None)
            if callable(setter):
                try:
                    setter(False)
                except Exception:
                    pass
            try:
                window.removeEventFilter(self)
            except Exception:
                pass
            self._observed_windows.discard(window)
        for window in active_windows:
            if window in self._observed_windows:
                continue
            try:
                window.installEventFilter(self)
            except Exception:
                continue
            setter = getattr(window, "set_group_title_bar_hidden", None)
            if callable(setter):
                try:
                    setter(True)
                except Exception:
                    pass
            self._observed_windows.add(window)

    def _queue_refresh(self, *, force: bool = False) -> None:
        if self._drag_active or self._resize_active:
            return
        if force:
            self.refresh_from_tiles(force=True)
            return
        if not self._queued_refresh_timer.isActive():
            self._queued_refresh_timer.start()

    def _group_geometry_from_union(self, union: QtCore.QRect) -> QtCore.QRect:
        return QtCore.QRect(
            int(union.left() - self._pad),
            int(union.top() - self._header_height - self._pad),
            int(union.width() + (self._pad * 2)),
            int(union.height() + self._header_height + (self._pad * 2)),
        )

    def _union_rect_from_group_geometry(self, rect: QtCore.QRect) -> QtCore.QRect:
        return QtCore.QRect(
            int(rect.left() + self._pad),
            int(rect.top() + self._header_height + self._pad),
            max(1, int(rect.width() - (self._pad * 2))),
            max(1, int(rect.height() - self._header_height - (self._pad * 2))),
        )

    def _minimum_group_size(self) -> QtCore.QSize:
        return QtCore.QSize(220, self._header_height + 120)

    def _resize_edges_for_pos(self, pos: QtCore.QPoint) -> int:
        rect = self.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return 0
        margin = max(4, int(self._resize_margin))
        edges = 0
        if pos.x() <= margin:
            edges |= self._RESIZE_LEFT
        elif pos.x() >= rect.width() - margin:
            edges |= self._RESIZE_RIGHT
        if pos.y() <= margin:
            edges |= self._RESIZE_TOP
        elif pos.y() >= rect.height() - margin:
            edges |= self._RESIZE_BOTTOM
        return edges

    def _cursor_for_resize_edges(self, edges: int) -> QtCore.Qt.CursorShape:
        if edges in (self._RESIZE_LEFT | self._RESIZE_TOP, self._RESIZE_RIGHT | self._RESIZE_BOTTOM):
            return QtCore.Qt.CursorShape.SizeFDiagCursor
        if edges in (self._RESIZE_RIGHT | self._RESIZE_TOP, self._RESIZE_LEFT | self._RESIZE_BOTTOM):
            return QtCore.Qt.CursorShape.SizeBDiagCursor
        if edges & (self._RESIZE_LEFT | self._RESIZE_RIGHT):
            return QtCore.Qt.CursorShape.SizeHorCursor
        if edges & (self._RESIZE_TOP | self._RESIZE_BOTTOM):
            return QtCore.Qt.CursorShape.SizeVerCursor
        return QtCore.Qt.CursorShape.ArrowCursor

    def _apply_resize_cursor(self, edges: int) -> None:
        self.setCursor(self._cursor_for_resize_edges(edges))
        try:
            self.header.setCursor(self._cursor_for_resize_edges(edges) if edges else QtCore.Qt.CursorShape.ArrowCursor)
        except Exception:
            pass
        try:
            self.title_label.setCursor(self._cursor_for_resize_edges(edges) if edges else QtCore.Qt.CursorShape.ArrowCursor)
        except Exception:
            pass

    def _resized_group_geometry(self, delta: QtCore.QPoint) -> QtCore.QRect:
        geom = QtCore.QRect(self._resize_start_geometry)
        min_size = self._minimum_group_size()
        min_w = int(min_size.width())
        min_h = int(min_size.height())
        x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()
        if self._resize_edges & self._RESIZE_LEFT:
            x += delta.x()
            w -= delta.x()
        elif self._resize_edges & self._RESIZE_RIGHT:
            w += delta.x()
        if self._resize_edges & self._RESIZE_TOP:
            y += delta.y()
            h -= delta.y()
        elif self._resize_edges & self._RESIZE_BOTTOM:
            h += delta.y()
        if w < min_w:
            if self._resize_edges & self._RESIZE_LEFT and not (self._resize_edges & self._RESIZE_RIGHT):
                x = geom.x() + geom.width() - min_w
            w = min_w
        if h < min_h:
            if self._resize_edges & self._RESIZE_TOP and not (self._resize_edges & self._RESIZE_BOTTOM):
                y = geom.y() + geom.height() - min_h
            h = min_h
        return QtCore.QRect(x, y, w, h)

    def _begin_resize(self, edges: int, global_pos: QtCore.QPoint) -> bool:
        if not edges:
            return False
        union = self._active_union_rect()
        if union is None or union.width() <= 0 or union.height() <= 0:
            return False
        self._resize_active = True
        self._resize_edges = int(edges)
        self._resize_start_global = QtCore.QPoint(global_pos)
        self._resize_start_geometry = QtCore.QRect(self.geometry())
        self._resize_start_union = QtCore.QRect(union)
        self._resize_member_geometries = {}
        for tile in self._active_tiles():
            window = self._canvas.detached_window_for_tile(tile)
            if window is not None:
                self._resize_member_geometries[tile] = QtCore.QRect(window.geometry())
        self._apply_resize_cursor(edges)
        return True

    def _apply_member_resize(self, new_union: QtCore.QRect) -> None:
        old_union = QtCore.QRect(self._resize_start_union)
        old_w = max(1, int(old_union.width()))
        old_h = max(1, int(old_union.height()))
        new_w = max(1, int(new_union.width()))
        new_h = max(1, int(new_union.height()))
        for tile, geometry in self._resize_member_geometries.items():
            window = self._canvas.detached_window_for_tile(tile)
            if window is None:
                continue
            rel_left = (int(geometry.left()) - int(old_union.left())) / old_w
            rel_top = (int(geometry.top()) - int(old_union.top())) / old_h
            rel_width = max(0.0, int(geometry.width()) / old_w)
            rel_height = max(0.0, int(geometry.height()) / old_h)
            target = QtCore.QRect(
                int(round(new_union.left() + (rel_left * new_w))),
                int(round(new_union.top() + (rel_top * new_h))),
                max(80, int(round(rel_width * new_w))),
                max(60, int(round(rel_height * new_h))),
            )
            if target.right() > new_union.right():
                target.moveRight(new_union.right())
            if target.bottom() > new_union.bottom():
                target.moveBottom(new_union.bottom())
            if target.left() < new_union.left():
                target.moveLeft(new_union.left())
            if target.top() < new_union.top():
                target.moveTop(new_union.top())
            window.setGeometry(target)

    def _update_resize(self, global_pos: QtCore.QPoint) -> bool:
        if not self._resize_active:
            return False
        delta = QtCore.QPoint(global_pos - self._resize_start_global)
        target_geometry = self._resized_group_geometry(delta)
        self.setGeometry(target_geometry)
        self._apply_member_resize(self._union_rect_from_group_geometry(target_geometry))
        self._update_layout_and_mask()
        return True

    def _end_resize(self) -> None:
        self._resize_active = False
        self._resize_edges = 0
        self._resize_member_geometries = {}
        self._apply_resize_cursor(0)

    def _current_percent(self) -> int:
        active = self._active_tiles()
        if not active:
            return 100
        try:
            return max(10, min(100, int(round(float(active[0].detached_window_opacity) * 100.0))))
        except Exception:
            return 100

    def _apply_self_opacity(self, percent: int) -> None:
        self._visual_opacity_percent = max(10, min(100, int(percent)))
        try:
            self.setWindowOpacity(max(0.10, min(1.0, float(self._visual_opacity_percent) / 100.0)))
        except Exception:
            pass
        self.update()

    def _sync_slider(self) -> None:
        percent = self._current_percent()
        with QtCore.QSignalBlocker(self.opacity_slider):
            self.opacity_slider.setValue(percent)
        self.opacity_label.setText(f"{percent}%")
        self._apply_self_opacity(percent)

    def _update_layout_and_mask(self) -> None:
        rect = self.rect()
        self._header_rect = QtCore.QRect(
            self._pad,
            0,
            max(1, rect.width() - (self._pad * 2)),
            self._header_height,
        )
        self._hole_rect = QtCore.QRect(
            self._pad,
            self._header_height + self._pad,
            max(1, rect.width() - (self._pad * 2)),
            max(1, rect.height() - self._header_height - (self._pad * 2)),
        )
        self.header.setGeometry(self._header_rect)
        outer_region = QtGui.QRegion(rect)
        hole_region = QtGui.QRegion(self._hole_rect)
        self.setMask(outer_region.subtracted(hole_region))

    def refresh_from_tiles(self, *, force: bool = False) -> None:
        active = self._active_tiles()
        self._sync_window_observers(active)
        if not active:
            self.close()
            return
        if self._any_fullscreen_tile(active):
            if self.isVisible():
                self.hide()
            return
        union = self._active_union_rect()
        if union is None or union.width() <= 0 or union.height() <= 0:
            self.close()
            return
        target_geometry = self._group_geometry_from_union(union)
        if force or ((not self._drag_active and not self._resize_active) and self.geometry() != target_geometry):
            self.setGeometry(target_geometry)
        self.title_label.setText(f"{self._title_base} ({len(active)}개)")
        self.redock_button.setEnabled(bool(active))
        self._sync_slider()
        self._update_layout_and_mask()
        if not self.isVisible():
            self.show()
        self.raise_()

    def _handle_opacity_changed(self, value: int) -> None:
        percent = max(10, min(100, int(value)))
        self.opacity_label.setText(f"{percent}%")
        self._apply_self_opacity(percent)
        active = self._active_tiles()
        if active:
            self._canvas.set_tiles_window_opacity(active, percent / 100.0)

    def _redock_all(self) -> None:
        active = self._active_tiles()
        if not active:
            self.close()
            return
        self._canvas._restore_main_window_if_minimized()
        for tile in active:
            self._restore_tile_opacity(tile)
            self._canvas.redock_tile(tile)
        self.close()

    def _restore_tile_opacity(self, tile: "VideoTile") -> None:
        restore_opacity = self._restore_opacities.get(tile)
        if restore_opacity is None:
            return
        window = self._canvas.detached_window_for_tile(tile)
        if window is not None:
            window.set_window_opacity_value(restore_opacity)
            return
        try:
            tile.detached_window_opacity = float(restore_opacity)
        except Exception:
            pass

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        opacity_ratio = max(0.10, min(1.0, float(self._visual_opacity_percent) / 100.0))
        frame_color = QtGui.QColor(120, 180, 210, max(18, int(round(180 * opacity_ratio))))
        header_fill = QtGui.QColor(18, 24, 30, max(24, int(round(220 * opacity_ratio))))
        strip_fill = QtGui.QColor(18, 24, 30, max(8, int(round(72 * opacity_ratio))))

        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(header_fill)
        painter.drawRoundedRect(QtCore.QRectF(self._header_rect), 8.0, 8.0)

        left_strip = QtCore.QRect(0, self._header_height, self._pad, self.height() - self._header_height)
        right_strip = QtCore.QRect(
            self.width() - self._pad,
            self._header_height,
            self._pad,
            self.height() - self._header_height,
        )
        top_strip = QtCore.QRect(0, self._header_height, self.width(), self._pad)
        bottom_strip = QtCore.QRect(0, self.height() - self._pad, self.width(), self._pad)
        painter.setBrush(strip_fill)
        for strip in (left_strip, right_strip, top_strip, bottom_strip):
            painter.drawRect(strip)

        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(frame_color, 1))
        painter.drawRoundedRect(QtCore.QRectF(self.rect().adjusted(1, 1, -1, -1)), 10.0, 10.0)
        painter.drawRoundedRect(QtCore.QRectF(self._hole_rect.adjusted(-1, -1, 1, 1)), 6.0, 6.0)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        title_label = getattr(self, "title_label", None)
        if watched not in {self.header, title_label}:
            if watched in self._observed_windows:
                event_type = event.type()
                if event_type in {
                    QtCore.QEvent.Type.Move,
                    QtCore.QEvent.Type.Resize,
                    QtCore.QEvent.Type.Show,
                    QtCore.QEvent.Type.Hide,
                    QtCore.QEvent.Type.WindowStateChange,
                }:
                    self._queue_refresh(force=(event_type == QtCore.QEvent.Type.WindowStateChange))
            return super().eventFilter(watched, event)
        if event.type() == QtCore.QEvent.Type.MouseButtonPress:
            mouse_event = event
            if isinstance(mouse_event, QtGui.QMouseEvent) and mouse_event.button() == QtCore.Qt.MouseButton.LeftButton:
                local_pos = watched.mapTo(self, mouse_event.position().toPoint()) if isinstance(watched, QtWidgets.QWidget) and watched is not self else mouse_event.position().toPoint()
                edges = self._resize_edges_for_pos(local_pos)
                if self._begin_resize(edges, mouse_event.globalPosition().toPoint()):
                    return True
                self._drag_active = True
                self._drag_start_global = mouse_event.globalPosition().toPoint()
                self._drag_start_geometry = QtCore.QRect(self.geometry())
                self._drag_member_geometries = {}
                for tile in self._active_tiles():
                    window = self._canvas.detached_window_for_tile(tile)
                    if window is not None:
                        self._drag_member_geometries[tile] = QtCore.QRect(window.geometry())
                return True
        if event.type() == QtCore.QEvent.Type.MouseMove and self._drag_active:
            mouse_event = event
            if isinstance(mouse_event, QtGui.QMouseEvent):
                delta = mouse_event.globalPosition().toPoint() - self._drag_start_global
                self.move(self._drag_start_geometry.topLeft() + delta)
                for tile, geometry in self._drag_member_geometries.items():
                    window = self._canvas.detached_window_for_tile(tile)
                    if window is not None:
                        window.setGeometry(QtCore.QRect(geometry).translated(delta))
                return True
        if event.type() == QtCore.QEvent.Type.MouseMove:
            mouse_event = event
            if isinstance(mouse_event, QtGui.QMouseEvent):
                if self._resize_active:
                    return self._update_resize(mouse_event.globalPosition().toPoint())
                local_pos = watched.mapTo(self, mouse_event.position().toPoint()) if isinstance(watched, QtWidgets.QWidget) and watched is not self else mouse_event.position().toPoint()
                self._apply_resize_cursor(self._resize_edges_for_pos(local_pos))
        if event.type() == QtCore.QEvent.Type.MouseButtonRelease and self._drag_active:
            self._drag_active = False
            self._drag_member_geometries = {}
            self.refresh_from_tiles(force=True)
            return True
        if event.type() == QtCore.QEvent.Type.MouseButtonRelease and self._resize_active:
            self._end_resize()
            self.refresh_from_tiles(force=True)
            return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self._begin_resize(self._resize_edges_for_pos(event.position().toPoint()), event.globalPosition().toPoint()):
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._resize_active:
            if self._update_resize(event.globalPosition().toPoint()):
                event.accept()
                return
        self._apply_resize_cursor(self._resize_edges_for_pos(event.position().toPoint()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._resize_active and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._end_resize()
            self.refresh_from_tiles(force=True)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._refresh_timer.stop()
        self._queued_refresh_timer.stop()
        for window in list(self._observed_windows):
            setter = getattr(window, "set_group_title_bar_hidden", None)
            if callable(setter):
                try:
                    setter(False)
                except Exception:
                    pass
            try:
                window.removeEventFilter(self)
            except Exception:
                pass
        self._observed_windows.clear()
        super().closeEvent(event)
