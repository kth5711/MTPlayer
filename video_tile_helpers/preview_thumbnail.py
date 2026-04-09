import os
import tempfile
from typing import Optional

from PyQt6 import QtCore, QtGui

from .support import _ffmpeg_available, _spawn_ffmpeg, current_ffmpeg_bin


def get_frame_thumbnail(tile, path: str, ms: int, w: int = 160, h: int = 90) -> Optional[QtGui.QPixmap]:
    import cv2

    if not os.path.exists(path):
        return None
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0, ms))
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    hh, ww, ch = frame.shape
    image = QtGui.QImage(frame.data, ww, hh, ch * ww, QtGui.QImage.Format.Format_BGR888)
    return QtGui.QPixmap.fromImage(image).scaled(
        w,
        h,
        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )


def _tile_ffmpeg_bin(tile, preferred: str = "") -> str:
    mw = tile._main_window() if hasattr(tile, "_main_window") else None
    mw_pref = str(getattr(mw, "ffmpeg_path", "") or "").strip() if mw is not None else ""
    return current_ffmpeg_bin(preferred or mw_pref)


def _ffmpeg_thumbnail_command(ffmpeg_bin: str, path: str, ms: int, w: int, jpg: str) -> list[str]:
    return [
        ffmpeg_bin,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        path,
        "-ss",
        f"{max(ms, 0) / 1000.0:.3f}",
        "-frames:v",
        "1",
        "-vf",
        f"scale={w}:-1:flags=bilinear",
        "-q:v",
        "3",
        jpg,
    ]


def get_frame_thumbnail_ffmpeg(tile, path: str, ms: int, w=160, h=90, ffmpeg_bin: str = ""):
    ffmpeg_bin = _tile_ffmpeg_bin(tile, ffmpeg_bin)
    if not os.path.exists(path) or not _ffmpeg_available(ffmpeg_bin):
        return None
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        jpg = tmp.name
    try:
        _spawn_ffmpeg(_ffmpeg_thumbnail_command(ffmpeg_bin, path, ms, w, jpg))
        if os.path.exists(jpg) and os.path.getsize(jpg) > 0:
            pixmap = QtGui.QPixmap(jpg)
            return pixmap if not pixmap.isNull() else None
        return None
    finally:
        try:
            os.remove(jpg)
        except Exception:
            pass


def get_frame_thumbnail_safe(tile, path: str, ms: int, w=160, h=90):
    pixmap = get_frame_thumbnail(tile, path, ms, w=w, h=h)
    if pixmap and not pixmap.isNull():
        return pixmap
    for delta in (120, 240, -120, -240):
        pixmap = get_frame_thumbnail(tile, path, max(ms + delta, 0), w=w, h=h)
        if pixmap and not pixmap.isNull():
            return pixmap
    return get_frame_thumbnail_ffmpeg(tile, path, ms, w=w, h=h)
