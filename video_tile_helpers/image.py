from typing import TYPE_CHECKING, Optional

from PyQt6 import QtCore, QtGui

from .image_display import (
    clear_image_display,
    current_media_pixel_size,
    refresh_image_display,
    set_image_mode_enabled,
    target_video_size_for_window_fit,
)
from .support import (
    is_animated_image_file_path as is_animated_image_file_path_impl,
    is_image_file_path as is_image_file_path_impl,
)

if TYPE_CHECKING:
    from video_tile import VideoTile


def is_image_path(tile: "VideoTile", path: Optional[str]) -> bool:
    return is_image_file_path_impl(path or "")


def is_animated_image_path(tile: "VideoTile", path: Optional[str]) -> bool:
    return is_animated_image_file_path_impl(path or "")


def is_static_image(tile: "VideoTile") -> bool:
    return getattr(tile, "_current_media_kind", "none") == "image"


def set_image_source_pixmap(tile: "VideoTile", pixmap: QtGui.QPixmap):
    tile._image_source_pixmap = QtGui.QPixmap(pixmap)


def set_image_movie(tile: "VideoTile", movie: Optional[QtGui.QMovie]):
    current = getattr(tile, "_image_movie", None)
    if current is movie:
        return
    if current is not None:
        try:
            current.frameChanged.disconnect(tile._on_image_movie_frame_changed)
        except Exception:
            pass
        try:
            current.stop()
        except Exception:
            pass
        try:
            current.deleteLater()
        except Exception:
            pass
    tile._image_movie = movie
    if movie is not None:
        movie.frameChanged.connect(tile._on_image_movie_frame_changed)


def on_image_movie_frame_changed(tile: "VideoTile", _frame_no: int):
    movie = getattr(tile, "_image_movie", None)
    if movie is None:
        return
    pixmap = movie.currentPixmap()
    if pixmap is not None and not pixmap.isNull():
        tile._set_image_source_pixmap(pixmap)
    tile._refresh_image_display()


def current_image_export_pixmap(tile: "VideoTile") -> Optional[QtGui.QPixmap]:
    pixmap = getattr(tile, "_image_source_pixmap", None)
    if pixmap is None or pixmap.isNull():
        return None
    mode = getattr(tile, "transform_mode", "none")
    if mode == "none":
        return QtGui.QPixmap(pixmap)
    image = pixmap.toImage()
    if mode == "hflip":
        image = image.mirrored(True, False)
    elif mode == "vflip":
        image = image.mirrored(False, True)
    elif mode == "180":
        image = image.transformed(QtGui.QTransform().rotate(180.0), QtCore.Qt.TransformationMode.SmoothTransformation)
    elif mode == "90":
        image = image.transformed(QtGui.QTransform().rotate(90.0), QtCore.Qt.TransformationMode.SmoothTransformation)
    elif mode == "270":
        image = image.transformed(QtGui.QTransform().rotate(270.0), QtCore.Qt.TransformationMode.SmoothTransformation)
    elif mode == "transpose":
        image = image.transformed(QtGui.QTransform().rotate(90.0), QtCore.Qt.TransformationMode.SmoothTransformation)
        image = image.mirrored(True, False)
    elif mode == "antitranspose":
        image = image.transformed(QtGui.QTransform().rotate(90.0), QtCore.Qt.TransformationMode.SmoothTransformation)
        image = image.mirrored(False, True)
    transformed = QtGui.QPixmap.fromImage(image)
    return transformed if not transformed.isNull() else QtGui.QPixmap(pixmap)
