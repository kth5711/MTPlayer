import logging
import os
import sys
import threading
from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets
import vlc

from i18n import tr
from scene_analysis.core.media import _ffmpeg_frame_to_qimage

logger = logging.getLogger(__name__)
SNAPSHOT_REFRESH_MAX_WIDTH = 1920
MAX_PREVIEW_SURFACE_DIMENSION = 16384
PREVIEW_ASPECT_LIMIT_FACTOR = 2.2
PREVIEW_SMALL_FOCUS_SOFTEN_START = 0.18
PREVIEW_SMALL_FOCUS_SOFTEN_END = 0.08


class FocusReviewFrameWorker(QtCore.QThread):
    frameReady = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._condition = threading.Condition()
        self._running = True
        self._pending_job: Optional[dict] = None
        self._cap = None
        self._cap_path: Optional[str] = None
        self._cap_lock = threading.Lock()

    def request_frame(self, job: dict) -> None:
        payload = dict(job or {})
        if not payload:
            return
        with self._condition:
            self._pending_job = payload
            self._condition.notify()

    def stop(self, wait_ms: int = 2000) -> None:
        with self._condition:
            self._running = False
            self._pending_job = None
            self._condition.notify()
        try:
            self.wait(max(0, int(wait_ms)))
        except RuntimeError:
            logger.debug("focus review worker wait skipped", exc_info=True)
        self._release_cap()

    def run(self) -> None:
        while True:
            with self._condition:
                while self._running and self._pending_job is None:
                    self._condition.wait()
                if not self._running:
                    break
                job = dict(self._pending_job or {})
                self._pending_job = None
            try:
                raw_max_width = job.get("max_width", 960)
                image = self._extract_frame_image(
                    str(job.get("path") or ""),
                    int(job.get("ms", 0) or 0),
                    max_width=960 if raw_max_width in (None, "") else int(raw_max_width),
                    transform_mode=str(job.get("transform_mode", "none") or "none"),
                )
            except Exception:
                logger.warning("focus review frame extraction failed", exc_info=True)
                image = QtGui.QImage()
            payload = dict(job)
            payload["image"] = image
            if self._running:
                self.frameReady.emit(payload)
        self._release_cap()

    def _extract_frame_image(self, path: str, ms: int, *, max_width: int, transform_mode: str) -> QtGui.QImage:
        image = self._extract_cv2_qimage(path, ms, max_width=max_width)
        if image is None or image.isNull():
            target_w = max(320, int(max_width)) if int(max_width) > 0 else 3840
            target_h = max(180, int(round(float(target_w) * 9.0 / 16.0)))
            image = _ffmpeg_frame_to_qimage(path, ms, w=target_w, h=target_h)
        if image is None or image.isNull():
            return QtGui.QImage()
        image = _scale_image_to_width(image, max_width=max_width)
        return _apply_transform_mode_to_image(image, transform_mode)

    def _extract_cv2_qimage(self, path: str, ms: int, *, max_width: int) -> Optional[QtGui.QImage]:
        try:
            import cv2
        except ImportError:
            return None
        if not path or not os.path.isfile(path):
            return None
        cap = self._ensure_capture(path, cv2)
        if cap is None:
            return None
        ok, frame = self._read_frame(cap, ms, cv2)
        if (not ok) or frame is None:
            cap = self._reopen_capture(path, cv2)
            if cap is None:
                return None
            ok, frame = self._read_frame(cap, ms, cv2)
            if (not ok) or frame is None:
                return None
        image = _qimage_from_bgr_frame(frame)
        if image is None or image.isNull():
            image = _qimage_from_rgb_frame(frame, cv2)
        if image is None or image.isNull():
            return None
        return _scale_image_to_width(image, max_width=max_width)

    def _ensure_capture(self, path: str, cv2_module):
        with self._cap_lock:
            if self._cap is None or self._cap_path != path:
                self._release_cap_locked()
                cap = cv2_module.VideoCapture(path)
                if not cap.isOpened():
                    try:
                        cap.release()
                    except RuntimeError:
                        logger.debug("focus review capture close skipped after open failure", exc_info=True)
                    return None
                self._cap = cap
                self._cap_path = path
            return self._cap

    def _reopen_capture(self, path: str, cv2_module):
        with self._cap_lock:
            self._release_cap_locked()
            cap = cv2_module.VideoCapture(path)
            if not cap.isOpened():
                try:
                    cap.release()
                except RuntimeError:
                    logger.debug("focus review capture reopen close skipped", exc_info=True)
                return None
            self._cap = cap
            self._cap_path = path
            return self._cap

    def _read_frame(self, cap, ms: int, cv2_module):
        cap.set(cv2_module.CAP_PROP_POS_MSEC, max(0, int(ms)))
        return cap.read()

    def _release_cap(self) -> None:
        with self._cap_lock:
            self._release_cap_locked()

    def _release_cap_locked(self) -> None:
        cap = self._cap
        self._cap = None
        self._cap_path = None
        if cap is not None:
            try:
                cap.release()
            except (AttributeError, RuntimeError):
                logger.debug("focus review capture release skipped", exc_info=True)


