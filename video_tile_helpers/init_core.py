import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PyQt6 import QtCore, QtGui, QtWidgets
import vlc

if TYPE_CHECKING:
    from video_tile import VideoTile


def init_video_tile_core(tile: "VideoTile", parent=None, vlc_instance=None):
    _configure_vlc_instance(tile, parent, vlc_instance)
    _init_frame_state(tile)
    _init_playback_state(tile)
    tile._create_mediaplayer(tile.shared_vlc_instance)
    _init_video_surface(tile)
    _init_image_widgets(tile)
    _init_cursor_bridge_overlay(tile)
    _init_feedback_overlays(tile)
    _init_tile_audio_display_state(tile)


def _configure_vlc_instance(tile: "VideoTile", parent, vlc_instance):
    tile.vlc_instance = vlc_instance
    if tile.vlc_instance is None:
        print("Warning: VLC instance not provided to VideoTile, creating a new one.")
        tile.vlc_instance = _build_default_vlc_instance()
    tile.shared_vlc_instance = tile.vlc_instance
    tile._owned_vlc_instance = None
    tile._main_window_owner = _main_window_owner(parent)


def _build_default_vlc_instance():
    if os.name != "nt":
        return vlc.Instance()
    return vlc.Instance(
        "--avcodec-hw=none",
        "--no-video-title-show",
        "--aout=directsound",
        "--no-xlib",
        "--file-caching=200",
        "--network-caching=200",
    )


def _main_window_owner(parent):
    try:
        owner = parent.window() if parent is not None and hasattr(parent, "window") else None
    except Exception:
        return None
    if owner is not None and hasattr(owner, "config"):
        return owner
    return None


def _init_frame_state(tile: "VideoTile"):
    tile.setLineWidth(1)
    tile.is_selected = False
    tile.selection_mode = "off"
    tile.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    tile.setStyleSheet("border: 1px solid black;")
    tile.setAcceptDrops(True)
    tile.setMinimumSize(0, 0)
    tile.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
    tile.playlist = []
    tile.detached_window_opacity = 1.0
    tile._scene_cache = {}
    tile.current_index = -1
    tile._last_bound_video_target = None
    tile._drag_preview_pending = None
    tile._compact_mode = False
    tile._controls_requested_visible = True
    tile._export_worker = None
    tile._export_worker_busy = False
    tile._export_job_meta = {}
    tile._subtitle_generation_worker = None
    tile._subtitle_translation_worker = None
    tile._url_download_worker = None
    tile._active_context_menu = None
    tile.add_button = None


def _init_playback_state(tile: "VideoTile"):
    tile.playlist = []
    tile.current_index = -1
    tile._playlist_entry_bookmarks = {}
    tile._playlist_bookmark_end_ms = None
    tile._playlist_bookmark_guard_active = False
    tile.posA = None
    tile.posB = None
    tile.loop_enabled = False
    tile.repeat_mode = "off"
    tile.external_subtitles = {}
    tile.playback_rate = 1.0
    tile.zoom_percent = 100
    tile.transform_mode = "none"
    tile._last_set_media_error = ""
    tile.mediaplayer = None
    tile.event_manager = None


def _init_video_surface(tile: "VideoTile"):
    tile.video_widget = QtWidgets.QWidget(tile)
    tile.video_widget.setMouseTracking(True)
    tile.video_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
    tile.video_widget.installEventFilter(tile)
    tile._current_media_kind = "none"
    tile._image_source_pixmap = QtGui.QPixmap()
    tile._image_movie = None


def _init_image_widgets(tile: "VideoTile"):
    tile.image_overlay = QtWidgets.QLabel(tile)
    tile.image_overlay.setVisible(False)
    tile.image_overlay.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    tile.image_overlay.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    tile.image_overlay.setStyleSheet("background-color: #000;")


def _init_cursor_bridge_overlay(tile: "VideoTile"):
    tile._cursor_bridge_overlay = QtWidgets.QWidget(tile)
    tile._cursor_bridge_overlay.setVisible(False)
    tile._cursor_bridge_overlay.setMouseTracking(True)
    tile._cursor_bridge_overlay.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
    tile._cursor_bridge_overlay.setStyleSheet("background: transparent;")
    tile._cursor_bridge_overlay.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground, True)
    tile._cursor_bridge_overlay.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
    tile._cursor_bridge_overlay_timer = QtCore.QTimer(tile)
    tile._cursor_bridge_overlay_timer.setSingleShot(True)
    tile._cursor_bridge_overlay_timer.timeout.connect(tile._cursor_bridge_overlay.hide)


