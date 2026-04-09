import os
from typing import Optional

from PyQt6 import QtGui, QtWidgets

from scene_analysis.core.media import (
    FFMPEG_BIN,
    _ffmpeg_frame_to_pixmap,
    ffmpeg_available,
    resolve_ffmpeg_bin,
)


def _fmt_ms_tag(ms: int) -> str:
    total = max(0, int(ms))
    sec = total // 1000
    ms3 = total % 1000
    hh = sec // 3600
    mm = (sec % 3600) // 60
    ss = sec % 60
    return f"{hh:02d}-{mm:02d}-{ss:02d}-{ms3:03d}"


def _pixmap_safe(get_frame_thumbnail_callable, path: str, ms: int, w=160, h=90) -> Optional[QtGui.QPixmap]:
    pm = None
    try:
        pm = get_frame_thumbnail_callable(path, ms, w=w, h=h)
        if pm and not pm.isNull():
            return pm
    except Exception:
        pm = None
    for delta in (120, 240, -120, -240):
        try:
            pm = get_frame_thumbnail_callable(path, max(ms + delta, 0), w=w, h=h)
            if pm and not pm.isNull():
                return pm
        except Exception:
            pass
    return _ffmpeg_frame_to_pixmap(path, ms, w=w, h=h)


def _dialog_ffmpeg_bin(dialog) -> str:
    preferred = str(getattr(getattr(dialog, "ed_ff", None), "text", lambda: "")() or "").strip()
    if not preferred:
        host = getattr(dialog, "host", None)
        preferred = str(getattr(host, "ffmpeg_path", "") or "").strip()
    ffbin = resolve_ffmpeg_bin(preferred or FFMPEG_BIN)
    try:
        if hasattr(dialog, "ed_ff"):
            dialog.ed_ff.setText(ffbin)
    except Exception:
        pass
    try:
        host = getattr(dialog, "host", None)
        if host is not None:
            setattr(host, "ffmpeg_path", ffbin)
    except Exception:
        pass
    return ffbin


def _existing_scene_path(dialog, allow_host_fallback: bool = False) -> str:
    path = os.path.abspath(str(getattr(dialog, "current_path", "") or "").strip())
    if not path and allow_host_fallback:
        host = getattr(dialog, "host", None)
        host_path = str(getattr(host, "_current_media_path", lambda: "")() or "").strip()
        path = os.path.abspath(host_path) if host_path else ""
    if not path or not os.path.exists(path):
        return ""
    return path


def _scene_busy_message(dialog, include_clip_busy: bool = False) -> str:
    if getattr(dialog, "worker", None) is not None:
        return "씬변화가 실행 중입니다."
    rw = getattr(dialog, "refilter_worker", None)
    if rw is not None and rw.isRunning():
        return "유사씬 탐색이 실행 중입니다."
    if include_clip_busy and bool(getattr(dialog, "_clip_worker_busy", False)):
        return "클립 작업이 실행 중입니다."
    return ""


def _show_scene_busy_message(dialog, include_clip_busy: bool = False) -> bool:
    msg = _scene_busy_message(dialog, include_clip_busy=include_clip_busy)
    if not msg:
        return False
    QtWidgets.QMessageBox.information(dialog, "알림", msg)
    return True


def _available_ffmpeg_bin(dialog) -> str:
    ffbin = _dialog_ffmpeg_bin(dialog)
    return ffbin if ffmpeg_available(ffbin) else ""
