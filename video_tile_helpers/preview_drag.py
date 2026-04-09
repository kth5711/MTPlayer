import os
from typing import Optional

from PyQt6 import QtCore, QtGui

from .preview_seek_state import ensure_seek_preview_worker, lookup_seek_preview_cache, quantize_seek_preview_ms, seek_preview_cache_key


def _drag_preview_current_ms(tile) -> int:
    try:
        current_ms = int(tile.mediaplayer.get_time())
    except Exception:
        current_ms = -1
    try:
        length_ms = int(tile.mediaplayer.get_length())
    except Exception:
        length_ms = -1
    if current_ms < 0:
        try:
            pos = float(tile.mediaplayer.get_position())
            if 0 <= pos <= 1 and length_ms > 0:
                current_ms = int(pos * length_ms)
        except Exception:
            current_ms = 0
    return max(0, int(current_ms))


def _drag_preview_display_size(tile) -> tuple[int, int]:
    base_size = tile.video_widget.size() if hasattr(tile, "video_widget") else tile.size()
    return max(160, min(base_size.width(), 480)), max(90, min(base_size.height(), 270))


def drag_preview_request(tile):
    path = tile._current_playlist_path() or tile._current_media_path()
    if not path or not os.path.exists(path):
        return None
    current_ms = _drag_preview_current_ms(tile)
    try:
        length_ms = int(tile.mediaplayer.get_length())
    except Exception:
        length_ms = -1
    cache_w = tile.preview_label.width() if hasattr(tile, "preview_label") else 160
    cache_h = tile.preview_label.height() if hasattr(tile, "preview_label") else 90
    preview_ms = quantize_seek_preview_ms(tile, current_ms, max(length_ms, current_ms + 1), max(1, int(cache_w)))
    target_w, target_h = _drag_preview_display_size(tile)
    return {
        "path": path,
        "preview_ms": preview_ms,
        "cache_key": seek_preview_cache_key(tile, path, preview_ms, cache_w, cache_h),
        "display_w": int(target_w),
        "display_h": int(target_h),
    }


def scale_drag_preview_pixmap(
    tile,
    pixmap: Optional[QtGui.QPixmap],
    target_w: int,
    target_h: int,
) -> Optional[QtGui.QPixmap]:
    if pixmap is None or pixmap.isNull():
        return None
    try:
        return pixmap.scaled(
            int(max(1, target_w)),
            int(max(1, target_h)),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
    except Exception:
        return pixmap


def video_widget_drag_fallback_pixmap(tile, target_w: int, target_h: int) -> Optional[QtGui.QPixmap]:
    try:
        pixmap = tile.video_widget.grab()
    except Exception:
        pixmap = QtGui.QPixmap()
    if pixmap is None or pixmap.isNull():
        return None
    return scale_drag_preview_pixmap(tile, pixmap, target_w, target_h)


def _tile_drag_fallback_pixmap(tile, target_w: int, target_h: int) -> Optional[QtGui.QPixmap]:
    fallback = video_widget_drag_fallback_pixmap(tile, target_w, target_h)
    if fallback is not None and not fallback.isNull():
        return fallback
    try:
        tile_fallback = tile.grab()
    except Exception:
        tile_fallback = QtGui.QPixmap()
    if tile_fallback.isNull():
        return None
    return scale_drag_preview_pixmap(tile, tile_fallback, target_w, target_h)


def build_drag_preview_pixmap(tile) -> Optional[QtGui.QPixmap]:
    request = drag_preview_request(tile)
    if request is None:
        return None
    pixmap = lookup_seek_preview_cache(tile, request["cache_key"])
    if pixmap is not None and not pixmap.isNull():
        return scale_drag_preview_pixmap(tile, pixmap, request["display_w"], request["display_h"])
    tile._drag_preview_pending = request
    worker = ensure_seek_preview_worker(tile)
    if worker is not None:
        try:
            worker.add_job(request["path"], request["preview_ms"])
        except Exception:
            pass
    return _tile_drag_fallback_pixmap(tile, request["display_w"], request["display_h"])
