import os

from PyQt6 import QtCore, QtGui

from .preview_seek_state import (
    cancel_seek_preview_request,
    ensure_seek_preview_worker,
    lookup_seek_preview_cache,
    quantize_seek_preview_ms,
    remember_seek_preview_cache,
    seek_preview_cache_key,
    show_seek_preview_pixmap,
)
from .preview_thumbnail import get_frame_thumbnail_safe


def resolve_pending_seek_preview(tile):
    pending = getattr(tile, "_seek_preview_pending", None)
    if not pending:
        return
    pixmap = lookup_seek_preview_cache(tile, pending["key"])
    if pixmap is None:
        worker = ensure_seek_preview_worker(tile)
        if worker is not None:
            try:
                worker.clear_jobs()
                worker.add_job(pending["path"], pending["preview_ms"])
            except Exception:
                pass
            return
        pixmap = get_frame_thumbnail_safe(tile, pending["path"], pending["preview_ms"], w=pending["w"], h=pending["h"])
        remember_seek_preview_cache(tile, pending["key"], pixmap)
    if pixmap is None or pixmap.isNull():
        return
    tile._seek_preview_pending = None
    show_seek_preview_pixmap(tile, pixmap, pending["global_pos"])


def on_seek_preview_thumbnail_ready(tile, path: str, image: QtGui.QImage, ms: int):
    if image.isNull():
        return
    key = seek_preview_cache_key(tile, path, ms, tile.preview_label.width(), tile.preview_label.height())
    pixmap = QtGui.QPixmap.fromImage(image)
    if pixmap.isNull():
        return
    remember_seek_preview_cache(tile, key, pixmap)
    pending = getattr(tile, "_seek_preview_pending", None)
    if pending and pending.get("key") == key:
        tile._seek_preview_pending = None
        show_seek_preview_pixmap(tile, pixmap, pending["global_pos"])
    drag_pending = getattr(tile, "_drag_preview_pending", None)
    if drag_pending and drag_pending.get("cache_key") == key:
        tile._drag_preview_pending = None
        scaled = tile._scale_drag_preview_pixmap(
            pixmap, drag_pending.get("display_w", pixmap.width()), drag_pending.get("display_h", pixmap.height())
        )
        if scaled is not None and not scaled.isNull():
            try:
                tile.dragPreviewReady.emit(scaled)
            except Exception:
                pass


def _preview_request(tile, event):
    if not tile.playlist or tile.current_index < 0:
        return None
    path = tile.playlist[tile.current_index]
    if not os.path.exists(path):
        return None
    slider_width = tile.sld_pos.width()
    if slider_width <= 0:
        return None
    length_ms = tile.mediaplayer.get_length()
    if length_ms <= 0:
        return None
    pos_ratio = max(0.0, min(1.0, event.pos().x() / slider_width))
    preview_ms = quantize_seek_preview_ms(tile, int(length_ms * pos_ratio), length_ms, slider_width)
    global_pos = tile.sld_pos.mapToGlobal(event.pos())
    width = tile.preview_label.width()
    height = tile.preview_label.height()
    return {
        "key": seek_preview_cache_key(tile, path, preview_ms, width, height),
        "path": path,
        "preview_ms": preview_ms,
        "w": width,
        "h": height,
        "global_pos": global_pos,
    }


def _move_preview_label(tile, global_pos: QtCore.QPoint) -> None:
    tile.preview_label.move(
        global_pos.x() - tile.preview_label.width() // 2,
        tile.sld_pos.mapToGlobal(QtCore.QPoint(0, 0)).y() - tile.preview_label.height() - 10,
    )


def show_preview(tile, event):
    pending = _preview_request(tile, event)
    if pending is None:
        return
    pixmap = lookup_seek_preview_cache(tile, pending["key"])
    if pixmap is not None and not pixmap.isNull():
        cancel_seek_preview_request(tile)
        show_seek_preview_pixmap(tile, pixmap, pending["global_pos"])
        return
    tile._seek_preview_pending = pending
    if tile.preview_label.isVisible():
        _move_preview_label(tile, pending["global_pos"])
    tile._seek_preview_timer.start()
