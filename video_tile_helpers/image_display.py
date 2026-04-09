from typing import TYPE_CHECKING, Optional

from PyQt6 import QtCore, QtGui

if TYPE_CHECKING:
    from video_tile import VideoTile


def refresh_image_display(tile: "VideoTile"):
    overlay = getattr(tile, "image_overlay", None)
    if overlay is None:
        return
    overlay.setGeometry(tile.video_widget.geometry())
    pixmap = _display_pixmap(tile, overlay.size())
    if pixmap is None:
        overlay.clear()
        overlay.hide()
        return
    overlay.setPixmap(pixmap)
    overlay.show()
    overlay.raise_()


def _display_pixmap(tile: "VideoTile", target_size: QtCore.QSize) -> Optional[QtGui.QPixmap]:
    if not tile.is_static_image():
        return None
    pixmap = tile._current_image_export_pixmap()
    if pixmap is None or pixmap.isNull():
        return None
    if target_size.width() <= 0 or target_size.height() <= 0:
        return None
    scaled = _scale_display_pixmap(tile, pixmap, target_size)
    return _apply_zoom_to_pixmap(tile, scaled, target_size)


def _scale_display_pixmap(
    tile: "VideoTile",
    pixmap: QtGui.QPixmap,
    target_size: QtCore.QSize,
) -> QtGui.QPixmap:
    mode = getattr(tile, "display_mode", "fit")
    aspect_mode = _display_aspect_mode(mode)
    if aspect_mode is None:
        return pixmap
    return pixmap.scaled(
        target_size,
        aspect_mode,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )


def _apply_zoom_to_pixmap(
    tile: "VideoTile",
    pixmap: QtGui.QPixmap,
    target_size: QtCore.QSize,
) -> QtGui.QPixmap:
    try:
        zoom_percent = int(getattr(tile, "zoom_percent", 100) or 100)
    except Exception:
        zoom_percent = 100
    if zoom_percent == 100:
        return pixmap
    factor = max(0.25, min(4.0, float(zoom_percent) / 100.0))
    scaled = pixmap.scaled(
        max(1, int(round(pixmap.width() * factor))),
        max(1, int(round(pixmap.height() * factor))),
        QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )
    canvas = QtGui.QPixmap(target_size)
    canvas.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(canvas)
    x = int((target_size.width() - scaled.width()) / 2)
    y = int((target_size.height() - scaled.height()) / 2)
    painter.drawPixmap(x, y, scaled)
    painter.end()
    return canvas


def _display_aspect_mode(mode: str):
    if mode == "stretch":
        return QtCore.Qt.AspectRatioMode.IgnoreAspectRatio
    if mode == "crop":
        return QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding
    if mode == "original":
        return None
    return QtCore.Qt.AspectRatioMode.KeepAspectRatio


def clear_image_display(tile: "VideoTile"):
    tile._set_image_movie(None)
    tile._image_source_pixmap = QtGui.QPixmap()
    overlay = getattr(tile, "image_overlay", None)
    if overlay is None:
        return
    overlay.clear()
    overlay.hide()


def set_image_mode_enabled(tile: "VideoTile", enabled: bool):
    enabled = bool(enabled)
    tile._current_media_kind = "image" if enabled else "video"
    _set_video_controls_enabled(tile, not enabled)
    _set_image_slider_state(tile, enabled)
    if enabled:
        _reset_image_playback_state(tile)
    elif tile.lbl_time.text() == "이미지":
        tile.lbl_time.setText("00:00 / 00:00")
    tile._apply_controls_visibility()


def _set_video_controls_enabled(tile: "VideoTile", enabled: bool):
    for name in (
        "btn_scenes",
        "btn_play",
        "btn_stop",
        "btn_volume_toggle",
        "btn_audio_tracks",
        "btn_subtitle_tracks",
        "btn_A",
        "btn_repeat_mode",
        "btn_gif",
        "btn_clip",
        "btn_frameset",
    ):
        widget = getattr(tile, name, None)
        if widget is not None:
            widget.setEnabled(enabled)


def _set_image_slider_state(tile: "VideoTile", image_enabled: bool):
    if hasattr(tile, "sld_pos"):
        tile.sld_pos.setEnabled(not image_enabled)
        if image_enabled:
            tile.sld_pos.setValue(0)
    if hasattr(tile, "sld_vol"):
        if image_enabled and hasattr(tile, "btn_volume_toggle"):
            tile.btn_volume_toggle.setChecked(False)
        tile.sld_vol.setEnabled(not image_enabled)


def _reset_image_playback_state(tile: "VideoTile"):
    tile.posA = None
    tile.posB = None
    tile.loop_enabled = False
    tile.lbl_time.setText("이미지")
    tile._update_ab_controls()
    tile._update_repeat_button()


def current_media_pixel_size(tile: "VideoTile") -> Optional[QtCore.QSize]:
    if tile.is_static_image():
        return _current_image_pixel_size(tile)
    size = _current_video_pixel_size(tile)
    if size is None:
        return None
    if str(getattr(tile, "transform_mode", "none") or "none") in {"90", "270", "transpose", "antitranspose"}:
        return QtCore.QSize(size.height(), size.width())
    return size


def _current_image_pixel_size(tile: "VideoTile") -> Optional[QtCore.QSize]:
    pixmap = tile._current_image_export_pixmap()
    if pixmap is None or pixmap.isNull():
        return None
    return QtCore.QSize(int(pixmap.width()), int(pixmap.height()))


def _current_video_pixel_size(tile: "VideoTile") -> Optional[QtCore.QSize]:
    player = getattr(tile, "mediaplayer", None)
    if player is None or not _player_has_media(player):
        return None
    raw_size = _player_raw_video_size(player)
    if not isinstance(raw_size, (tuple, list)) or len(raw_size) < 2:
        return None
    try:
        width = int(raw_size[0] or 0)
        height = int(raw_size[1] or 0)
    except Exception:
        return None
    if width <= 0 or height <= 0:
        return None
    return QtCore.QSize(width, height)


def _player_has_media(player) -> bool:
    try:
        return player.get_media() is not None
    except Exception:
        return False


def _player_raw_video_size(player):
    try:
        return player.video_get_size(0)
    except TypeError:
        try:
            return player.video_get_size()
        except Exception:
            return None
    except Exception:
        return None


def target_video_size_for_window_fit(tile: "VideoTile") -> Optional[QtCore.QSize]:
    media_size = tile.current_media_pixel_size()
    if media_size is None or media_size.width() <= 0 or media_size.height() <= 0:
        return None
    mode = str(getattr(tile, "display_mode", "fit") or "fit")
    if mode == "original":
        return QtCore.QSize(media_size)
    viewport_size = _video_viewport_size(tile)
    if viewport_size is None:
        return QtCore.QSize(media_size)
    if mode in {"stretch", "crop"}:
        return viewport_size
    fitted = QtCore.QSize(media_size)
    fitted.scale(viewport_size.width(), viewport_size.height(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)
    return fitted


def _video_viewport_size(tile: "VideoTile") -> Optional[QtCore.QSize]:
    video_widget = getattr(tile, "video_widget", None)
    if video_widget is None:
        return None
    viewport_size = video_widget.size()
    if viewport_size.width() <= 0 or viewport_size.height() <= 0:
        return None
    return QtCore.QSize(int(viewport_size.width()), int(viewport_size.height()))
