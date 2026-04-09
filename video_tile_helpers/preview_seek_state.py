from collections import OrderedDict
from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from scene_analysis.core.media import ThumbnailWorker


def init_seek_preview_state(tile):
    tile.preview_label = QtWidgets.QLabel(tile)
    tile.preview_label.setWindowFlags(QtCore.Qt.WindowType.ToolTip)
    tile.preview_label.setScaledContents(True)
    tile.preview_label.resize(160, 90)
    tile.preview_label.hide()
    tile._seek_preview_cache = OrderedDict()
    tile._seek_preview_cache_limit = 48
    tile._seek_preview_pending = None
    tile._seek_preview_worker = None
    tile._seek_preview_timer = QtCore.QTimer(tile)
    tile._seek_preview_timer.setSingleShot(True)
    tile._seek_preview_timer.setInterval(60)
    tile._seek_preview_timer.timeout.connect(tile._resolve_pending_seek_preview)


def ensure_seek_preview_worker(tile):
    worker = getattr(tile, "_seek_preview_worker", None)
    if worker is not None:
        return worker
    try:
        worker = ThumbnailWorker(parent=tile)
        worker.thumbnailReady.connect(tile._on_seek_preview_thumbnail_ready)
        worker.start()
        tile._seek_preview_worker = worker
    except Exception:
        tile._seek_preview_worker = None
        return None
    return worker


def shutdown_seek_preview(tile):
    try:
        if hasattr(tile, "_seek_preview_timer") and tile._seek_preview_timer is not None:
            tile._seek_preview_timer.stop()
    except Exception:
        pass
    try:
        worker = getattr(tile, "_seek_preview_worker", None)
        if worker is not None:
            worker.stop()
            tile._seek_preview_worker = None
    except Exception:
        pass


def cancel_seek_preview_request(tile):
    tile._seek_preview_pending = None
    try:
        tile._seek_preview_timer.stop()
    except Exception:
        pass
    try:
        worker = getattr(tile, "_seek_preview_worker", None)
        if worker is not None:
            worker.clear_jobs()
    except Exception:
        pass


def quantize_seek_preview_ms(tile, ms: int, length_ms: int, slider_width: int) -> int:
    width = max(1, int(slider_width))
    base_step = int(length_ms / width) if length_ms > 0 else 250
    step = max(120, min(1000, base_step))
    return int(round(max(0, int(ms)) / float(step)) * step)


def seek_preview_cache_key(tile, path: str, ms: int, w: int, h: int):
    return (
        tile._normalize_media_path(path),
        int(ms),
        int(max(1, w)),
        int(max(1, h)),
    )


def lookup_seek_preview_cache(tile, key):
    cache = getattr(tile, "_seek_preview_cache", None)
    if cache is None:
        return None
    pixmap = cache.get(key)
    if pixmap is None:
        return None
    try:
        cache.move_to_end(key)
    except Exception:
        pass
    return pixmap


def remember_seek_preview_cache(tile, key, pixmap: Optional[QtGui.QPixmap]):
    if pixmap is None or pixmap.isNull():
        return
    cache = getattr(tile, "_seek_preview_cache", None)
    if cache is None:
        return
    cache[key] = pixmap
    try:
        cache.move_to_end(key)
    except Exception:
        pass
    while len(cache) > int(getattr(tile, "_seek_preview_cache_limit", 48) or 48):
        try:
            cache.popitem(last=False)
        except Exception:
            break


def show_seek_preview_pixmap(tile, pixmap: QtGui.QPixmap, global_pos: QtCore.QPoint):
    if pixmap.isNull():
        return
    tile.preview_label.setPixmap(pixmap)
    tile.preview_label.move(
        global_pos.x() - tile.preview_label.width() // 2,
        tile.sld_pos.mapToGlobal(QtCore.QPoint(0, 0)).y() - tile.preview_label.height() - 10,
    )
    tile.preview_label.show()
