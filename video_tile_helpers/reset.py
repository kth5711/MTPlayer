from typing import TYPE_CHECKING
from i18n import tr

if TYPE_CHECKING:
    from video_tile import VideoTile


def clear_playlist(tile: "VideoTile"):
    _reset_playlist_state(tile)
    _stop_active_media(tile)
    _reset_track_controls(tile)
    _reset_title(tile)
    tile.refresh_bookmark_marks(force=True, length_ms=0)
    _refresh_window_title(tile)
    tile._update_ab_controls()
    tile._update_add_button()


def _reset_playlist_state(tile: "VideoTile"):
    tile.playlist.clear()
    tile.current_index = -1
    tile._clear_playlist_entry_start_positions()
    tile._playlist_bookmark_end_ms = None
    tile._playlist_bookmark_guard_active = False
    tile.external_subtitles.clear()
    tile.posA = None
    tile.posB = None
    tile.loop_enabled = False
    tile._current_media_kind = "none"


def _stop_active_media(tile: "VideoTile"):
    tile.mediaplayer.stop()
    try:
        tile.mediaplayer.set_media(None)
    except Exception:
        pass
    tile._clear_image_display()
    tile._set_image_mode_enabled(False)


def _reset_track_controls(tile: "VideoTile"):
    try:
        tile.audio_menu.clear()
        tile.subtitle_menu.clear()
        tile.btn_audio_tracks.setEnabled(False)
        tile.btn_subtitle_tracks.setEnabled(False)
    except Exception:
        pass


def _reset_title(tile: "VideoTile"):
    tile.title.setText(tr(tile, "(열기)"))
    tile.title.setToolTip(tr(tile, "이 타일에 미디어를 열려면 클릭하세요"))


def _refresh_window_title(tile: "VideoTile"):
    try:
        window = tile.window()
        if window is not None and hasattr(window, "refresh_title"):
            window.refresh_title()
    except Exception:
        pass