def _init_feedback_overlays(tile: "VideoTile"):
    mute_overlay = _configure_center_overlay(
        tile,
        "mute_overlay",
        "",
        "_mute_overlay_timer",
    )
    tile._mute_overlay_timer.timeout.connect(mute_overlay.hide)
    volume_overlay = _configure_center_overlay(
        tile,
        "volume_overlay",
        "",
        "_volume_overlay_timer",
    )
    tile._volume_overlay_timer.timeout.connect(volume_overlay.hide)
    _configure_center_overlay(
        tile,
        "seek_overlay",
        "",
        "_seek_overlay_timer",
        tile._hide_seek_overlay,
    )
    rate_overlay = _configure_center_overlay(
        tile,
        "rate_overlay",
        "",
        "_rate_overlay_timer",
    )
    tile._rate_overlay_timer.timeout.connect(rate_overlay.hide)
    status_overlay = _configure_center_overlay(
        tile,
        "status_overlay",
        "",
        "_status_overlay_timer",
    )
    tile._status_overlay_timer.timeout.connect(status_overlay.hide)
    refresh_feedback_overlay_styles(tile)

def _configure_center_overlay(
    tile: "VideoTile",
    name: str,
    stylesheet: str,
    timer_name: str,
    timeout_slot=None,
):
    overlay = QtWidgets.QLabel(tile)
    overlay.setVisible(False)
    overlay.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    overlay.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    overlay.setStyleSheet(stylesheet)
    setattr(tile, name, overlay)
    timer = QtCore.QTimer(tile)
    timer.setSingleShot(True)
    if timeout_slot is not None:
        timer.timeout.connect(timeout_slot)
    setattr(tile, timer_name, timer)
    return overlay


def _init_tile_audio_display_state(tile: "VideoTile"):
    tile.tile_volume = getattr(tile, "tile_volume", 120)
    tile.tile_muted = getattr(tile, "tile_muted", False)
    tile.display_mode = getattr(tile, "display_mode", "fit")
    tile.transform_mode = getattr(tile, "transform_mode", "none")


def _feedback_overlay_theme_is_dark(tile: "VideoTile") -> bool:
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
        return int(tile.palette().color(QtGui.QPalette.ColorRole.Window).lightness()) < 140
    except Exception:
        return True


def refresh_feedback_overlay_styles(tile: "VideoTile") -> None:
    dark_theme = _feedback_overlay_theme_is_dark(tile)
    text_styles = (
        {
            "mute_overlay": "font-size: 42px; color: rgba(255,255,255,218); background: transparent; padding: 0;",
            "volume_overlay": "font-size: 11px; font-weight: 700; color: rgba(248,248,248,232); background: transparent; padding: 0;",
            "seek_overlay": "font-size: 12px; font-weight: 700; color: rgba(255,255,255,236); background: transparent; padding: 0;",
            "rate_overlay": "font-size: 12px; font-weight: 700; color: rgba(255,255,255,236); background: transparent; padding: 0;",
            "status_overlay": "font-size: 13px; font-weight: 700; color: rgba(255,255,255,240); background: transparent; padding: 0;",
        }
        if dark_theme
        else
        {
            "mute_overlay": "font-size: 42px; color: rgba(29,40,52,228); background: transparent; padding: 0;",
            "volume_overlay": "font-size: 11px; font-weight: 700; color: rgba(33,45,58,234); background: transparent; padding: 0;",
            "seek_overlay": "font-size: 12px; font-weight: 700; color: rgba(31,42,55,236); background: transparent; padding: 0;",
            "rate_overlay": "font-size: 12px; font-weight: 700; color: rgba(31,42,55,236); background: transparent; padding: 0;",
            "status_overlay": "font-size: 13px; font-weight: 700; color: rgba(27,38,50,238); background: transparent; padding: 0;",
        }
    )
    shadow_color = QtGui.QColor(0, 0, 0, 186) if dark_theme else QtGui.QColor(255, 255, 255, 212)
    shadow_blur = 14 if dark_theme else 12
    shadow_offset = QtCore.QPointF(0, 1) if dark_theme else QtCore.QPointF(0, 0)
    for name, stylesheet in text_styles.items():
        overlay = getattr(tile, name, None)
        if overlay is None:
            continue
        overlay.setStyleSheet(stylesheet)
        shadow = overlay.graphicsEffect()
        if not isinstance(shadow, QtWidgets.QGraphicsDropShadowEffect):
            shadow = QtWidgets.QGraphicsDropShadowEffect(overlay)
            overlay.setGraphicsEffect(shadow)
        shadow.setBlurRadius(shadow_blur)
        shadow.setOffset(shadow_offset)
        shadow.setColor(shadow_color)