class FocusReviewMinimap(QtWidgets.QWidget):
    interactionStarted = QtCore.pyqtSignal()
    interactionFinished = QtCore.pyqtSignal()
    focusRectChanged = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame_image = QtGui.QImage()
        self._frame_pixmap = QtGui.QPixmap()
        self._focus_rect_norm = QtCore.QRectF(0.34, 0.34, 0.32, 0.32)
        self._dragging = False
        self._interaction_mode = ""
        self._interaction_start_rect = QtCore.QRectF(self._focus_rect_norm)
        self._drag_offset = QtCore.QPointF(0.16, 0.16)
        self._resize_margin_px = 8.0
        self.setMinimumSize(280, 180)
        self.setMouseTracking(True)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(360, 220)

    def set_frame_image(self, image: QtGui.QImage) -> None:
        self._frame_image = QtGui.QImage(image) if image is not None else QtGui.QImage()
        self._frame_pixmap = QtGui.QPixmap.fromImage(self._frame_image) if not self._frame_image.isNull() else QtGui.QPixmap()
        self.update()

    def set_focus_rect_norm(self, rect: QtCore.QRectF) -> None:
        normalized = _normalized_focus_rect(rect)
        if _rect_close(normalized, self._focus_rect_norm):
            return
        self._focus_rect_norm = normalized
        self.focusRectChanged.emit(QtCore.QRectF(self._focus_rect_norm))
        self.update()

    def focus_rect_norm(self) -> QtCore.QRectF:
        return QtCore.QRectF(self._focus_rect_norm)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QtGui.QColor(22, 26, 30))
        draw_rect = self._image_draw_rect()
        if self._frame_pixmap.isNull() or draw_rect.width() <= 0 or draw_rect.height() <= 0:
            painter.setPen(QtGui.QColor(150, 158, 168))
            painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, tr(self, "프레임 없음"))
            painter.end()
            return
        painter.drawPixmap(draw_rect, self._frame_pixmap, QtCore.QRectF(self._frame_pixmap.rect()))
        focus_rect = self._focus_rect_widget(draw_rect)
        shade = QtGui.QColor(0, 0, 0, 132)
        painter.fillRect(
            QtCore.QRectF(draw_rect.left(), draw_rect.top(), draw_rect.width(), max(0.0, focus_rect.top() - draw_rect.top())),
            shade,
        )
        painter.fillRect(
            QtCore.QRectF(draw_rect.left(), focus_rect.bottom(), draw_rect.width(), max(0.0, draw_rect.bottom() - focus_rect.bottom())),
            shade,
        )
        painter.fillRect(
            QtCore.QRectF(draw_rect.left(), focus_rect.top(), max(0.0, focus_rect.left() - draw_rect.left()), focus_rect.height()),
            shade,
        )
        painter.fillRect(
            QtCore.QRectF(focus_rect.right(), focus_rect.top(), max(0.0, draw_rect.right() - focus_rect.right()), focus_rect.height()),
            shade,
        )
        painter.setPen(QtGui.QPen(QtGui.QColor(240, 246, 252), 2))
        painter.drawRect(focus_rect)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(88, 188, 255))
        for point in (
            focus_rect.topLeft(),
            focus_rect.topRight(),
            focus_rect.bottomLeft(),
            focus_rect.bottomRight(),
        ):
            painter.drawEllipse(point, 4.0, 4.0)
        painter.end()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        draw_rect = self._image_draw_rect()
        if draw_rect.width() <= 0 or draw_rect.height() <= 0 or not draw_rect.contains(event.position()):
            super().mousePressEvent(event)
            return
        point_norm = self._widget_point_to_normalized(event.position(), draw_rect)
        mode = self._interaction_mode_for_pos(event.position(), draw_rect)
        rect = QtCore.QRectF(self._focus_rect_norm)
        if not rect.contains(point_norm) and not mode:
            rect.moveCenter(point_norm)
            rect = _normalized_focus_rect(rect)
            self._focus_rect_norm = rect
            self.focusRectChanged.emit(QtCore.QRectF(self._focus_rect_norm))
            self.update()
            mode = "move"
        if not mode:
            mode = "move"
        self._interaction_mode = mode
        self._interaction_start_rect = QtCore.QRectF(self._focus_rect_norm)
        self._drag_offset = point_norm - self._focus_rect_norm.topLeft()
        self._dragging = True
        self.interactionStarted.emit()
        event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if not self._dragging:
            self._update_hover_cursor(event.position())
            super().mouseMoveEvent(event)
            return
        draw_rect = self._image_draw_rect()
        point_norm = self._widget_point_to_normalized(event.position(), draw_rect)
        if self._interaction_mode == "move":
            rect = QtCore.QRectF(self._focus_rect_norm)
            rect.moveTopLeft(point_norm - self._drag_offset)
        else:
            rect = _resized_focus_rect(self._interaction_start_rect, self._interaction_mode, point_norm)
        self.set_focus_rect_norm(rect)
        event.accept()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._dragging and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._dragging = False
            self._interaction_mode = ""
            self.interactionFinished.emit()
            self._update_hover_cursor(event.position())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        if not self._dragging:
            self.unsetCursor()
        super().leaveEvent(event)

    def _image_draw_rect(self) -> QtCore.QRectF:
        if self._frame_pixmap.isNull():
            return QtCore.QRectF()
        size = QtCore.QSizeF(self._frame_pixmap.size())
        size.scale(QtCore.QSizeF(self.size()), QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        x = (self.width() - size.width()) / 2.0
        y = (self.height() - size.height()) / 2.0
        return QtCore.QRectF(x, y, size.width(), size.height())

    def _focus_rect_widget(self, draw_rect: QtCore.QRectF) -> QtCore.QRectF:
        return QtCore.QRectF(
            draw_rect.left() + (self._focus_rect_norm.x() * draw_rect.width()),
            draw_rect.top() + (self._focus_rect_norm.y() * draw_rect.height()),
            max(1.0, self._focus_rect_norm.width() * draw_rect.width()),
            max(1.0, self._focus_rect_norm.height() * draw_rect.height()),
        )

    def _widget_point_to_normalized(self, pos: QtCore.QPointF, draw_rect: QtCore.QRectF) -> QtCore.QPointF:
        if draw_rect.width() <= 0 or draw_rect.height() <= 0:
            return QtCore.QPointF(0.5, 0.5)
        x = (pos.x() - draw_rect.left()) / draw_rect.width()
        y = (pos.y() - draw_rect.top()) / draw_rect.height()
        return QtCore.QPointF(min(1.0, max(0.0, x)), min(1.0, max(0.0, y)))

    def _interaction_mode_for_pos(self, pos: QtCore.QPointF, draw_rect: QtCore.QRectF) -> str:
        focus_rect = self._focus_rect_widget(draw_rect)
        if focus_rect.width() <= 0 or focus_rect.height() <= 0:
            return ""
        margin = float(self._resize_margin_px)
        probe = focus_rect.adjusted(-margin, -margin, margin, margin)
        if not probe.contains(pos):
            return ""
        near_left = abs(pos.x() - focus_rect.left()) <= margin
        near_right = abs(pos.x() - focus_rect.right()) <= margin
        near_top = abs(pos.y() - focus_rect.top()) <= margin
        near_bottom = abs(pos.y() - focus_rect.bottom()) <= margin
        if near_left and near_top:
            return "top_left"
        if near_right and near_top:
            return "top_right"
        if near_left and near_bottom:
            return "bottom_left"
        if near_right and near_bottom:
            return "bottom_right"
        if near_left:
            return "left"
        if near_right:
            return "right"
        if near_top:
            return "top"
        if near_bottom:
            return "bottom"
        if focus_rect.contains(pos):
            return "move"
        return ""

    def _update_hover_cursor(self, pos: QtCore.QPointF) -> None:
        draw_rect = self._image_draw_rect()
        if draw_rect.width() <= 0 or draw_rect.height() <= 0:
            self.unsetCursor()
            return
        mode = self._interaction_mode_for_pos(pos, draw_rect)
        cursor = _cursor_for_interaction_mode(mode)
        if cursor is None:
            self.unsetCursor()
            return
        self.setCursor(cursor)


class FocusReviewPreviewViewport(QtWidgets.QFrame):
    doubleClicked = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._focus_rect_norm = QtCore.QRectF(0.34, 0.34, 0.32, 0.32)
        self._source_frame_size = QtCore.QSizeF(1920.0, 1080.0)
        self.setMinimumSize(420, 280)
        self.setStyleSheet("background: #11161c; border: 1px solid #26303a;")
        self._video_surface = QtWidgets.QWidget(self)
        self._video_surface.setAttribute(QtCore.Qt.WidgetAttribute.WA_NativeWindow, True)
        self._video_surface.setStyleSheet("background: #000; border: none;")
        self._video_surface.show()

    def video_surface(self) -> QtWidgets.QWidget:
        return self._video_surface

    def set_focus_rect_norm(self, rect: QtCore.QRectF) -> None:
        normalized = _normalized_focus_rect(rect)
        if _rect_close(normalized, self._focus_rect_norm):
            return
        self._focus_rect_norm = normalized
        self._update_video_surface_geometry()

    def set_source_frame_size(self, width: int, height: int) -> None:
        width_f = max(1.0, float(width))
        height_f = max(1.0, float(height))
        next_size = QtCore.QSizeF(width_f, height_f)
        if (
            abs(next_size.width() - self._source_frame_size.width()) < 1e-4
            and abs(next_size.height() - self._source_frame_size.height()) < 1e-4
        ):
            return
        self._source_frame_size = next_size
        self._update_video_surface_geometry()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_video_surface_geometry()

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.doubleClicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _update_video_surface_geometry(self) -> None:
        viewport_rect = QtCore.QRectF(self.rect())
        viewport_w = max(1.0, float(viewport_rect.width()))
        viewport_h = max(1.0, float(viewport_rect.height()))
        source_w = max(1.0, float(self._source_frame_size.width()))
        source_h = max(1.0, float(self._source_frame_size.height()))
        focus_rect = _normalized_focus_rect(self._focus_rect_norm)
        roi_w = max(1.0, source_w * max(0.01, float(focus_rect.width())))
        roi_h = max(1.0, source_h * max(0.01, float(focus_rect.height())))
        scale = min(viewport_w / roi_w, viewport_h / roi_h)
        render_w = max(1, int(round(source_w * scale)))
        render_h = max(1, int(round(source_h * scale)))
        max_dim = int(MAX_PREVIEW_SURFACE_DIMENSION)
        render_max_dim = max(render_w, render_h)
        if render_max_dim > max_dim and render_max_dim > 0:
            clamp_scale = float(max_dim) / float(render_max_dim)
            render_w = max(1, int(round(float(render_w) * clamp_scale)))
            render_h = max(1, int(round(float(render_h) * clamp_scale)))
        roi_screen_w = float(render_w) * max(0.01, float(focus_rect.width()))
        roi_screen_h = float(render_h) * max(0.01, float(focus_rect.height()))
        x = int(round((-float(focus_rect.x()) * float(render_w)) + ((viewport_w - roi_screen_w) / 2.0)))
        y = int(round((-float(focus_rect.y()) * float(render_h)) + ((viewport_h - roi_screen_h) / 2.0)))
        self._video_surface.setGeometry(x, y, render_w, render_h)

    def source_frame_size(self) -> QtCore.QSizeF:
        return QtCore.QSizeF(self._source_frame_size)

    def focus_rect_norm(self) -> QtCore.QRectF:
        return QtCore.QRectF(self._focus_rect_norm)


class FocusReviewPreviewHost(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._viewport = FocusReviewPreviewViewport(self)
        self._viewport.show()

    def viewport(self) -> FocusReviewPreviewViewport:
        return self._viewport

    def set_focus_rect_norm(self, rect: QtCore.QRectF) -> None:
        self._viewport.set_focus_rect_norm(rect)
        self._update_viewport_geometry()

    def set_source_frame_size(self, width: int, height: int) -> None:
        self._viewport.set_source_frame_size(width, height)
        self._update_viewport_geometry()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_viewport_geometry()

    def _update_viewport_geometry(self) -> None:
        available_rect = QtCore.QRectF(self.rect())
        if available_rect.width() <= 0 or available_rect.height() <= 0:
            self._viewport.setGeometry(self.rect())
            return
        source_size = self._viewport.source_frame_size()
        focus_rect = self._viewport.focus_rect_norm()
        source_w = max(1.0, float(source_size.width()))
        source_h = max(1.0, float(source_size.height()))
        roi_w = max(1.0, source_w * max(0.01, float(focus_rect.width())))
        roi_h = max(1.0, source_h * max(0.01, float(focus_rect.height())))
        available_aspect = available_rect.width() / max(1.0, available_rect.height())
        aspect = roi_w / roi_h if roi_h > 1e-6 else available_aspect
        focus_min_ratio = min(float(focus_rect.width()), float(focus_rect.height()))
        soften_start = float(PREVIEW_SMALL_FOCUS_SOFTEN_START)
        soften_end = float(PREVIEW_SMALL_FOCUS_SOFTEN_END)
        if soften_start > soften_end:
            soften = (focus_min_ratio - soften_end) / (soften_start - soften_end)
            soften = max(0.0, min(1.0, soften))
            aspect = available_aspect + ((aspect - available_aspect) * soften)
        min_aspect = available_aspect / float(PREVIEW_ASPECT_LIMIT_FACTOR)
        max_aspect = available_aspect * float(PREVIEW_ASPECT_LIMIT_FACTOR)
        aspect = max(min_aspect, min(max_aspect, aspect))
        target_w = available_rect.width()
        target_h = available_rect.height()
        if aspect > 1e-6:
            if (target_w / max(1.0, target_h)) > aspect:
                target_w = target_h * aspect
            else:
                target_h = target_w / aspect
        x = available_rect.left() + ((available_rect.width() - target_w) / 2.0)
        y = available_rect.top() + ((available_rect.height() - target_h) / 2.0)
        self._viewport.setGeometry(
            int(round(x)),
            int(round(y)),
            max(1, int(round(target_w))),
            max(1, int(round(target_h))),
        )


class FocusReviewPreviewFullscreen(QtWidgets.QDialog):
    closed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(QtCore.Qt.WindowType.Window, True)
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setStyleSheet("background: #000;")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._host = FocusReviewPreviewHost(self)
        self._host.viewport().setStyleSheet("background: #000; border: none;")
        self._host.viewport().doubleClicked.connect(self.close)
        layout.addWidget(self._host, 1)

    def preview_viewport(self) -> FocusReviewPreviewViewport:
        return self._host.viewport()

    def set_focus_rect_norm(self, rect: QtCore.QRectF) -> None:
        self._host.set_focus_rect_norm(rect)

    def set_source_frame_size(self, width: int, height: int) -> None:
        self._host.set_source_frame_size(width, height)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() in (int(QtCore.Qt.Key.Key_Escape), int(QtCore.Qt.Key.Key_F11)):
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.closed.emit()
        super().closeEvent(event)


class FocusReviewWindow(QtWidgets.QDialog):
    def __init__(self, tile, parent=None):
        super().__init__(parent if parent is not None else _dialog_parent_for_tile(tile))
        self._tile = tile
        self._snapshot_image = QtGui.QImage()
        self._current_preview_crop = QtGui.QImage()
        self._focus_rect_norm = QtCore.QRectF(getattr(tile, "_focus_review_rect_norm", QtCore.QRectF(0.34, 0.34, 0.32, 0.32)))
        self._drag_pause_requested = False
        self._snapshot_request_token = 0
        self._initial_snapshot_requested = False
        self._preview_fullscreen_dialog: Optional[FocusReviewPreviewFullscreen] = None
        self._preview_vlc_instance = None
        self._preview_player = None
        self._preview_media_path = ""
        self._preview_transform_mode = ""
        self._preview_last_target = None
        self._fullscreen_preview_vlc_instance = None
        self._fullscreen_preview_player = None
        self._fullscreen_preview_media_path = ""
        self._fullscreen_preview_transform_mode = ""
        self._fullscreen_preview_last_target = None
        self._frame_worker = FocusReviewFrameWorker(self)
        self._follow_timer = QtCore.QTimer(self)
        self._follow_timer.setInterval(120)
        self._follow_timer.timeout.connect(self._tick_follow_preview)
        self._build_ui()
        self._frame_worker.frameReady.connect(self._on_worker_frame_ready)
        self._frame_worker.start()
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowFlag(QtCore.Qt.WindowType.Window, True)
        self.resize(1040, 640)
        self._sync_title()
        self._minimap.set_focus_rect_norm(self._focus_rect_norm)
        self._minimap.interactionStarted.connect(self._on_minimap_interaction_started)
        self._minimap.interactionFinished.connect(self._on_minimap_interaction_finished)
        self._minimap.focusRectChanged.connect(self._on_focus_rect_changed)
        self._save_button.clicked.connect(self._save_current_preview)
        self._frameset_button.clicked.connect(self._tile.save_frame_set)
        self._gif_button.clicked.connect(self._export_gif_with_range)
        self._clip_button.clicked.connect(self._export_clip_with_range)
        self._fullscreen_button.clicked.connect(self._toggle_preview_fullscreen)
        self._preview_viewport.doubleClicked.connect(self._toggle_preview_fullscreen)
        self._range_start_now_button.clicked.connect(self._set_export_start_from_current)
        self._range_end_now_button.clicked.connect(self._set_export_end_from_current)
        self._range_start_edit.editingFinished.connect(self._normalize_export_range_inputs)
        self._range_end_edit.editingFinished.connect(self._normalize_export_range_inputs)
        try:
            tile.destroyed.connect(self.close)
        except Exception:
            logger.debug("focus review tile destroy hookup skipped", exc_info=True)
        self._sync_export_range_fields()
        self.refresh_snapshot_from_tile()
        self._tick_follow_preview()
        self._follow_timer.start()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        if self._initial_snapshot_requested:
            return
        self._initial_snapshot_requested = True
        QtCore.QTimer.singleShot(0, self.refresh_snapshot_from_tile)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if getattr(self._tile, "_focus_review_window", None) is self:
            self._tile._focus_review_window = None
        try:
            self._tile._focus_review_rect_norm = QtCore.QRectF(self._focus_rect_norm)
        except Exception:
            logger.debug("focus review rect persistence skipped on close", exc_info=True)
        try:
            self._follow_timer.stop()
        except Exception:
            pass
        try:
            self._frame_worker.stop()
        except Exception:
            logger.debug("focus review worker stop skipped", exc_info=True)
        self._release_preview_player()
        self._release_fullscreen_preview_player()
        try:
            if self._preview_fullscreen_dialog is not None:
                self._preview_fullscreen_dialog.close()
        except Exception:
            logger.debug("focus review fullscreen preview close skipped", exc_info=True)
        super().closeEvent(event)

    def refresh_snapshot_from_tile(self) -> None:
        source = self._current_source_info()
        if source is None:
            self._status_label.setText(tr(self, "로컬 영상 파일만 지원"))
            return
        self._status_label.setText(tr(self, "원본 프레임 갱신 중..."))
        self._request_snapshot_frame(source["path"], source["ms"])

    def _build_ui(self) -> None:
        self.setWindowTitle(tr(self, "포커스 검토"))
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        top_row = QtWidgets.QHBoxLayout()
        top_row.setSpacing(8)
        self._time_label = QtWidgets.QLabel("00:00:00")
        self._time_label.setMinimumWidth(90)
        self._save_button = QtWidgets.QPushButton(tr(self, "확대 보기 저장"), self)
        self._frameset_button = QtWidgets.QPushButton(tr(self, "프레임셋 저장"), self)
        self._gif_button = QtWidgets.QPushButton("GIF", self)
        self._clip_button = QtWidgets.QPushButton("Clip", self)
        self._fullscreen_button = QtWidgets.QPushButton(tr(self, "확대 보기 전체화면"), self)
        top_row.addWidget(self._save_button)
        top_row.addWidget(self._frameset_button)
        top_row.addWidget(self._gif_button)
        top_row.addWidget(self._clip_button)
        top_row.addWidget(self._fullscreen_button)
        top_row.addStretch(1)
        top_row.addWidget(self._time_label)
        root.addLayout(top_row)

        range_row = QtWidgets.QHBoxLayout()
        range_row.setSpacing(8)
        range_row.addWidget(QtWidgets.QLabel(tr(self, "GIF/Clip 구간"), self))
        range_row.addWidget(QtWidgets.QLabel(tr(self, "시작"), self))
        self._range_start_edit = QtWidgets.QLineEdit(self)
        self._range_start_edit.setMinimumWidth(112)
        range_row.addWidget(self._range_start_edit)
        self._range_start_now_button = QtWidgets.QPushButton(tr(self, "현재 -> 시작"), self)
        range_row.addWidget(self._range_start_now_button)
        range_row.addWidget(QtWidgets.QLabel("~", self))
        range_row.addWidget(QtWidgets.QLabel(tr(self, "끝"), self))
        self._range_end_edit = QtWidgets.QLineEdit(self)
        self._range_end_edit.setMinimumWidth(112)
        range_row.addWidget(self._range_end_edit)
        self._range_end_now_button = QtWidgets.QPushButton(tr(self, "현재 -> 끝"), self)
        range_row.addWidget(self._range_end_now_button)
        range_row.addStretch(1)
        root.addLayout(range_row)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        left = QtWidgets.QWidget(splitter)
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        left_layout.addWidget(QtWidgets.QLabel(tr(self, "원본 프레임"), left))
        self._minimap = FocusReviewMinimap(left)
        left_layout.addWidget(self._minimap, 1)
        tip = QtWidgets.QLabel(tr(self, "박스를 드래그해 이동하고, 테두리로 자유롭게 크기를 조절합니다."), left)
        tip.setStyleSheet("color: #6b7785;")
        tip.setWordWrap(True)
        left_layout.addWidget(tip)

        right = QtWidgets.QWidget(splitter)
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        right_layout.addWidget(QtWidgets.QLabel(tr(self, "확대 보기"), right))
        self._preview_host = FocusReviewPreviewHost(right)
        self._preview_viewport = self._preview_host.viewport()
        right_layout.addWidget(self._preview_host, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self._status_label = QtWidgets.QLabel("")
        self._status_label.setStyleSheet("color: #6b7785;")
        root.addWidget(self._status_label)

    def _current_source_info(self) -> Optional[dict]:
        tile = self._tile
        try:
            if bool(tile.is_static_image()):
                return None
        except Exception:
            return None
        try:
            path = str(tile._current_playlist_path() or "").strip()
        except Exception:
            path = ""
        if not path or not os.path.isfile(path):
            return None
        try:
            ms = int(tile.current_playback_ms())
        except Exception:
            ms = 0
        try:
            transform_mode = str(getattr(tile, "transform_mode", "none") or "none")
        except Exception:
            transform_mode = "none"
        return {
            "path": path,
            "ms": max(0, ms),
            "transform_mode": transform_mode,
        }

    def _sync_title(self) -> None:
        source = self._current_source_info()
        basename = os.path.basename(str(source["path"])) if source is not None else ""
        if basename:
            self.setWindowTitle(tr(self, "포커스 검토") + f" - {basename}")
        else:
            self.setWindowTitle(tr(self, "포커스 검토"))

    def _request_snapshot_frame(self, path: str, ms: int) -> None:
        if not path:
            return
        self._snapshot_request_token += 1
        token = self._snapshot_request_token
        self._frame_worker.request_frame(
            {
                "path": path,
                "ms": max(0, int(ms)),
                "token": token,
                "transform_mode": str(getattr(self._tile, "transform_mode", "none") or "none"),
                "max_width": SNAPSHOT_REFRESH_MAX_WIDTH,
            }
        )

    def _on_worker_frame_ready(self, payload: dict) -> None:
        image = payload.get("image")
        token = int(payload.get("token", 0) or 0)
        if not isinstance(image, QtGui.QImage) or image.isNull():
            self._status_label.setText(tr(self, "프레임 추출 실패"))
            return
        if token != self._snapshot_request_token:
            return
        self._snapshot_image = QtGui.QImage(image)
        self._minimap.set_frame_image(self._snapshot_image)
        self._preview_host.set_source_frame_size(self._snapshot_image.width(), self._snapshot_image.height())
        self._status_label.setText(tr(self, "원본 프레임 고정됨"))
        self._update_preview_from_image(self._snapshot_image)

    def _tick_follow_preview(self) -> None:
        if self._minimap._dragging:
            return
        source = self._current_source_info()
        self._sync_title()
        if source is None:
            self._status_label.setText(tr(self, "로컬 영상 파일만 지원"))
            self._release_preview_player()
            self._release_fullscreen_preview_player()
            return
        self._time_label.setText(_format_ms_clock(int(source["ms"])))
        self._sync_preview_player(source)
        self._sync_fullscreen_preview_player(source)

    def _on_focus_rect_changed(self, rect: QtCore.QRectF) -> None:
        self._focus_rect_norm = _normalized_focus_rect(rect)
        try:
            self._tile._focus_review_rect_norm = QtCore.QRectF(self._focus_rect_norm)
        except Exception:
            logger.debug("focus review rect persistence skipped", exc_info=True)
        self._preview_host.set_focus_rect_norm(self._focus_rect_norm)
        self._sync_fullscreen_preview()
        if not self._snapshot_image.isNull():
            self._update_preview_from_image(self._snapshot_image)

    def _on_minimap_interaction_started(self) -> None:
        self.refresh_snapshot_from_tile()
        try:
            playing = bool(self._tile.mediaplayer.is_playing())
        except Exception:
            playing = False
        self._drag_pause_requested = playing
        if playing:
            try:
                self._tile.pause()
            except Exception:
                logger.debug("focus review pause skipped", exc_info=True)
        self._status_label.setText(tr(self, "박스 조절 중"))

    def _on_minimap_interaction_finished(self) -> None:
        if self._drag_pause_requested:
            try:
                self._tile.play()
            except Exception:
                logger.debug("focus review resume skipped", exc_info=True)
        self._drag_pause_requested = False
        self._tick_follow_preview()
        self._status_label.setText(tr(self, "재생 추적 중"))

    def _update_preview_from_image(self, image: QtGui.QImage) -> None:
        if image is None or image.isNull():
            self._current_preview_crop = QtGui.QImage()
            self._sync_fullscreen_preview()
            return
        self._preview_host.set_source_frame_size(image.width(), image.height())
        crop = _crop_focus_region(image, self._focus_rect_norm)
        if crop.isNull():
            self._current_preview_crop = QtGui.QImage()
            self._sync_fullscreen_preview()
            return
        self._current_preview_crop = QtGui.QImage(crop)
        self._sync_fullscreen_preview()

    def _active_preview_crop(self) -> QtGui.QImage:
        if not self._current_preview_crop.isNull():
            return QtGui.QImage(self._current_preview_crop)
        if self._snapshot_image.isNull():
            return QtGui.QImage()
        return _crop_focus_region(self._snapshot_image, self._focus_rect_norm)

    def _dialog_start_dir(self) -> str:
        mainwin = getattr(self._tile, "_main_window", lambda: None)()
        if mainwin is not None:
            try:
                return mainwin.config.get("last_dir", "") or os.path.expanduser("~")
            except Exception:
                logger.debug("focus review dialog start dir lookup skipped", exc_info=True)
        return os.path.expanduser("~")

    def _remember_dialog_dir(self, path: str) -> None:
        if not path:
            return
        mainwin = getattr(self._tile, "_main_window", lambda: None)()
        if mainwin is None:
            return
        try:
            mainwin.config["last_dir"] = os.path.dirname(path) or path
        except Exception:
            logger.debug("focus review dialog dir persist skipped", exc_info=True)
        try:
            if hasattr(mainwin, "last_dir"):
                mainwin.last_dir = os.path.dirname(path) or path
        except Exception:
            logger.debug("focus review last_dir attr update skipped", exc_info=True)

    def _current_media_length_ms(self) -> int:
        try:
            length_ms = int(self._tile.mediaplayer.get_length() or 0)
        except Exception:
            length_ms = 0
        if length_ms > 0:
            return max(0, length_ms)
        source = self._current_source_info()
        path = str((source or {}).get("path") or "")
        if not path or not os.path.isfile(path):
            return 0
        try:
            import cv2  # type: ignore

            cap = cv2.VideoCapture(path)
            if not cap.isOpened():
                cap.release()
                return 0
            try:
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                total_frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
            finally:
                cap.release()
            if fps > 1e-6 and total_frames > 1.0:
                return max(0, int(round((total_frames / fps) * 1000.0)))
        except Exception:
            logger.debug("focus review media length probe skipped", exc_info=True)
        return 0

    def _default_export_range_ms(self) -> tuple[int, int]:
        source = self._current_source_info() or {}
        current_ms = max(0, int(source.get("ms", 0) or 0))
        length_ms = self._current_media_length_ms()
        start_ms = current_ms
        end_ms = current_ms + 3000
        if length_ms > 0:
            start_ms = min(start_ms, max(0, length_ms - 1))
            end_ms = min(length_ms, end_ms)
            if end_ms <= start_ms:
                start_ms = max(0, min(start_ms, max(0, length_ms - 1000)))
                end_ms = min(length_ms, start_ms + 1000)
        if end_ms <= start_ms:
            end_ms = start_ms + 1000
        return start_ms, end_ms

    def _tile_ab_range_ms(self) -> Optional[tuple[int, int]]:
        pos_a = getattr(self._tile, "posA", None)
        pos_b = getattr(self._tile, "posB", None)
        if pos_a is None or pos_b is None:
            return None
        length_ms = self._current_media_length_ms()
        if length_ms <= 0:
            return None
        start_pos = max(0.0, min(1.0, float(pos_a)))
        end_pos = max(0.0, min(1.0, float(pos_b)))
        if end_pos < start_pos:
            start_pos, end_pos = end_pos, start_pos
        start_ms = max(0, int(round(start_pos * float(length_ms))))
        end_ms = max(start_ms + 1, int(round(end_pos * float(length_ms))))
        return start_ms, end_ms

    def _sync_export_range_fields(self) -> None:
        start_ms, end_ms = self._tile_ab_range_ms() or self._default_export_range_ms()
        self._set_export_range_fields(start_ms, end_ms)

    def _set_export_range_fields(self, start_ms: int, end_ms: int) -> None:
        self._range_start_edit.setText(_format_timecode_input(start_ms))
        self._range_end_edit.setText(_format_timecode_input(end_ms))

    def _normalize_export_range_inputs(self) -> None:
        clip_range = self._export_range_ms_from_fields(show_error=False)
        if clip_range is None:
            return
        self._set_export_range_fields(clip_range[0], clip_range[1])

    def _export_range_ms_from_fields(self, *, show_error: bool) -> Optional[tuple[int, int]]:
        try:
            start_ms = _parse_timecode_ms(self._range_start_edit.text())
            end_ms = _parse_timecode_ms(self._range_end_edit.text())
        except ValueError:
            if show_error:
                QtWidgets.QMessageBox.warning(
                    self,
                    tr(self, "구간 설정"),
                    tr(self, "잘못된 시간 형식입니다.\n예: 01:23 / 00:01:23 / 00:01:23.450"),
                )
            return None
        length_ms = self._current_media_length_ms()
        if length_ms > 0:
            start_ms = min(start_ms, max(0, length_ms - 1))
            end_ms = min(end_ms, length_ms)
        if end_ms <= start_ms:
            if show_error:
                QtWidgets.QMessageBox.warning(self, tr(self, "구간 설정"), tr(self, "끝 시간이 시작 시간보다 뒤여야 합니다."))
            return None
        return start_ms, end_ms

    def _set_export_start_from_current(self) -> None:
        source = self._current_source_info()
        if source is None:
            return
        start_ms = max(0, int(source.get("ms", 0) or 0))
        existing = self._export_range_ms_from_fields(show_error=False) or self._default_export_range_ms()
        end_ms = max(existing[1], start_ms + 1)
        length_ms = self._current_media_length_ms()
        if length_ms > 0:
            start_ms = min(start_ms, max(0, length_ms - 1))
            end_ms = min(length_ms, max(end_ms, start_ms + 1))
            if end_ms <= start_ms:
                end_ms = min(length_ms, start_ms + 1000)
        self._set_export_range_fields(start_ms, end_ms)

    def _set_export_end_from_current(self) -> None:
        source = self._current_source_info()
        if source is None:
            return
        end_ms = max(0, int(source.get("ms", 0) or 0))
        existing = self._export_range_ms_from_fields(show_error=False) or self._default_export_range_ms()
        start_ms = min(existing[0], max(0, end_ms - 1))
        if end_ms <= start_ms:
            start_ms = max(0, end_ms - 1000)
        length_ms = self._current_media_length_ms()
        if length_ms > 0:
            end_ms = min(end_ms, length_ms)
        if end_ms <= start_ms:
            end_ms = start_ms + 1000
        self._set_export_range_fields(start_ms, end_ms)

    def _restore_tile_ab_state(self, previous_state: tuple[object, object, bool]) -> None:
        prev_pos_a, prev_pos_b, prev_loop_enabled = previous_state
        self._tile.posA = prev_pos_a
        self._tile.posB = prev_pos_b
        self._tile.loop_enabled = bool(prev_loop_enabled) and prev_pos_a is not None and prev_pos_b is not None
        try:
            self._tile._update_ab_controls()
        except Exception:
            logger.debug("focus review A/B restore controls skipped", exc_info=True)

    def _run_export_with_range(self, export_action) -> None:
        source = self._current_source_info()
        if source is None:
            QtWidgets.QMessageBox.information(self, tr(self, "포커스 검토"), tr(self, "로컬 영상 파일만 지원"))
            return
        clip_range = self._export_range_ms_from_fields(show_error=True)
        if clip_range is None:
            return
        self._set_export_range_fields(clip_range[0], clip_range[1])
        previous_state = (getattr(self._tile, "posA", None), getattr(self._tile, "posB", None), bool(getattr(self._tile, "loop_enabled", False)))
        try:
            if not bool(self._tile.set_ab_range_ms(int(clip_range[0]), int(clip_range[1]), seek_to_start=False)):
                QtWidgets.QMessageBox.warning(self, tr(self, "구간 설정"), tr(self, "구간을 A/B로 적용하지 못했습니다."))
                return
            export_action()
        finally:
            self._restore_tile_ab_state(previous_state)

    def _export_gif_with_range(self) -> None:
        self._run_export_with_range(self._tile.export_gif)

    def _export_clip_with_range(self) -> None:
        self._run_export_with_range(self._tile.export_clip)

    def _save_current_preview(self) -> None:
        crop = self._extract_save_crop()
        if crop.isNull():
            QtWidgets.QMessageBox.information(self, tr(self, "포커스 검토"), tr(self, "저장할 확대 보기가 없습니다."))
            return
        source = self._current_source_info() or {}
        default_name = _default_review_filename(str(source.get("path") or ""), int(source.get("ms", 0) or 0))
        default_path = os.path.join(self._dialog_start_dir(), default_name)
        path, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            tr(self, "확대 보기 저장"),
            default_path,
            tr(self, "이미지 파일 (*.png *.jpg *.jpeg)"),
        )
        if not path:
            return
        path = _ensure_image_extension(path, selected_filter)
        fmt = _image_format_for_path(path)
        if not bool(crop.save(path, fmt)):
            QtWidgets.QMessageBox.warning(self, tr(self, "포커스 검토"), tr(self, "확대 보기 저장에 실패했습니다."))
            return
        self._remember_dialog_dir(path)
        self._status_label.setText(tr(self, "확대 보기 저장: {path}", path=path))

    def _extract_save_crop(self) -> QtGui.QImage:
        source = self._current_source_info()
        if source is not None:
            image = _extract_focus_review_frame_once(
                str(source.get("path") or ""),
                int(source.get("ms", 0) or 0),
                max_width=0,
                transform_mode=str(source.get("transform_mode", "none") or "none"),
            )
            if not image.isNull():
                crop = _crop_focus_region(image, self._focus_rect_norm)
                if not crop.isNull():
                    return crop
        return self._active_preview_crop()

    def _toggle_preview_fullscreen(self) -> None:
        source = self._current_source_info()
        if source is None:
            QtWidgets.QMessageBox.information(self, tr(self, "포커스 검토"), tr(self, "로컬 영상 파일만 지원"))
            return
        dialog = self._ensure_preview_fullscreen_dialog()
        if dialog.isVisible():
            dialog.close()
            return
        self._sync_fullscreen_preview()
        dialog.showFullScreen()
        dialog.raise_()
        dialog.activateWindow()
        self._sync_fullscreen_preview_player(source)
        QtCore.QTimer.singleShot(0, self._tick_follow_preview)
        QtCore.QTimer.singleShot(120, self._tick_follow_preview)

    def _ensure_preview_fullscreen_dialog(self) -> FocusReviewPreviewFullscreen:
        dialog = self._preview_fullscreen_dialog
        if dialog is None:
            dialog = FocusReviewPreviewFullscreen(self)
            dialog.closed.connect(self._on_preview_fullscreen_closed)
            dialog.destroyed.connect(lambda *_args, owner=self: setattr(owner, "_preview_fullscreen_dialog", None))
            self._preview_fullscreen_dialog = dialog
        return dialog

    def _sync_fullscreen_preview(self) -> None:
        dialog = self._preview_fullscreen_dialog
        if dialog is None:
            return
        source_size = self._preview_source_size()
        dialog.set_source_frame_size(source_size.width(), source_size.height())
        dialog.set_focus_rect_norm(self._focus_rect_norm)

    def _on_preview_fullscreen_closed(self) -> None:
        self._release_fullscreen_preview_player()
        self._tick_follow_preview()

    def _preview_target(self):
        viewport = getattr(self, "_preview_viewport", None)
        if viewport is None:
            return None
        return self._target_for_surface(viewport.video_surface())

    def _fullscreen_preview_target(self):
        dialog = self._preview_fullscreen_dialog
        if dialog is None or not dialog.isVisible():
            return None
        return self._target_for_surface(dialog.preview_viewport().video_surface())

    def _target_for_surface(self, video_surface):
        try:
            winid = int(video_surface.winId())
        except Exception:
            return None
        if sys.platform.startswith("linux"):
            return ("xwindow", winid)
        if sys.platform == "win32":
            return ("hwnd", winid)
        if sys.platform == "darwin":
            return ("nsobject", winid)
        return ("generic", winid)

    def _bind_preview_target(self, force: bool = False) -> None:
        player = self._preview_player
        if player is None:
            return
        target = self._preview_target()
        if target is None:
            return
        self._bind_player_target(player, target, cache_attr="_preview_last_target", force=force)

    def _bind_fullscreen_preview_target(self, force: bool = False) -> None:
        player = self._fullscreen_preview_player
        if player is None:
            return
        target = self._fullscreen_preview_target()
        if target is None:
            return
        self._bind_player_target(player, target, cache_attr="_fullscreen_preview_last_target", force=force)

    def _bind_player_target(self, player, target, *, cache_attr: str, force: bool = False) -> None:
        if player is None or target is None:
            return
        if (not force) and getattr(self, cache_attr, None) == target:
            return
        kind, winid = target
        try:
            if kind == "xwindow":
                player.set_xwindow(winid)
            elif kind == "hwnd":
                player.set_hwnd(winid)
            elif kind == "nsobject":
                player.set_nsobject(winid)
        except Exception:
            logger.debug("focus review preview target bind skipped", exc_info=True)
        setattr(self, cache_attr, target)

    def _release_preview_player(self) -> None:
        player = self._preview_player
        self._preview_player = None
        self._preview_media_path = ""
        self._preview_transform_mode = ""
        self._preview_last_target = None
        if player is not None:
            for action in (player.stop, lambda: player.set_media(None), player.release):
                try:
                    action()
                except Exception:
                    logger.debug("focus review preview player release step skipped", exc_info=True)
        instance = self._preview_vlc_instance
        self._preview_vlc_instance = None
        if instance is not None:
            try:
                instance.release()
            except Exception:
                logger.debug("focus review preview instance release skipped", exc_info=True)

    def _ensure_preview_player(self, transform_mode: str):
        transform_mode = str(transform_mode or "none")
        if self._preview_player is not None and self._preview_vlc_instance is not None and self._preview_transform_mode == transform_mode:
            self._bind_preview_target()
            return self._preview_player
        self._release_preview_player()
        try:
            if transform_mode == "none":
                args = tuple(self._tile._vlc_base_instance_args())
            else:
                args = tuple(self._tile._transform_instance_args(transform_mode))
            self._preview_vlc_instance = vlc.Instance(*args)
            self._preview_player = self._preview_vlc_instance.media_player_new()
            for setter in (self._preview_player.video_set_mouse_input, self._preview_player.video_set_key_input):
                try:
                    setter(False)
                except Exception:
                    pass
            try:
                self._preview_player.audio_set_mute(True)
            except Exception:
                pass
            self._preview_transform_mode = transform_mode
            self._bind_preview_target(force=True)
            return self._preview_player
        except Exception:
            logger.warning("focus review preview player init failed", exc_info=True)
            self._release_preview_player()
            return None

    def _pause_preview_player(self, player, context: str) -> None:
        try:
            player.set_pause(1)
            return
        except Exception:
            logger.debug("%s set_pause skipped", context, exc_info=True)
        try:
            if bool(player.is_playing()):
                player.pause()
        except Exception:
            logger.debug("%s pause fallback skipped", context, exc_info=True)

    def _start_preview_player(self, player, context: str) -> bool:
        try:
            player.play()
            return True
        except Exception:
            logger.debug("%s play skipped", context, exc_info=True)
            return False

    def _open_preview_media(self, path: str, transform_mode: str, *, source_playing: bool) -> bool:
        player = self._ensure_preview_player(transform_mode)
        if player is None or self._preview_vlc_instance is None:
            return False
        try:
            media = self._preview_vlc_instance.media_new(path)
            player.set_media(media)
            self._bind_preview_target(force=True)
            self._preview_media_path = str(path or "")
            try:
                player.audio_set_mute(True)
            except Exception:
                pass
            self._start_preview_player(
                player,
                "focus review preview player initial play"
                if source_playing
                else "focus review preview player initial prime",
            )
            return True
        except Exception:
            logger.warning("focus review preview media open failed", exc_info=True)
            self._preview_media_path = ""
            return False

    def _sync_preview_player(self, source: dict) -> None:
        path = str(source.get("path") or "")
        if not path:
            self._release_preview_player()
            return
        transform_mode = str(source.get("transform_mode", "none") or "none")
        self._preview_host.set_focus_rect_norm(self._focus_rect_norm)
        source_size = self._preview_source_size()
        self._preview_host.set_source_frame_size(source_size.width(), source_size.height())
        self._sync_fullscreen_preview()
        player = self._ensure_preview_player(transform_mode)
        if player is None:
            return
        self._bind_preview_target()
        try:
            source_playing = bool(self._tile.mediaplayer.is_playing())
        except Exception:
            source_playing = False
        if self._preview_media_path != path:
            if not self._open_preview_media(path, transform_mode, source_playing=source_playing):
                return
            player = self._preview_player
            if player is None:
                return
        target_ms = max(0, int(source.get("ms", 0) or 0))
        try:
            player.set_rate(float(getattr(self._tile, "playback_rate", 1.0) or 1.0))
        except Exception:
            pass
        try:
            preview_ms = int(player.get_time() or 0)
        except Exception:
            preview_ms = 0
        drift = abs(int(preview_ms) - int(target_ms))
        try:
            preview_playing = bool(player.is_playing())
        except Exception:
            preview_playing = False
        if source_playing:
            if not preview_playing:
                try:
                    player.play()
                except Exception:
                    logger.debug("focus review preview play skipped during sync", exc_info=True)
            if drift > 250:
                try:
                    player.set_time(target_ms)
                except Exception:
                    logger.debug("focus review preview seek skipped during play sync", exc_info=True)
        else:
            if drift > 80:
                try:
                    player.set_time(target_ms)
                except Exception:
                    logger.debug("focus review preview seek skipped during pause sync", exc_info=True)
            self._pause_preview_player(player, "focus review preview pause sync")

    def _release_fullscreen_preview_player(self) -> None:
        player = self._fullscreen_preview_player
        self._fullscreen_preview_player = None
        self._fullscreen_preview_media_path = ""
        self._fullscreen_preview_transform_mode = ""
        self._fullscreen_preview_last_target = None
        if player is not None:
            for action in (player.stop, lambda: player.set_media(None), player.release):
                try:
                    action()
                except Exception:
                    logger.debug("focus review fullscreen preview player release step skipped", exc_info=True)
        instance = self._fullscreen_preview_vlc_instance
        self._fullscreen_preview_vlc_instance = None
        if instance is not None:
            try:
                instance.release()
            except Exception:
                logger.debug("focus review fullscreen preview instance release skipped", exc_info=True)

    def _ensure_fullscreen_preview_player(self, transform_mode: str):
        transform_mode = str(transform_mode or "none")
        if (
            self._fullscreen_preview_player is not None
            and self._fullscreen_preview_vlc_instance is not None
            and self._fullscreen_preview_transform_mode == transform_mode
        ):
            self._bind_fullscreen_preview_target()
            return self._fullscreen_preview_player
        self._release_fullscreen_preview_player()
        try:
            if transform_mode == "none":
                args = tuple(self._tile._vlc_base_instance_args())
            else:
                args = tuple(self._tile._transform_instance_args(transform_mode))
            self._fullscreen_preview_vlc_instance = vlc.Instance(*args)
            self._fullscreen_preview_player = self._fullscreen_preview_vlc_instance.media_player_new()
            for setter in (self._fullscreen_preview_player.video_set_mouse_input, self._fullscreen_preview_player.video_set_key_input):
                try:
                    setter(False)
                except Exception:
                    pass
            try:
                self._fullscreen_preview_player.audio_set_mute(True)
            except Exception:
                pass
            self._fullscreen_preview_transform_mode = transform_mode
            self._bind_fullscreen_preview_target(force=True)
            return self._fullscreen_preview_player
        except Exception:
            logger.warning("focus review fullscreen preview player init failed", exc_info=True)
            self._release_fullscreen_preview_player()
            return None

    def _open_fullscreen_preview_media(self, path: str, transform_mode: str, *, source_playing: bool) -> bool:
        player = self._ensure_fullscreen_preview_player(transform_mode)
        if player is None or self._fullscreen_preview_vlc_instance is None:
            return False
        try:
            media = self._fullscreen_preview_vlc_instance.media_new(path)
            player.set_media(media)
            self._bind_fullscreen_preview_target(force=True)
            self._fullscreen_preview_media_path = str(path or "")
            try:
                player.audio_set_mute(True)
            except Exception:
                pass
            self._start_preview_player(
                player,
                "focus review fullscreen preview player initial play"
                if source_playing
                else "focus review fullscreen preview player initial prime",
            )
            return True
        except Exception:
            logger.warning("focus review fullscreen preview media open failed", exc_info=True)
            self._fullscreen_preview_media_path = ""
            return False

    def _sync_fullscreen_preview_player(self, source: dict) -> None:
        dialog = self._preview_fullscreen_dialog
        if dialog is None or not dialog.isVisible():
            self._release_fullscreen_preview_player()
            return
        path = str(source.get("path") or "")
        if not path:
            self._release_fullscreen_preview_player()
            return
        transform_mode = str(source.get("transform_mode", "none") or "none")
        self._sync_fullscreen_preview()
        source_size = self._preview_source_size()
        player = self._ensure_fullscreen_preview_player(transform_mode)
        if player is None:
            return
        self._bind_fullscreen_preview_target()
        try:
            source_playing = bool(self._tile.mediaplayer.is_playing())
        except Exception:
            source_playing = False
        if self._fullscreen_preview_media_path != path:
            if not self._open_fullscreen_preview_media(path, transform_mode, source_playing=source_playing):
                return
            player = self._fullscreen_preview_player
            if player is None:
                return
        target_ms = max(0, int(source.get("ms", 0) or 0))
        try:
            player.set_rate(float(getattr(self._tile, "playback_rate", 1.0) or 1.0))
        except Exception:
            pass
        try:
            preview_ms = int(player.get_time() or 0)
        except Exception:
            preview_ms = 0
        drift = abs(int(preview_ms) - int(target_ms))
        try:
            preview_playing = bool(player.is_playing())
        except Exception:
            preview_playing = False
        if source_playing:
            if not preview_playing:
                try:
                    player.play()
                except Exception:
                    logger.debug("focus review fullscreen preview play skipped during sync", exc_info=True)
            if drift > 250:
                try:
                    player.set_time(target_ms)
                except Exception:
                    logger.debug("focus review fullscreen preview seek skipped during play sync", exc_info=True)
        else:
            if drift > 80:
                try:
                    player.set_time(target_ms)
                except Exception:
                    logger.debug("focus review fullscreen preview seek skipped during pause sync", exc_info=True)
            self._pause_preview_player(player, "focus review fullscreen preview pause sync")
    def _preview_source_size(self) -> QtCore.QSize:
        if not self._snapshot_image.isNull():
            return self._snapshot_image.size()
        try:
            size_info = self._tile.mediaplayer.video_get_size(0)
            if isinstance(size_info, (tuple, list)) and len(size_info) >= 2:
                width = max(1, int(size_info[0] or 0))
                height = max(1, int(size_info[1] or 0))
                if width > 0 and height > 0:
                    return QtCore.QSize(width, height)
        except Exception:
            logger.debug("focus review preview source size lookup skipped", exc_info=True)
        return QtCore.QSize(1920, 1080)


def _dialog_parent_for_tile(tile):
    try:
        main_window_getter = getattr(tile, "_main_window", None)
        if callable(main_window_getter):
            main_window = main_window_getter()
            if isinstance(main_window, QtWidgets.QWidget):
                return main_window
    except Exception:
        pass
    try:
        window = tile.window()
        if isinstance(window, QtWidgets.QWidget) and hasattr(window, "config"):
            return window
    except Exception:
        pass
    return None


def reanchor_focus_review_window(tile) -> None:
    window = getattr(tile, "_focus_review_window", None)
    if not isinstance(window, QtWidgets.QWidget):
        return
    try:
        target_parent = _dialog_parent_for_tile(tile)
    except Exception:
        return
    try:
        current_parent = window.parentWidget()
    except RuntimeError:
        tile._focus_review_window = None
        return
    if current_parent is target_parent:
        return
    try:
        was_visible = bool(window.isVisible())
        geometry = QtCore.QRect(window.geometry())
        window.setParent(target_parent, window.windowFlags() | QtCore.Qt.WindowType.Window)
        window.setWindowFlag(QtCore.Qt.WindowType.Window, True)
        if geometry.isValid():
            window.setGeometry(geometry)
        if was_visible:
            window.show()
            window.raise_()
            window.activateWindow()
    except RuntimeError:
        tile._focus_review_window = None


def _format_ms_clock(ms: int) -> str:
    total_seconds = max(0, int(ms)) // 1000
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _default_review_filename(path: str, ms: int) -> str:
    base = os.path.splitext(os.path.basename(path or ""))[0].strip() or "focus_review"
    return f"{base}_focus_{_format_ms_clock(ms).replace(':', '-')}.png"


def _format_timecode_input(ms: int) -> str:
    total_ms = max(0, int(ms))
    total_seconds, millis = divmod(total_ms, 1000)
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    base = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    if millis <= 0:
        return base
    return f"{base}.{millis:03d}"


def _parse_timecode_ms(text: str) -> int:
    raw = str(text or "").strip().replace(",", ".")
    if not raw:
        raise ValueError("empty")
    if ":" not in raw:
        seconds_value = float(raw)
        if seconds_value < 0:
            raise ValueError("negative")
        return int(round(seconds_value * 1000.0))
    parts = raw.split(":")
    if len(parts) > 3:
        raise ValueError("too many parts")
    try:
        seconds_value = float(parts[-1])
        minutes_value = int(parts[-2]) if len(parts) >= 2 else 0
        hours_value = int(parts[-3]) if len(parts) >= 3 else 0
    except Exception as exc:
        raise ValueError("invalid") from exc
    if min(seconds_value, float(minutes_value), float(hours_value)) < 0:
        raise ValueError("negative")
    total_ms = int(round((hours_value * 3600.0 + minutes_value * 60.0 + seconds_value) * 1000.0))
    return max(0, total_ms)


def _ensure_image_extension(path: str, selected_filter: str) -> str:
    root, ext = os.path.splitext(path)
    if ext:
        return path
    filter_text = str(selected_filter or "").lower()
    if "jpg" in filter_text or "jpeg" in filter_text:
        return root + ".jpg"
    return root + ".png"


def _image_format_for_path(path: str) -> str:
    suffix = os.path.splitext(path)[1].lower()
    if suffix in {".jpg", ".jpeg"}:
        return "JPG"
    return "PNG"


def _normalized_focus_rect(rect: QtCore.QRectF) -> QtCore.QRectF:
    width = min(1.0, max(0.01, float(rect.width())))
    height = min(1.0, max(0.01, float(rect.height())))
    x = min(1.0 - width, max(0.0, float(rect.x())))
    y = min(1.0 - height, max(0.0, float(rect.y())))
    return QtCore.QRectF(x, y, width, height)


def _rect_close(left: QtCore.QRectF, right: QtCore.QRectF) -> bool:
    return (
        abs(left.x() - right.x()) < 1e-4
        and abs(left.y() - right.y()) < 1e-4
        and abs(left.width() - right.width()) < 1e-4
        and abs(left.height() - right.height()) < 1e-4
    )


def _crop_focus_region(image: QtGui.QImage, rect_norm: QtCore.QRectF) -> QtGui.QImage:
    rect = _normalized_focus_rect(rect_norm)
    width = max(1, image.width())
    height = max(1, image.height())
    x = int(round(rect.x() * width))
    y = int(round(rect.y() * height))
    w = max(1, int(round(rect.width() * width)))
    h = max(1, int(round(rect.height() * height)))
    bounded = QtCore.QRect(x, y, w, h).intersected(image.rect())
    if bounded.width() <= 0 or bounded.height() <= 0:
        return QtGui.QImage()
    return image.copy(bounded)


def _resized_focus_rect(base_rect: QtCore.QRectF, mode: str, point_norm: QtCore.QPointF) -> QtCore.QRectF:
    left = float(base_rect.left())
    top = float(base_rect.top())
    right = float(base_rect.right())
    bottom = float(base_rect.bottom())
    if "left" in mode:
        left = float(point_norm.x())
    if "right" in mode:
        right = float(point_norm.x())
    if "top" in mode:
        top = float(point_norm.y())
    if "bottom" in mode:
        bottom = float(point_norm.y())
    rect = QtCore.QRectF(
        QtCore.QPointF(min(left, right), min(top, bottom)),
        QtCore.QPointF(max(left, right), max(top, bottom)),
    )
    return _normalized_focus_rect(rect)


def _cursor_for_interaction_mode(mode: str):
    if mode == "move":
        return QtCore.Qt.CursorShape.SizeAllCursor
    if mode in {"left", "right"}:
        return QtCore.Qt.CursorShape.SizeHorCursor
    if mode in {"top", "bottom"}:
        return QtCore.Qt.CursorShape.SizeVerCursor
    if mode in {"top_left", "bottom_right"}:
        return QtCore.Qt.CursorShape.SizeFDiagCursor
    if mode in {"top_right", "bottom_left"}:
        return QtCore.Qt.CursorShape.SizeBDiagCursor
    return None


def _scale_image_to_width(image: QtGui.QImage, *, max_width: int) -> QtGui.QImage:
    if int(max_width) <= 0:
        return QtGui.QImage(image)
    target_width = max(240, int(max_width))
    if image.width() <= target_width:
        return QtGui.QImage(image)
    return image.scaledToWidth(target_width, QtCore.Qt.TransformationMode.SmoothTransformation)


def _apply_transform_mode_to_image(image: QtGui.QImage, mode: str) -> QtGui.QImage:
    normalized = str(mode or "none")
    if normalized == "none":
        return QtGui.QImage(image)
    transformed = QtGui.QImage(image)
    if normalized == "hflip":
        return transformed.mirrored(True, False)
    if normalized == "vflip":
        return transformed.mirrored(False, True)
    if normalized == "180":
        return transformed.transformed(QtGui.QTransform().rotate(180), QtCore.Qt.TransformationMode.SmoothTransformation)
    if normalized == "90":
        return transformed.transformed(QtGui.QTransform().rotate(90), QtCore.Qt.TransformationMode.SmoothTransformation)
    if normalized == "270":
        return transformed.transformed(QtGui.QTransform().rotate(270), QtCore.Qt.TransformationMode.SmoothTransformation)
    if normalized == "transpose":
        rotated = transformed.transformed(QtGui.QTransform().rotate(90), QtCore.Qt.TransformationMode.SmoothTransformation)
        return rotated.mirrored(True, False)
    if normalized == "antitranspose":
        rotated = transformed.transformed(QtGui.QTransform().rotate(90), QtCore.Qt.TransformationMode.SmoothTransformation)
        return rotated.mirrored(False, True)
    return transformed


def _qimage_from_bgr_frame(frame) -> Optional[QtGui.QImage]:
    try:
        height, width, channels = frame.shape
    except Exception:
        return None
    fmt_container = getattr(QtGui.QImage, "Format", None)
    if fmt_container is not None and hasattr(fmt_container, "Format_BGR888"):
        return QtGui.QImage(frame.data, width, height, channels * width, fmt_container.Format_BGR888).copy()
    if hasattr(QtGui.QImage, "Format_BGR888"):
        return QtGui.QImage(frame.data, width, height, channels * width, QtGui.QImage.Format_BGR888).copy()
    return None


def _qimage_from_rgb_frame(frame, cv2_module) -> Optional[QtGui.QImage]:
    try:
        frame_rgb = cv2_module.cvtColor(frame, cv2_module.COLOR_BGR2RGB)
        height, width, channels = frame_rgb.shape
    except Exception:
        return None
    fmt_container = getattr(QtGui.QImage, "Format", None)
    if fmt_container is not None and hasattr(fmt_container, "Format_RGB888"):
        fmt = fmt_container.Format_RGB888
    else:
        fmt = QtGui.QImage.Format_RGB888
    return QtGui.QImage(frame_rgb.data, width, height, channels * width, fmt).copy()


def _extract_focus_review_frame_once(path: str, ms: int, *, max_width: int, transform_mode: str) -> QtGui.QImage:
    image = _extract_focus_review_frame_cv2_once(path, ms, max_width=max_width)
    if image is None or image.isNull():
        target_w = max(320, int(max_width)) if int(max_width) > 0 else 3840
        target_h = max(180, int(round(float(target_w) * 9.0 / 16.0)))
        image = _ffmpeg_frame_to_qimage(path, ms, w=target_w, h=target_h)
    if image is None or image.isNull():
        return QtGui.QImage()
    image = _scale_image_to_width(image, max_width=max_width)
    return _apply_transform_mode_to_image(image, transform_mode)


def _extract_focus_review_frame_cv2_once(path: str, ms: int, *, max_width: int) -> Optional[QtGui.QImage]:
    try:
        import cv2
    except ImportError:
        return None
    if not path or not os.path.isfile(path):
        return None
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        try:
            cap.release()
        except RuntimeError:
            logger.debug("focus review one-shot capture close skipped after open failure", exc_info=True)
        return None
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0, int(ms)))
        ok, frame = cap.read()
        if (not ok) or frame is None:
            return None
        image = _qimage_from_bgr_frame(frame)
        if image is None or image.isNull():
            image = _qimage_from_rgb_frame(frame, cv2)
        if image is None or image.isNull():
            return None
        return _scale_image_to_width(image, max_width=max_width)
    finally:
        try:
            cap.release()
        except RuntimeError:
            logger.debug("focus review one-shot capture release skipped", exc_info=True)


__all__ = ["FocusReviewWindow"]
