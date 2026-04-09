import os
import urllib.parse
from typing import List, Optional, Dict, Any

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QPushButton, QFileDialog

from video_tile_helpers.export_capture import (
    capture_screenshot as capture_screenshot_impl,
    save_frame_set as save_frame_set_impl,
)
from video_tile_helpers.export_common import get_export_path as get_export_path_impl
from video_tile_helpers.export_jobs import (
    export_audio_clip as export_audio_clip_impl,
    export_clip as export_clip_impl,
    export_gif as export_gif_impl,
)
from video_tile_helpers.export_worker import stop_export_worker as stop_export_worker_impl
from video_tile_helpers.url_download import (
    save_url_from_context as save_url_from_context_impl,
    stop_url_download_worker as stop_url_download_worker_impl,
)
from video_tile_helpers.subtitle_generation import (
    generate_subtitle_from_context as generate_subtitle_from_context_impl,
    stop_subtitle_generation_worker as stop_subtitle_generation_worker_impl,
)
from video_tile_helpers.subtitle_translation import (
    stop_subtitle_translation_worker as stop_subtitle_translation_worker_impl,
    translate_subtitle_from_context as translate_subtitle_from_context_impl,
)
from video_tile_helpers.playlist import (
    add_to_playlist as add_to_playlist_impl,
    append_media_paths as append_media_paths_impl,
    apply_external_subtitle_to_player as apply_external_subtitle_to_player_impl,
    apply_saved_subtitle_option as apply_saved_subtitle_option_impl,
    collect_video_files as collect_video_files_impl,
    current_playlist_path as current_playlist_path_impl,
    get_external_subtitle_for_path as get_external_subtitle_for_path_impl,
    normalize_media_path as normalize_media_path_impl,
    open_subtitle_file as open_subtitle_file_impl,
    pop_external_subtitle_for_path as pop_external_subtitle_for_path_impl,
    prepend_files_to_playlist_and_play as prepend_files_to_playlist_and_play_impl,
    set_external_subtitle_for_path as set_external_subtitle_for_path_impl,
)
from video_tile_helpers.selection import set_selection as set_selection_impl
from video_tile_helpers.player import (
    apply_display_mode as apply_display_mode_impl,
    apply_media_hw_options as apply_media_hw_options_impl,
    bind_hwnd as bind_hwnd_impl,
    create_mediaplayer as create_mediaplayer_impl,
    cycle_display_mode as cycle_display_mode_impl,
    cycle_transform_mode as cycle_transform_mode_impl,
    display_geometry_spec as display_geometry_spec_impl,
    pause as pause_impl,
    play as play_impl,
    populate_track_menus as populate_track_menus_impl,
    rebuild_display_mode_menu as rebuild_display_mode_menu_impl,
    rebuild_player_for_transform_mode as rebuild_player_for_transform_mode_impl,
    rebuild_transform_mode_menu as rebuild_transform_mode_menu_impl,
    refresh_track_menus as refresh_track_menus_impl,
    release_mediaplayer as release_mediaplayer_impl,
    set_audio_track as set_audio_track_impl,
    set_display_mode as set_display_mode_impl,
    set_media as set_media_impl,
    set_subtitle_track as set_subtitle_track_impl,
    set_transform_mode as set_transform_mode_impl,
    set_zoom_percent as set_zoom_percent_impl,
    should_use_hw_accel as should_use_hw_accel_impl,
    stop as stop_impl,
    toggle_play as toggle_play_impl,
    transform_instance_args as transform_instance_args_impl,
    update_display_mode_button as update_display_mode_button_impl,
    update_transform_mode_button as update_transform_mode_button_impl,
    vlc_base_instance_args as vlc_base_instance_args_impl,
)
from video_tile_helpers.image import (
    clear_image_display as clear_image_display_impl,
    current_image_export_pixmap as current_image_export_pixmap_impl,
    current_media_pixel_size as current_media_pixel_size_impl,
    is_animated_image_path as is_animated_image_path_impl,
    is_image_path as is_image_path_impl,
    is_static_image as is_static_image_impl,
    on_image_movie_frame_changed as on_image_movie_frame_changed_impl,
    refresh_image_display as refresh_image_display_impl,
    set_image_mode_enabled as set_image_mode_enabled_impl,
    set_image_movie as set_image_movie_impl,
    set_image_source_pixmap as set_image_source_pixmap_impl,
    target_video_size_for_window_fit as target_video_size_for_window_fit_impl,
)
from video_tile_helpers.init_core import init_video_tile_core as init_video_tile_core_impl
from video_tile_helpers.init_ui import (
    init_video_tile_ui as init_video_tile_ui_impl,
)
from video_tile_helpers.ui import refresh_video_tile_ui_texts as refresh_video_tile_ui_texts_impl
from video_tile_helpers.overlay_context import (
    apply_overlay_opacity_preset_from_context as apply_overlay_opacity_preset_from_context_impl,
    clear_overlay_stack_from_context as clear_overlay_stack_from_context_impl,
    clamp_dialog_point as clamp_dialog_point_impl,
    create_overlay_stack_from_context as create_overlay_stack_from_context_impl,
    dialog_available_rect_for_video as dialog_available_rect_for_video_impl,
    open_opacity_slider_dialog as open_opacity_slider_dialog_impl,
    open_overlay_global_apply_dialog_from_context as open_overlay_global_apply_dialog_from_context_impl,
    open_overlay_layer_opacity_dialog_from_context as open_overlay_layer_opacity_dialog_from_context_impl,
    open_overlay_opacity_dialog_from_context as open_overlay_opacity_dialog_from_context_impl,
    open_tile_window_opacity_dialog_from_context as open_tile_window_opacity_dialog_from_context_impl,
    overlay_dialog_parent as overlay_dialog_parent_impl,
    overlay_layer_dialog_label as overlay_layer_dialog_label_impl,
    overlay_layer_opacity_items as overlay_layer_opacity_items_impl,
    position_dialog_outside_video as position_dialog_outside_video_impl,
    prepare_overlay_dialog as prepare_overlay_dialog_impl,
    set_overlay_audio_mode_from_context as set_overlay_audio_mode_from_context_impl,
    set_overlay_global_apply_from_context as set_overlay_global_apply_from_context_impl,
    set_tile_window_opacity_from_context as set_tile_window_opacity_from_context_impl,
)
from video_tile_helpers.preview import (
    build_drag_preview_pixmap as build_drag_preview_pixmap_impl,
    cancel_seek_preview_request as cancel_seek_preview_request_impl,
    drag_preview_request as drag_preview_request_impl,
    ensure_seek_preview_worker as ensure_seek_preview_worker_impl,
    get_frame_thumbnail as get_frame_thumbnail_impl,
    get_frame_thumbnail_ffmpeg as get_frame_thumbnail_ffmpeg_impl,
    get_frame_thumbnail_safe as get_frame_thumbnail_safe_impl,
    lookup_seek_preview_cache as lookup_seek_preview_cache_impl,
    on_seek_preview_thumbnail_ready as on_seek_preview_thumbnail_ready_impl,
    quantize_seek_preview_ms as quantize_seek_preview_ms_impl,
    remember_seek_preview_cache as remember_seek_preview_cache_impl,
    resolve_pending_seek_preview as resolve_pending_seek_preview_impl,
    scale_drag_preview_pixmap as scale_drag_preview_pixmap_impl,
    seek_preview_cache_key as seek_preview_cache_key_impl,
    show_preview as show_preview_impl,
    show_seek_preview_pixmap as show_seek_preview_pixmap_impl,
    shutdown_seek_preview as shutdown_seek_preview_impl,
    video_widget_drag_fallback_pixmap as video_widget_drag_fallback_pixmap_impl,
)
from video_tile_helpers.support import (
    _detect_scenes_parallel,
    media_file_dialog_filter as media_file_dialog_filter_impl,
)
from video_tile_helpers.ui import (
    bind_tile_context_menu as bind_tile_context_menu_impl,
    exec_tile_context_menu as exec_tile_context_menu_impl,
    finalize_tile_context_menu as finalize_tile_context_menu_impl,
    OpacitySliderDialog,
    OverlayGlobalApplyDialog,
    OverlayLayerOpacityDialog,
    show_tile_context_menu as show_tile_context_menu_impl,
)
from video_tile_helpers.context_actions import (
    add_bookmark as add_bookmark_impl,
    dialog_start_dir as dialog_start_dir_impl,
    fit_media_size_from_context as fit_media_size_from_context_impl,
    jump_to_timecode_from_context as jump_to_timecode_from_context_impl,
    open_focus_review_from_context as open_focus_review_from_context_impl,
    open_url_stream_from_context as open_url_stream_from_context_impl,
    remember_dialog_dir as remember_dialog_dir_impl,
    sync_other_tiles_to_this_timecode as sync_other_tiles_to_this_timecode_impl,
    trigger_mute_selected_tiles as trigger_mute_selected_tiles_impl,
)
from video_tile_helpers.bookmarks import (
    activate_bookmark_marker_positions as activate_bookmark_marker_positions_impl,
    bookmark_marker_select_mode_active as bookmark_marker_select_mode_active_impl,
    bookmark_snap_ms_for_slider_x as bookmark_snap_ms_for_slider_x_impl,
    handle_bookmark_marker_click as handle_bookmark_marker_click_impl,
    refresh_bookmark_marks as refresh_bookmark_marks_impl,
    show_preview_for_slider_x as show_preview_for_slider_x_impl,
    sync_bookmark_marker_select_mode_from_cursor as sync_bookmark_marker_select_mode_from_cursor_impl,
)
from video_tile_helpers.events import (
    event_filter as event_filter_impl,
    handle_volume_wheel_event as handle_volume_wheel_event_impl,
    jump_to_click as jump_to_click_impl,
    on_seek_slider_moved as on_seek_slider_moved_impl,
)
from video_tile_helpers.playlist_bookmarks import (
    advance_current_playlist_bookmark as advance_current_playlist_bookmark_impl,
    apply_current_playlist_start_position as apply_current_playlist_start_position_impl,
    clear_playlist_entry_start_positions as clear_playlist_entry_start_positions_impl,
    playlist_entries_with_start_positions as playlist_entries_with_start_positions_impl,
    playlist_entry_bookmark_positions as playlist_entry_bookmark_positions_impl,
    select_playlist_entry_bookmark as select_playlist_entry_bookmark_impl,
    set_playlist_entry_bookmark_cursor as set_playlist_entry_bookmark_cursor_impl,
    set_playlist_entry_bookmark_positions as set_playlist_entry_bookmark_positions_impl,
    set_playlist_entry_bookmark_targets as set_playlist_entry_bookmark_targets_impl,
    set_playlist_entry_start_position as set_playlist_entry_start_position_impl,
)
from video_tile_helpers.reset import clear_playlist as clear_playlist_impl
from video_tile_helpers.state import (
    from_state as from_state_impl,
    restore_session_media_state as restore_session_media_state_impl,
    to_state as to_state_impl,
)
from i18n import tr


class VideoTile(QtWidgets.QFrame):
    double_clicked = QtCore.pyqtSignal(object)  # self 전달
    dragPreviewReady = QtCore.pyqtSignal(object)
    REPEAT_MODES = ("off", "single", "playlist")
    DISPLAY_MODES = ("fit", "crop", "stretch", "original")
    TRANSFORM_MODES = ("none", "hflip", "vflip", "180", "90", "270", "transpose", "antitranspose")
    ROTATION_TOGGLE_MODES = ("none", "90", "180", "270")
    ZOOM_PERCENTS = (100, 125, 150, 200)
    DISPLAY_MODE_LABELS = {
        "fit": "최적화",
        "crop": "채우기",
        "stretch": "늘이기",
        "original": "원본",
    }
    DISPLAY_MODE_TOOLTIPS = {
        "fit": "영상 비율 유지, 타일 안에 맞춤",
        "crop": "영상 비율 유지, 타일을 가득 채우도록 잘라냄",
        "stretch": "타일 크기에 맞게 비율을 무시하고 늘림",
        "original": "원본 픽셀 배율(1x)로 표시",
    }
    TRANSFORM_MODE_LABELS = {
        "none": "정방향",
        "hflip": "좌우반전",
        "vflip": "상하반전",
        "180": "180도",
        "90": "시계90",
        "270": "반시계90",
        "transpose": "대각반전",
        "antitranspose": "역대각반전",
    }
    TRANSFORM_MODE_TOOLTIPS = {
        "none": "영상 방향을 원래대로 표시",
        "hflip": "좌우를 뒤집어 표시",
        "vflip": "상하를 뒤집어 표시",
        "180": "180도 회전",
        "90": "시계 방향으로 90도 회전",
        "270": "반시계 방향으로 90도 회전",
        "transpose": "시계90 회전 후 좌우반전",
        "antitranspose": "시계90 회전 후 상하반전",
    }

    def __init__(self, parent=None, vlc_instance=None):
        super().__init__(parent)
        init_video_tile_core_impl(self, parent, vlc_instance)
        init_video_tile_ui_impl(self)

    def _refresh_ui_texts(self):
        refresh_video_tile_ui_texts_impl(self)
        self._refresh_add_button_style()

    def eventFilter(self, obj, event):
        handled = event_filter_impl(self, obj, event)
        if handled is not None:
            return handled
        return super().eventFilter(obj, event)

    def wheelEvent(self, event: QtGui.QWheelEvent):
        if self._handle_volume_wheel_event(event):
            return
        super().wheelEvent(event)

    def _handle_volume_wheel_event(self, event: QtGui.QWheelEvent) -> bool:
        return handle_volume_wheel_event_impl(self, event)

    def _jump_to_click(self, pos: QtCore.QPoint):
        jump_to_click_impl(self, pos)

    def _on_seek_slider_moved(self, value: int):
        on_seek_slider_moved_impl(self, value)

    def set_selection(self, mode="normal"):
        set_selection_impl(self, mode)

    # --- 시간 변환 헬퍼 --- #
    def _ms_to_hms(self, ms: int) -> str:
        s = ms // 1000
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _ms_to_clock(self, ms: int) -> str:
        total_seconds = max(0, int(ms) // 1000)
        h, rem = divmod(total_seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _on_add_clicked(self):
        mainwin = self._main_window()
        if mainwin and hasattr(mainwin, "open_files_into_tile"):
            mainwin.open_files_into_tile(self)  # 🔹 이제 자기 자신만 채움

    def _add_button_theme(self) -> str:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            try:
                theme = str(app.property("multiPlayTheme") or "").strip().lower()
            except Exception:
                theme = ""
            if theme == "white":
                return "white"
            if theme == "black":
                return "black"
            if theme == "system":
                try:
                    lightness = int(app.palette().color(QtGui.QPalette.ColorRole.Window).lightness())
                    return "black" if lightness < 140 else "white"
                except Exception:
                    pass
        try:
            lightness = int(self.palette().color(QtGui.QPalette.ColorRole.Window).lightness())
        except Exception:
            lightness = 0
        return "black" if lightness < 140 else "white"

    def _refresh_add_button_style(self):
        button = getattr(self, "add_button", None)
        if button is None:
            return
        button.setObjectName("EmptyTileAddButton")
        button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        button.setAutoDefault(False)
        button.setDefault(False)
        button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        button.setFixedSize(56, 56)
        theme = self._add_button_theme()
        if theme == "white":
            button.setStyleSheet(
                """
                QPushButton#EmptyTileAddButton {
                    font-size: 28px;
                    font-weight: 500;
                    color: #415362;
                    background: rgba(255, 255, 255, 210);
                    border: 1px solid #C9D4DF;
                    border-radius: 28px;
                    padding: 0 0 3px 0;
                }
                QPushButton#EmptyTileAddButton:hover {
                    color: #1C2731;
                    background: #EEF3F7;
                    border: 1px solid #9FB2C5;
                }
                QPushButton#EmptyTileAddButton:pressed {
                    color: #17212A;
                    background: #E4EBF1;
                    border: 1px solid #8FA4B8;
                }
                """
            )
            shadow_color = QtGui.QColor(60, 80, 100, 30)
            shadow_blur = 16
        else:
            button.setStyleSheet(
                """
                QPushButton#EmptyTileAddButton {
                    font-size: 30px;
                    font-weight: 500;
                    color: rgba(255, 255, 255, 232);
                    background: rgba(16, 18, 22, 140);
                    border: 1px solid rgba(255, 255, 255, 34);
                    border-radius: 28px;
                    padding: 0 0 3px 0;
                }
                QPushButton#EmptyTileAddButton:hover {
                    color: rgba(255, 255, 255, 248);
                    background: rgba(28, 32, 38, 168);
                    border: 1px solid rgba(255, 255, 255, 52);
                }
                QPushButton#EmptyTileAddButton:pressed {
                    background: rgba(10, 12, 16, 176);
                    border: 1px solid rgba(255, 255, 255, 44);
                }
                """
            )
            shadow_color = QtGui.QColor(0, 0, 0, 96)
            shadow_blur = 20
        shadow = button.graphicsEffect()
        if not isinstance(shadow, QtWidgets.QGraphicsDropShadowEffect):
            shadow = QtWidgets.QGraphicsDropShadowEffect(button)
            button.setGraphicsEffect(shadow)
        shadow.setBlurRadius(shadow_blur)
        shadow.setOffset(0, 2)
        shadow.setColor(shadow_color)

    def _bind_tile_context_menu(self, widget):
        bind_tile_context_menu_impl(self, widget)

    def _finalize_tile_context_menu(self, menu):
        finalize_tile_context_menu_impl(self, menu)

    def _exec_tile_context_menu(self, menu, global_pos: QtCore.QPoint):
        exec_tile_context_menu_impl(self, menu, global_pos)

    def _show_tile_context_menu(self, global_pos: QtCore.QPoint):
        show_tile_context_menu_impl(self, global_pos)

    def _main_window(self):
        mainwin = self.window()
        if mainwin is not None and hasattr(mainwin, "config"):
            self._main_window_owner = mainwin
            return mainwin
        owner = getattr(self, "_main_window_owner", None)
        return owner if owner is not None and hasattr(owner, "config") else None

    def _canvas_host(self):
        mainwin = self._main_window()
        canvas = getattr(mainwin, "canvas", None)
        return canvas if canvas is not None else None

    def _overlay_stack_targets_info(self) -> tuple[List["VideoTile"], str]:
        canvas = self._canvas_host()
        if canvas is None or not hasattr(canvas, "get_selected_tiles"):
            return [], "none"

        def _collect(candidates) -> List["VideoTile"]:
            ordered: List["VideoTile"] = []
            seen: set[VideoTile] = set()
            for tile in candidates:
                if tile in seen or tile not in getattr(canvas, "tiles", []):
                    continue
                has_media = bool(getattr(tile, "playlist", None)) or bool(getattr(tile, "is_static_image", lambda: False)())
                if not has_media:
                    continue
                ordered.append(tile)
                seen.add(tile)
            return ordered

        selected_targets = _collect([self] + list(canvas.get_selected_tiles()))
        if len(selected_targets) >= 2:
            return selected_targets, "selected"

        all_media_targets = _collect([self] + list(getattr(canvas, "tiles", [])))
        if len(all_media_targets) >= 2:
            return all_media_targets, "all"
        return all_media_targets, "none"

    def _overlay_stack_targets(self) -> List["VideoTile"]:
        targets, _mode = self._overlay_stack_targets_info()
        return targets

    def _overlay_group_tiles(self) -> List["VideoTile"]:
        canvas = self._canvas_host()
        if canvas is None or not hasattr(canvas, "overlay_group_tiles"):
            return []
        group_id = str(getattr(canvas, "overlay_group_id_for_tile", lambda _tile: "")(self) or "").strip()
        if not group_id:
            return []
        return list(canvas.overlay_group_tiles(group_id))

    def _overlay_opacity_percent(self, tile: Optional["VideoTile"] = None) -> int:
        canvas = self._canvas_host()
        if canvas is None or not hasattr(canvas, "detached_window_for_tile"):
            return 100
        target = tile if tile is not None else self
        window = canvas.detached_window_for_tile(target)
        if window is None or not getattr(window, "overlay_active", lambda: False)():
            return 100
        try:
            return int(round(float(window.overlay_opacity()) * 100.0))
        except Exception:
            return 100

    def _overlay_global_apply_percent(self) -> int:
        canvas = self._canvas_host()
        if canvas is None or not hasattr(canvas, "overlay_global_apply_percent"):
            return 10
        try:
            return int(canvas.overlay_global_apply_percent())
        except Exception:
            return 10

    def _overlay_audio_mode(self) -> str:
        canvas = self._canvas_host()
        if canvas is None or not hasattr(canvas, "overlay_audio_mode_for_tile"):
            return "leader"
        try:
            return str(canvas.overlay_audio_mode_for_tile(self) or "leader")
        except Exception:
            return "leader"

    def _tile_window_opacity_percent(self) -> int:
        canvas = self._canvas_host()
        if canvas is not None and hasattr(canvas, "detached_window_for_tile"):
            try:
                window = canvas.detached_window_for_tile(self)
            except Exception:
                window = None
            if window is not None:
                try:
                    return int(round(float(window.window_opacity_value()) * 100.0))
                except Exception:
                    pass
        try:
            return int(round(float(getattr(self, "detached_window_opacity", 1.0)) * 100.0))
        except Exception:
            return 100

    def _overlay_dialog_parent(self):
        return overlay_dialog_parent_impl(self)

    def _dialog_available_rect_for_video(self) -> QtCore.QRect:
        return dialog_available_rect_for_video_impl(self)

    def _clamp_dialog_point(self, point: QtCore.QPoint, size: QtCore.QSize, available: QtCore.QRect) -> QtCore.QPoint:
        return clamp_dialog_point_impl(point, size, available)

    def _position_dialog_outside_video(self, dialog: QtWidgets.QDialog):
        position_dialog_outside_video_impl(self, dialog)

    def _prepare_overlay_dialog(self, dialog: QtWidgets.QDialog):
        prepare_overlay_dialog_impl(self, dialog)

    def _open_opacity_slider_dialog(self, *, title: str, current_percent: int, on_change):
        open_opacity_slider_dialog_impl(self, title=title, current_percent=current_percent, on_change=on_change)

    def _open_tile_window_opacity_dialog_from_context(self):
        open_tile_window_opacity_dialog_from_context_impl(self)

    def _open_overlay_opacity_dialog_from_context(self, *, tile: Optional["VideoTile"] = None):
        open_overlay_opacity_dialog_from_context_impl(self, target_tile=tile)

    def _overlay_layer_dialog_label(self, target_tile: "VideoTile", order: int, total: int) -> str:
        return overlay_layer_dialog_label_impl(self, target_tile, order, total)

    def _overlay_layer_opacity_items(self) -> List[tuple["VideoTile", str, int]]:
        return overlay_layer_opacity_items_impl(self)

    def _open_overlay_layer_opacity_dialog_from_context(self):
        open_overlay_layer_opacity_dialog_from_context_impl(self)

    def _open_overlay_global_apply_dialog_from_context(self):
        open_overlay_global_apply_dialog_from_context_impl(self)

    def _create_overlay_stack_from_context(self):
        create_overlay_stack_from_context_impl(self)

    def _clear_overlay_stack_from_context(self):
        clear_overlay_stack_from_context_impl(self)

    def _set_overlay_opacity_from_context(self, opacity: float, *, tile: Optional["VideoTile"] = None):
        canvas = self._canvas_host()
        if canvas is None or not hasattr(canvas, "set_overlay_opacity_for_tile"):
            return
        canvas.set_overlay_opacity_for_tile(tile if tile is not None else self, opacity)

    def _set_overlay_global_apply_from_context(self, value: int):
        set_overlay_global_apply_from_context_impl(self, value)

    def _apply_overlay_opacity_preset_from_context(self, preset_name: str, top_percent: int):
        apply_overlay_opacity_preset_from_context_impl(self, preset_name, top_percent)

    def _set_overlay_audio_mode_from_context(self, mode: str):
        set_overlay_audio_mode_from_context_impl(self, mode)

    def _set_tile_window_opacity_from_context(self, opacity: float):
        set_tile_window_opacity_from_context_impl(self, opacity)

    def _fit_media_size_from_context(self):
        fit_media_size_from_context_impl(self)

    def _trigger_mute_selected_tiles(self):
        trigger_mute_selected_tiles_impl(self)

    def _add_bookmark(self):
        add_bookmark_impl(self)

    def _open_url_stream_from_context(self):
        open_url_stream_from_context_impl(self)

    def _save_url_from_context(self):
        save_url_from_context_impl(self)

    def _jump_to_timecode_from_context(self):
        jump_to_timecode_from_context_impl(self)

    def _sync_other_tiles_to_this_timecode(self):
        sync_other_tiles_to_this_timecode_impl(self)

    def _open_focus_review_from_context(self):
        open_focus_review_from_context_impl(self)

    def _bookmark_marker_select_mode_active(self) -> bool:
        return bookmark_marker_select_mode_active_impl(self)

    def _sync_bookmark_marker_select_mode_from_cursor(self):
        sync_bookmark_marker_select_mode_from_cursor_impl(self)

    def _bookmark_snap_ms_for_slider_x(self, x: int, tolerance_px: int = 12) -> Optional[int]:
        return bookmark_snap_ms_for_slider_x_impl(self, x, tolerance_px)

    def _show_preview_for_slider_x(self, position_ms: int, y: int = 0):
        show_preview_for_slider_x_impl(self, position_ms, y)

    def _activate_bookmark_marker_positions(self, positions, *, avoid_repeat: bool = False):
        activate_bookmark_marker_positions_impl(self, positions, avoid_repeat=avoid_repeat)

    def _handle_bookmark_marker_click(self, event: QtGui.QMouseEvent) -> bool:
        return handle_bookmark_marker_click_impl(self, event)

    def refresh_bookmark_marks(self, *, force: bool = False, length_ms: Optional[int] = None):
        refresh_bookmark_marks_impl(self, force=force, length_ms=length_ms)

    def _ensure_seek_preview_worker(self):
        return ensure_seek_preview_worker_impl(self)

    def _dialog_start_dir(self) -> str:
        return dialog_start_dir_impl(self)

    def _remember_dialog_dir(self, path: str):
        remember_dialog_dir_impl(self, path)

    def _generate_subtitle_from_context(self):
        generate_subtitle_from_context_impl(self)

    def _translate_subtitle_from_context(self):
        translate_subtitle_from_context_impl(self)

    def _is_image_path(self, path: Optional[str]) -> bool:
        return is_image_path_impl(self, path)

    def _is_animated_image_path(self, path: Optional[str]) -> bool:
        return is_animated_image_path_impl(self, path)

    def is_static_image(self) -> bool:
        return is_static_image_impl(self)

    def _set_image_source_pixmap(self, pixmap: QtGui.QPixmap):
        set_image_source_pixmap_impl(self, pixmap)

    def _set_image_movie(self, movie: Optional[QtGui.QMovie]):
        set_image_movie_impl(self, movie)

    def _on_image_movie_frame_changed(self, _frame_no: int):
        on_image_movie_frame_changed_impl(self, _frame_no)

    def _current_image_export_pixmap(self) -> Optional[QtGui.QPixmap]:
        return current_image_export_pixmap_impl(self)

    def _refresh_image_display(self):
        refresh_image_display_impl(self)

    def _clear_image_display(self):
        clear_image_display_impl(self)

    def _set_image_mode_enabled(self, enabled: bool):
        set_image_mode_enabled_impl(self, enabled)

    def current_media_pixel_size(self) -> Optional[QtCore.QSize]:
        return current_media_pixel_size_impl(self)

    def target_video_size_for_window_fit(self) -> Optional[QtCore.QSize]:
        return target_video_size_for_window_fit_impl(self)

    def _notify_playlist_changed(self, *, focus_mainwin: bool = True):
        mainwin = self._main_window()
        if mainwin is None:
            return
        try:
            if hasattr(mainwin, "request_playlist_refresh"):
                mainwin.request_playlist_refresh(delay_ms=0)
            else:
                mainwin.update_playlist()
        except Exception:
            pass
        if focus_mainwin:
            try:
                mainwin.setFocus()
            except Exception:
                pass

    def _restart_main_cursor_hide_timer_if_needed(self):
        mainwin = self._main_window()
        if mainwin is None:
            return
        try:
            is_fullscreen = bool(mainwin.windowState() & QtCore.Qt.WindowState.WindowFullScreen) or mainwin.isFullScreen()
        except Exception:
            is_fullscreen = False
        if not is_fullscreen:
            return
        timer = getattr(mainwin, "cursor_hide_timer", None)
        if timer is None:
            return
        # Fullscreen-specific workaround: after next/previous media opens, the old cursor-hide
        # timer may no longer fire again until the pointer moves. Restart it so the existing
        # hide logic gets another chance without requiring mouse movement.
        try:
            timer.start()
        except Exception:
            pass
        for delay_ms in (120, 320):
            try:
                QtCore.QTimer.singleShot(delay_ms, timer.start)
            except Exception:
                pass

    def _video_widget_global_rect(self) -> QtCore.QRect:
        top_left = self.video_widget.mapToGlobal(QtCore.QPoint(0, 0))
        return QtCore.QRect(top_left, self.video_widget.size())

    def _pulse_cursor_bridge_overlay_if_needed(self):
        overlay = getattr(self, "_cursor_bridge_overlay", None)
        if overlay is None:
            return
        # Only pulse when the pointer is already inside the video surface. This reproduces the
        # user's manual workaround of nudging/re-entering the video area after a media switch.
        try:
            if not self._video_widget_global_rect().contains(QtGui.QCursor.pos()):
                overlay.hide()
                return
        except Exception:
            return
        try:
            top = self.window()
            if top is not None:
                overlay.setCursor(top.cursor().shape())
        except Exception:
            pass
        try:
            overlay.setGeometry(self.video_widget.geometry())
            overlay.show()
            overlay.raise_()
        except Exception:
            return
        try:
            self._cursor_bridge_overlay_timer.start(240)
        except Exception:
            pass

    def _append_media_paths(self, paths: List[str]):
        append_media_paths_impl(self, paths)

    def _collect_video_files(self, folder: str) -> List[str]:
        return collect_video_files_impl(self, folder)

    def _normalize_media_path(self, path: str) -> str:
        return normalize_media_path_impl(path)

    def get_external_subtitle_for_path(self, media_path: str) -> Optional[str]:
        return get_external_subtitle_for_path_impl(self, media_path)

    def pop_external_subtitle_for_path(self, media_path: str) -> Optional[str]:
        return pop_external_subtitle_for_path_impl(self, media_path)

    def set_external_subtitle_for_path(
        self,
        media_path: str,
        subtitle_path: Optional[str],
        *,
        overwrite: bool = False,
    ):
        set_external_subtitle_for_path_impl(self, media_path, subtitle_path, overwrite=overwrite)

    def _current_playlist_path(self) -> Optional[str]:
        return current_playlist_path_impl(self)

    def _open_subtitle_file(self):
        open_subtitle_file_impl(self)

    def _apply_external_subtitle_to_player(self, subtitle_path: str) -> bool:
        return apply_external_subtitle_to_player_impl(self, subtitle_path)

    def _apply_saved_subtitle_option(self, media, media_path: str):
        apply_saved_subtitle_option_impl(self, media, media_path)

    def _vlc_base_instance_args(self) -> tuple[str, ...]:
        return vlc_base_instance_args_impl(self)

    def _transform_instance_args(self, mode: str) -> tuple[str, ...]:
        return transform_instance_args_impl(self, mode)

    def _create_mediaplayer(self, instance):
        create_mediaplayer_impl(self, instance)

    def _release_mediaplayer(self, release_owned_instance: bool = True):
        release_mediaplayer_impl(self, release_owned_instance=release_owned_instance)

    def _rebuild_player_for_transform_mode(self):
        rebuild_player_for_transform_mode_impl(self)

    def _pos_to_str(self, pos: float, length_ms: int) -> str:
        if length_ms <= 0 or pos is None or pos < 0 or pos > 1: return "0_0"
        ms = int(pos * length_ms)
        s = ms // 1000
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        if h > 0:
            return f"{h}h{m}m{s}s"
        return f"{m}m{s}s"

    def current_playback_ms(self) -> int:
        try:
            current_ms = int(self.mediaplayer.get_time() or -1)
        except Exception:
            current_ms = -1
        if current_ms >= 0:
            return current_ms
        try:
            position = float(self.mediaplayer.get_position())
        except Exception:
            position = -1.0
        try:
            length_ms = int(self.mediaplayer.get_length() or 0)
        except Exception:
            length_ms = 0
        if length_ms > 0 and 0.0 <= position <= 1.0:
            return max(0, int(round(position * length_ms)))
        return 0

    def _current_media_length_ms(self) -> int:
        try:
            return int(self.mediaplayer.get_length() or 0)
        except Exception:
            return 0

    def _sync_seek_ui(self, target_ms: int, *, length_ms: Optional[int] = None, show_overlay: bool = True, sync_slider: bool = True):
        target_ms = max(0, int(target_ms))
        if length_ms is None or int(length_ms) <= 0:
            length_ms = self._current_media_length_ms()
        else:
            length_ms = int(length_ms)
        if length_ms > 0:
            target_ms = min(target_ms, max(0, length_ms - 1))
            if sync_slider:
                try:
                    self.sld_pos.blockSignals(True)
                    self.sld_pos.setValue(int((float(target_ms) / float(max(1, length_ms))) * self.sld_pos.maximum()))
                finally:
                    self.sld_pos.blockSignals(False)
            self.lbl_time.setText(f"{self._ms_to_hms(target_ms)} / {self._ms_to_hms(length_ms)}")
        if show_overlay:
            self._show_seek_overlay_ms(target_ms)

    def _paused_scrub_timer(self):
        timer = getattr(self, "_paused_scrub_seek_timer", None)
        if timer is None:
            timer = QtCore.QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._commit_paused_scrub_seek)
            self._paused_scrub_seek_timer = timer
        return timer

    def _schedule_paused_scrub_seek(self, target_ms: int):
        self._paused_scrub_target_ms = int(max(0, target_ms))
        timer = self._paused_scrub_timer()
        if not timer.isActive():
            timer.start(35)

    def _cancel_paused_scrub_seek(self):
        timer = getattr(self, "_paused_scrub_seek_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()

    def _commit_paused_scrub_seek(self):
        target_ms = int(getattr(self, "_paused_scrub_target_ms", -1))
        if target_ms < 0:
            return
        self.seek_ms(target_ms, play=False, show_overlay=False)

    # --- 위치 이동 --- #
    def move_position(self, delta_s: float):
        if self.mediaplayer.get_media() is None or self.mediaplayer.get_length() <= 0:
            return
        current_ms = self.mediaplayer.get_time()
        length_ms = self.mediaplayer.get_length()
        new_ms = max(0, min(length_ms - 1, current_ms + int(delta_s * 1000)))
        self.mediaplayer.set_time(new_ms)
        new_pos = new_ms / length_ms
        self.sld_pos.setValue(int(new_pos * self.sld_pos.maximum()))
        self.lbl_time.setText(f"{self._ms_to_hms(new_ms)} / {self._ms_to_hms(length_ms)}")
        self._show_seek_overlay_ms(new_ms)

    def bind_hwnd(self, force: bool = False):
        bind_hwnd_impl(self, force=force)

    def _display_geometry_spec(self) -> Optional[str]:
        return display_geometry_spec_impl(self)

    def _rebuild_display_mode_menu(self):
        rebuild_display_mode_menu_impl(self)

    def _update_display_mode_button(self):
        update_display_mode_button_impl(self)

    def _rebuild_transform_mode_menu(self):
        rebuild_transform_mode_menu_impl(self)

    def _update_transform_mode_button(self):
        update_transform_mode_button_impl(self)

    def cycle_display_mode(self):
        cycle_display_mode_impl(self)

    def set_display_mode(self, mode: str):
        set_display_mode_impl(self, mode)

    def cycle_transform_mode(self):
        cycle_transform_mode_impl(self)

    def set_transform_mode(self, mode: str):
        set_transform_mode_impl(self, mode)

    def set_zoom_percent(self, percent: int):
        set_zoom_percent_impl(self, percent)

    def _apply_display_mode(self):
        apply_display_mode_impl(self)

    def _should_use_hw_accel(self) -> bool:
        return should_use_hw_accel_impl(self)

    def _apply_media_hw_options(self, media):
        apply_media_hw_options_impl(self, media)

    def refresh_track_menus(self):
        refresh_track_menus_impl(self)

    def _populate_track_menus(self, audio_menu=None, subtitle_menu=None):
        return populate_track_menus_impl(self, audio_menu=audio_menu, subtitle_menu=subtitle_menu)

    def set_audio_track(self, track_id: int):
        set_audio_track_impl(self, track_id)

    def set_subtitle_track(self, track_id: int):
        set_subtitle_track_impl(self, track_id)

    def add_to_playlist(self, path: str, play_now: bool = False):
        return add_to_playlist_impl(self, path, play_now=play_now)

    def set_playlist_entry_start_position(self, index: int, position_ms: Optional[int]):
        set_playlist_entry_start_position_impl(self, index, position_ms)

    def set_playlist_entry_bookmark_positions(self, index: int, positions_ms, *, cursor: Optional[int] = None):
        set_playlist_entry_bookmark_positions_impl(self, index, positions_ms, cursor=cursor)

    def set_playlist_entry_bookmark_targets(self, index: int, bookmark_targets, *, cursor: Optional[int] = None):
        set_playlist_entry_bookmark_targets_impl(self, index, bookmark_targets, cursor=cursor)

    def playlist_entry_bookmark_positions(self, index: int) -> List[int]:
        return playlist_entry_bookmark_positions_impl(self, index)

    def playlist_entries_with_start_positions(self):
        return playlist_entries_with_start_positions_impl(self)

    def select_playlist_entry_bookmark(self, index: int, bookmark_subindex: Optional[int] = None):
        select_playlist_entry_bookmark_impl(self, index, bookmark_subindex)

    def set_playlist_entry_bookmark_cursor(self, index: int, cursor: int):
        set_playlist_entry_bookmark_cursor_impl(self, index, cursor)

    def _clear_playlist_entry_start_positions(self):
        clear_playlist_entry_start_positions_impl(self)

    def _advance_current_playlist_bookmark(self, direction: int) -> bool:
        return advance_current_playlist_bookmark_impl(self, direction)

    def _apply_current_playlist_start_position(self):
        apply_current_playlist_start_position_impl(self)

    def _prepend_files_to_playlist_and_play(self, files: List[str]) -> bool:
        return prepend_files_to_playlist_and_play_impl(self, files)

    def set_media(self, path: str, *, show_error_dialog: bool = True) -> bool:
        try:
            if not bool(set_media_impl(self, path)):
                self._last_set_media_error = tr(self, "미디어를 열지 못했습니다.")
                if show_error_dialog:
                    QtWidgets.QMessageBox.warning(self, tr(self, "재생 실패"), self._last_set_media_error)
                return False
            self._last_set_media_error = ""
            return True
        except Exception as exc:
            self._last_set_media_error = str(exc) or exc.__class__.__name__
            if show_error_dialog:
                QtWidgets.QMessageBox.warning(self, tr(self, "재생 실패"), self._last_set_media_error)
            return False

    def play(self):
        play_impl(self)
        self._notify_canvas_playback_intent(True)

    def pause(self):
        pause_impl(self)
        self._notify_canvas_playback_intent(False)

    def toggle_play(self):
        toggle_play_impl(self)

    def stop(self):
        stop_impl(self)
        self._notify_canvas_playback_intent(False)

    def _notify_canvas_playback_intent(self, playing: bool):
        if bool(getattr(self, "_suppress_playback_notify", False)):
            return
        host = self.parentWidget()
        while host is not None:
            callback = getattr(host, "on_tile_playback_intent_changed", None)
            if callable(callback):
                try:
                    callback(self, bool(playing))
                except Exception:
                    pass
                return
            host = host.parentWidget()
        window = self.window()
        callback = getattr(window, "on_tile_playback_intent_changed", None)
        if callable(callback):
            try:
                callback(self, bool(playing))
            except Exception:
                pass

    # ✅ on_volume: "타일 볼륨 상태" 갱신 + 합성 적용
    def on_volume(self, vol: int):
        v = max(0, min(120, int(vol)))
        # 슬라이더는 UI 동기화만 (시그널 루프 방지)
        try:
            self.sld_vol.blockSignals(True)
            self.sld_vol.setValue(v)
        finally:
            self.sld_vol.blockSignals(False)
        self.tile_volume = v
        self._apply_tile_volume()  # ← 여기서 마스터/뮤트 합성

    def snap_volume_to_step(self):
        v = self.sld_vol.value()
        snapped = int(round(v / 5) * 5)
        snapped = max(0, min(120, snapped))
        if snapped != v:
            self.sld_vol.setValue(snapped)
        self.on_volume(snapped)

    def snap_volume_preview(self, v: int):
        snapped = int(round(v / 5) * 5)
        self.on_volume(snapped)

    # ✅ 5단계 증감도 현재 플레이어 볼륨이 아니라 "타일 볼륨" 기준
    def adjust_volume_step(self, direction: int):
        new_v = max(0, min(120, int(self.tile_volume) + (5 * direction)))
        self.sld_vol.setValue(new_v)  # valueChanged -> _on_tile_volume_changed -> _apply_tile_volume()
    def update_position(self):
        self._update_play_button()
        try:
            bookmark_length_ms = int(self.mediaplayer.get_length() or 0)
        except Exception:
            bookmark_length_ms = 0
        self.refresh_bookmark_marks(length_ms=bookmark_length_ms)
        if self.mediaplayer.is_playing() and not self.sld_pos.isSliderDown():
            pos = self.mediaplayer.get_position()
            if pos != -1:
                self.sld_pos.setValue(int(pos * self.sld_pos.maximum()))
                length_ms = self.mediaplayer.get_length()
                current_ms = int(pos * length_ms)
                self.lbl_time.setText(f"{self._ms_to_hms(current_ms)} / {self._ms_to_hms(length_ms)}")
            if self.loop_enabled and self.posA is not None and self.posB is not None:
                if pos >= self.posB:
                    self.mediaplayer.set_position(self.posA)
            elif bool(getattr(self, "_playlist_bookmark_guard_active", False)):
                end_ms = getattr(self, "_playlist_bookmark_end_ms", None)
                if end_ms is not None and current_ms >= max(0, int(end_ms) - 80):
                    self._playlist_bookmark_guard_active = False
                    self.pause()
                    self.seek_ms(int(end_ms), play=False, show_overlay=False)

    def set_position(self, pos: Optional[float] = None, show_overlay: bool = True):
        if pos is None:
            pos = self.sld_pos.value() / float(max(1, self.sld_pos.maximum()))
        pos = max(0.0, min(1.0, float(pos)))
        was_playing = bool(self.mediaplayer.is_playing())
        length_ms = self._current_media_length_ms()
        target_ms = int(pos * length_ms) if length_ms > 0 else None
        slider = getattr(self, "sld_pos", None)
        slider_down = bool(slider is not None and slider.isSliderDown())

        if not was_playing and target_ms is not None:
            self._sync_seek_ui(target_ms, length_ms=length_ms, show_overlay=show_overlay, sync_slider=False)
            if slider_down:
                self._schedule_paused_scrub_seek(target_ms)
                return
            self._cancel_paused_scrub_seek()
            self.seek_ms(target_ms, play=False, show_overlay=False)
            return

        desired_rate, needs_seek_stabilize = self._prepare_seek_playback_rate(play=was_playing)
        self.mediaplayer.set_position(pos)
        if target_ms is not None:
            self._sync_seek_ui(target_ms, length_ms=length_ms, show_overlay=show_overlay, sync_slider=False)
        if needs_seek_stabilize:
            self._nudge_play_after_seek()
            self._schedule_seek_rate_restore(desired_rate, play=was_playing)
        if was_playing:
            self.update_position()

    def set_A(self):
        pos = self.mediaplayer.get_position()
        if not isinstance(pos, float) or pos < 0:
            return
        self.posA = pos
        self.posB = None
        self.loop_enabled = False
        self._update_ab_controls()

    def set_B(self):
        pos = self.mediaplayer.get_position()
        if not isinstance(pos, float) or pos < 0:
            return
        self.posB = pos
        if self.posA is not None and self.posB is not None and self.posB < self.posA:
            self.posA, self.posB = self.posB, self.posA
        self.loop_enabled = self.posA is not None and self.posB is not None
        self._update_ab_controls()

    def set_ab_range_ms(self, start_ms: int, end_ms: int, seek_to_start: bool = True) -> bool:
        start_ms = max(0, int(start_ms))
        end_ms = max(0, int(end_ms))
        if end_ms <= start_ms:
            return False

        try:
            length_ms = int(self.mediaplayer.get_length() or 0)
        except Exception:
            length_ms = 0
        if length_ms <= 0:
            path = self._current_media_path()
            if path and os.path.exists(path):
                try:
                    import cv2  # type: ignore

                    cap = cv2.VideoCapture(path)
                    if cap.isOpened():
                        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                        total_frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
                        if fps > 1e-6 and total_frames > 1.0:
                            length_ms = max(0, int(round((total_frames / fps) * 1000.0)))
                    cap.release()
                except Exception:
                    length_ms = 0
        if length_ms <= 0:
            return False

        start_ms = min(start_ms, max(0, length_ms - 1))
        end_ms = min(end_ms, length_ms)
        if end_ms <= start_ms:
            end_ms = min(length_ms, start_ms + 1)
        if end_ms <= start_ms:
            return False

        self.posA = max(0.0, min(1.0, float(start_ms) / float(length_ms)))
        self.posB = max(0.0, min(1.0, float(end_ms) / float(length_ms)))
        if self.posB < self.posA:
            self.posA, self.posB = self.posB, self.posA
        self.loop_enabled = self.posA is not None and self.posB is not None
        self._update_ab_controls()

        if seek_to_start:
            try:
                was_playing = bool(self.mediaplayer.is_playing())
            except Exception:
                was_playing = False
            self.seek_ms(start_ms, play=was_playing, show_overlay=True)
        return True

    def cycle_ab_loop(self):
        if self.mediaplayer.get_media() is None:
            return
        if self.loop_enabled and self.posA is not None and self.posB is not None:
            self.toggle_loop(False)
            return
        if self.posA is None:
            self.set_A()
            return
        self.set_B()

    def _set_toggle_button_style(self, button, active: bool):
        if button is None:
            return
        button.setStyleSheet("color: #1DB954; font-weight: 700;" if active else "")

    def _update_play_button(self):
        is_playing = False
        try:
            is_playing = bool(self.mediaplayer.is_playing())
        except Exception:
            is_playing = False
        self.btn_play.setText("⏸" if is_playing else "▶")
        self._set_toggle_button_style(self.btn_play, is_playing)

    def _update_ab_controls(self):
        if self.loop_enabled and self.posA is not None and self.posB is not None:
            self.btn_A.setText("AB")
            self._set_toggle_button_style(self.btn_A, True)
            return
        if self.posA is not None:
            self.btn_A.setText("A")
            self._set_toggle_button_style(self.btn_A, True)
            return
        self.btn_A.setText("A")
        self._set_toggle_button_style(self.btn_A, False)

    # 구간반복 토글
    def toggle_loop(self, checked):
        self.loop_enabled = checked
        if not (checked and self.posA is not None and self.posB is not None):
            self.loop_enabled = False
            self.posA = None
            self.posB = None
        self._update_ab_controls()

    @property
    def repeat_one_enabled(self) -> bool:
        return self.repeat_mode == "single"

    @property
    def playlist_repeat_enabled(self) -> bool:
        return self.repeat_mode == "playlist"

    def cycle_repeat_mode(self):
        next_mode = {
            "off": "single",
            "single": "playlist",
            "playlist": "off",
        }.get(self.repeat_mode, "off")
        self.set_repeat_mode(next_mode)

    def set_repeat_mode(self, mode: str):
        mode = mode if mode in self.REPEAT_MODES else "off"
        self.repeat_mode = mode
        self._update_repeat_button()

    def set_repeat_one_enabled(self, enabled: bool):
        if enabled:
            self.set_repeat_mode("single")
        elif self.repeat_mode == "single":
            self.set_repeat_mode("off")

    def set_playlist_repeat_enabled(self, enabled: bool):
        if enabled:
            self.set_repeat_mode("playlist")
        elif self.repeat_mode == "playlist":
            self.set_repeat_mode("off")

    def _update_repeat_button(self):
        btn = getattr(self, "btn_repeat_mode", None)
        if btn is None:
            return
        labels = {
            "off": tr(self, "반복: 끔"),
            "single": tr(self, "반복: 1개"),
            "playlist": tr(self, "반복: 목록"),
        }
        tooltips = {
            "off": tr(self, "현재 상태: 반복 안 함. 클릭하면 현재 영상 1개 반복으로 변경"),
            "single": tr(self, "현재 상태: 현재 영상 1개 반복. 클릭하면 플레이리스트 반복으로 변경"),
            "playlist": tr(self, "현재 상태: 플레이리스트 반복. 클릭하면 반복 안 함으로 변경"),
        }
        active = self.repeat_mode != "off"
        btn.setText(labels.get(self.repeat_mode, labels["off"]))
        btn.setToolTip(tooltips.get(self.repeat_mode, tooltips["off"]))
        btn.setStyleSheet("color: green; font-weight: bold;" if active else "")

    def on_finished(self, event):
        action = "restart_current" if self.repeat_mode == "single" else "play_next"
        QtCore.QMetaObject.invokeMethod(self, action, QtCore.Qt.ConnectionType.QueuedConnection)

    def shutdown(self):
        # 타이머/툴팁 등 UI 타이머 중지
        try:
            if hasattr(self, "timer") and self.timer is not None:
                self.timer.stop()
        except Exception:
            pass
        dlg = getattr(self, "_sceneDlg", None)
        if dlg is not None:
            try:
                if hasattr(dlg, "shutdown_for_app_close"):
                    dlg.shutdown_for_app_close(timeout_ms=5000)
            except Exception:
                pass
            try:
                dlg.close()
            except Exception:
                pass
            try:
                if getattr(self, "_sceneDlg", None) is dlg:
                    self._sceneDlg = None
            except Exception:
                pass
        stop_export_worker_impl(self)
        stop_subtitle_generation_worker_impl(self)
        stop_subtitle_translation_worker_impl(self)
        stop_url_download_worker_impl(self)
        shutdown_seek_preview_impl(self)

        self._release_mediaplayer(release_owned_instance=True)
    @QtCore.pyqtSlot()
    def restart_current(self):
        if not self.playlist:
            return
        if not (0 <= self.current_index < len(self.playlist)):
            self.current_index = 0
        current_path = self.playlist[self.current_index]
        if self.set_media(current_path):
            self._apply_current_playlist_start_position()
            self.play()

    @QtCore.pyqtSlot()
    def play_next(self):
        if not self.playlist:
            return
        if self._advance_current_playlist_bookmark(1):
            current_path = self.playlist[self.current_index]
            if self.set_media(current_path):
                self._apply_current_playlist_start_position()
                self.play()
            return
        if self.current_index < 0:
            self.current_index = 0
        elif self.current_index + 1 < len(self.playlist):
            self.current_index += 1
        elif self.playlist_repeat_enabled:
            self.current_index = 0
        else:
            self.current_index = 0
            self.select_playlist_entry_bookmark(self.current_index, 0)
            first_path = self.playlist[self.current_index]
            if self.set_media(first_path):
                self._apply_current_playlist_start_position()
                self._update_play_button()
            return
        self.select_playlist_entry_bookmark(self.current_index, 0)
        next_path = self.playlist[self.current_index]
        if self.set_media(next_path):
            self._apply_current_playlist_start_position()
            self.play()

    @QtCore.pyqtSlot()
    def play_previous(self):
        if not self.playlist:
            return
        if self._advance_current_playlist_bookmark(-1):
            current_path = self.playlist[self.current_index]
            if self.set_media(current_path):
                self._apply_current_playlist_start_position()
                self.play()
            return
        if self.current_index < 0:
            self.current_index = 0
        elif self.current_index > 0:
            self.current_index -= 1
        elif self.playlist_repeat_enabled:
            self.current_index = len(self.playlist) - 1
        else:
            return
        positions = self.playlist_entry_bookmark_positions(self.current_index)
        if positions:
            self.set_playlist_entry_bookmark_cursor(self.current_index, len(positions) - 1)
        prev_path = self.playlist[self.current_index]
        if self.set_media(prev_path):
            self._apply_current_playlist_start_position()
            self.play()

    def adjust_rate(self, delta: float):
        new_rate = round(self.playback_rate + delta, 1)
        new_rate = max(0.5, min(4.0, new_rate))
        self.playback_rate = new_rate
        self.mediaplayer.set_rate(self.playback_rate)
        self.lbl_rate.setText(tr(self, "배속: {rate:.1f}x", rate=self.playback_rate))
        self.lbl_rate.setStyleSheet("color: red; font-weight: bold;" if self.playback_rate != 1.0 else "")
        self._show_rate_overlay()

    def _prepare_seek_playback_rate(self, *, play: bool) -> tuple[float, bool]:
        desired_rate = float(getattr(self, "playback_rate", 1.0) or 1.0)
        needs_seek_stabilize = bool(play and desired_rate < 1.0)
        if not needs_seek_stabilize:
            return desired_rate, False
        try:
            self.mediaplayer.set_rate(1.0)
        except Exception:
            pass
        return desired_rate, True

    def _nudge_play_after_seek(self, token: Optional[int] = None):
        for delay in (0, 45, 120):
            QtCore.QTimer.singleShot(delay, lambda token=token: self._resume_after_seek(token))

    def _resume_after_seek(self, token: Optional[int]):
        if token is not None and token != getattr(self, "_retry_seek_token", token):
            return
        m = getattr(self, "mediaplayer", None)
        if not m:
            return
        try:
            m.play()
        except Exception:
            pass

    def _schedule_seek_rate_restore(self, desired_rate: float, *, play: bool, token: Optional[int] = None):
        if desired_rate <= 0:
            return
        restore_token = getattr(self, "_seek_rate_restore_token", 0) + 1
        self._seek_rate_restore_token = restore_token
        delays = self._seek_rate_restore_delays(desired_rate)
        for delay in delays:
            QtCore.QTimer.singleShot(
                delay,
                lambda restore_token=restore_token, desired_rate=desired_rate, play=play, token=token:
                    self._restore_rate_after_seek(restore_token, desired_rate, play=play, token=token),
            )

    def _seek_rate_restore_delays(self, desired_rate: float) -> tuple[int, ...]:
        if desired_rate <= 0.5:
            return (320, 520)
        if desired_rate < 0.75:
            return (260, 420)
        if desired_rate < 1.0:
            return (70, 150)
        return (0, 70)

    def _restore_rate_after_seek(self, restore_token: int, desired_rate: float, *, play: bool, token: Optional[int]):
        if restore_token != getattr(self, "_seek_rate_restore_token", restore_token):
            return
        if token is not None and token != getattr(self, "_retry_seek_token", token):
            return
        m = getattr(self, "mediaplayer", None)
        if not m:
            return
        try:
            m.set_rate(float(desired_rate))
        except Exception:
            pass
        if not play:
            return
        try:
            if not m.is_playing():
                m.play()
        except Exception:
            pass

    def _get_export_paths(self, ext: str) -> Optional[str]:
        return get_export_path_impl(self, ext)

    def capture_screenshot(self):
        capture_screenshot_impl(self)

    def save_frame_set(self):
        save_frame_set_impl(self)

    def export_gif(self):
        export_gif_impl(self)

    def export_clip(self):
        export_clip_impl(self)

    def export_audio_clip(self):
        export_audio_clip_impl(self)

    def show_controls(self, visible: bool):
        self._controls_requested_visible = bool(visible)
        self._apply_controls_visibility()

    def minimumSizeHint(self) -> QtCore.QSize:
        if bool(getattr(self, "_compact_mode", False)) or bool(
            getattr(getattr(self, "controls_container", None), "isHidden", lambda: False)()
        ):
            return QtCore.QSize(160, 90)
        return QtCore.QSize(220, 120)

    # ---------- 상태 직렬화 ---------- #
    def to_state(self) -> Dict[str, Any]:
        return to_state_impl(self)

    def _restore_session_media_state(self, position: Optional[float], playing: bool):
        restore_session_media_state_impl(self, position, playing)

    def from_state(self, state):
        from_state_impl(self, state)

    def set_border_visible(self, visible: bool):
        if visible:
            self.setStyleSheet("border: 1px solid black;")
        else:
            self.setStyleSheet("border: none;")


    def set_compact_mode(self, enabled: bool):
        """영상만 보이도록 UI(컨트롤, 슬라이더) 온오프"""
        self._compact_mode = bool(enabled)
        self._apply_controls_visibility()

    def _toggle_volume_slider(self, checked: bool):
        if hasattr(self, "sld_vol"):
            self.sld_vol.setVisible(
                bool(checked)
                and bool(getattr(self, "_controls_requested_visible", True))
                and not bool(getattr(self, "_compact_mode", False))
            )

    def _apply_controls_visibility(self):
        controls_container = getattr(self, "controls_container", None)
        if controls_container is None:
            return
        visible = bool(getattr(self, "_controls_requested_visible", True)) and not bool(
            getattr(self, "_compact_mode", False)
        )
        if controls_container.isHidden() != (not visible):
            controls_container.setVisible(visible)
        if hasattr(self, "sld_vol") and hasattr(self, "btn_volume_toggle"):
            self.sld_vol.setVisible(visible and self.btn_volume_toggle.isChecked())


    def _update_add_button(self):
        """playlist가 비었을 때 + 버튼 표시"""
        if not self.playlist:
            if not self.add_button:
                self.add_button = QPushButton("+", self)
                self.add_button.clicked.connect(self._on_add_clicked)
                self._bind_tile_context_menu(self.add_button)
            self._refresh_add_button_style()

            # 버튼 중앙 배치
            rect = self.rect()
            self.add_button.move(
                rect.center().x() - self.add_button.width() // 2,
                rect.center().y() - self.add_button.height() // 2
            )
            self.add_button.show()
            self.add_button.raise_()  # 항상 맨 위로
        else:
            if self.add_button:
                self.add_button.hide()

    def resizeEvent(self, event):
        """타일 리사이즈 시 + 버튼도 중앙으로 이동"""
        super().resizeEvent(event)
        self._update_add_button()
        if self.add_button and self.add_button.isVisible():
            rect = self.rect()
            self.add_button.move(
                rect.center().x() - self.add_button.width() // 2,
                rect.center().y() - self.add_button.height() // 2
            )
        self._place_mute_overlay()
        self._place_seek_overlay()
        self._place_volume_overlay()
        self._place_rate_overlay()
        self._place_status_overlay()
        try:
            self._cursor_bridge_overlay.setGeometry(self.video_widget.geometry())
        except Exception:
            pass
        try:
            self.image_overlay.setGeometry(self.video_widget.geometry())
        except Exception:
            pass
        self._refresh_image_display()
        self._apply_display_mode()

    def _add_files(self):
        """파일 선택창 열고 playlist 채우기"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            tr(self, "미디어 파일 추가"),
            self._dialog_start_dir(),
            media_file_dialog_filter_impl(),
        )
        if not files:
            return
        self._remember_dialog_dir(os.path.dirname(files[0]))
        mainwin = self._main_window()
        if mainwin is not None and hasattr(mainwin, "_push_recent_media_many"):
            mainwin._push_recent_media_many(files, kind="path")
        self._append_media_paths(files)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, tr(self, "미디어 폴더 추가"), self._dialog_start_dir())
        if not folder:
            return
        self._remember_dialog_dir(folder)
        files = self._collect_video_files(folder)
        if not files:
            QtWidgets.QMessageBox.warning(
                self,
                tr(self, "안내"),
                tr(self, "선택한 폴더(하위 포함)에 미디어 파일이 없습니다."),
            )
            return
        self._append_media_paths(files)

    def clear_playlist(self):
        clear_playlist_impl(self)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls():
            # 파일 드랍만 허용
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent):
        urls = event.mimeData().urls()
        if not urls:
            return

        files = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if not files:
            return
        mainwin = self._main_window()
        if mainwin is not None and hasattr(mainwin, "_push_recent_media_many"):
            mainwin._push_recent_media_many(files, kind="path")

        has_active_playlist = bool(self.playlist) and bool(
            self._current_playlist_path() or (0 <= self.current_index < len(self.playlist))
        )
        if has_active_playlist:
            if self._prepend_files_to_playlist_and_play(files):
                event.acceptProposedAction()
                return

        # 여러 개 드랍 가능 → 순서대로 playlist에 추가
        for i, path in enumerate(files):
            play_now = (i == 0 and not self.playlist)  # 첫 파일 + 비어있으면 자동재생
            self.add_to_playlist(path, play_now=play_now)

        self._update_add_button()
        self._notify_playlist_changed()
        event.acceptProposedAction()

    def _cancel_seek_preview_request(self):
        cancel_seek_preview_request_impl(self)

    def _drag_preview_request(self):
        return drag_preview_request_impl(self)

    def _scale_drag_preview_pixmap(
        self,
        pixmap: Optional[QtGui.QPixmap],
        target_w: int,
        target_h: int,
    ) -> Optional[QtGui.QPixmap]:
        return scale_drag_preview_pixmap_impl(self, pixmap, target_w, target_h)

    def _video_widget_drag_fallback_pixmap(self, target_w: int, target_h: int) -> Optional[QtGui.QPixmap]:
        return video_widget_drag_fallback_pixmap_impl(self, target_w, target_h)

    def _quantize_seek_preview_ms(self, ms: int, length_ms: int, slider_width: int) -> int:
        return quantize_seek_preview_ms_impl(self, ms, length_ms, slider_width)

    def _seek_preview_cache_key(self, path: str, ms: int, w: int, h: int):
        return seek_preview_cache_key_impl(self, path, ms, w, h)

    def _lookup_seek_preview_cache(self, key):
        return lookup_seek_preview_cache_impl(self, key)

    def _remember_seek_preview_cache(self, key, pixmap: Optional[QtGui.QPixmap]):
        remember_seek_preview_cache_impl(self, key, pixmap)

    def _show_seek_preview_pixmap(self, pixmap: QtGui.QPixmap, global_pos: QtCore.QPoint):
        show_seek_preview_pixmap_impl(self, pixmap, global_pos)

    def _resolve_pending_seek_preview(self):
        resolve_pending_seek_preview_impl(self)

    @QtCore.pyqtSlot(str, QtGui.QImage, int)
    def _on_seek_preview_thumbnail_ready(self, path: str, image: QtGui.QImage, ms: int):
        on_seek_preview_thumbnail_ready_impl(self, path, image, ms)

    def show_preview(self, event):
        show_preview_impl(self, event)


    def _get_frame_thumbnail(self, path: str, ms: int, w: int = 160, h: int = 90) -> Optional[QtGui.QPixmap]:
        return get_frame_thumbnail_impl(self, path, ms, w=w, h=h)

    def _current_media_path(self) -> Optional[str]:
        """
        현재 재생/선택 중인 파일 경로를 반환.
        1) VLC의 media MRL(file:///)에서 추출
        2) 불가하면 playlist[current_index] 사용
        """
        # 1) VLC media에서 추출
        try:
            m = self.mediaplayer.get_media()
            if m is not None:
                mrl = m.get_mrl() or ""
                if mrl.startswith("file:///"):
                    path = urllib.parse.unquote(mrl[8:])
                    if os.name == "nt":
                        path = path.replace("/", "\\")
                    if os.path.exists(path):
                        return path
        except Exception:
            pass

        # 2) playlist에서 추출
        if self.playlist:
            idx = self.current_index if (0 <= self.current_index < len(self.playlist)) else 0
            path = self.playlist[idx]
            if os.path.exists(path):
                return path

        return None

    def _detect_scenes_parallel(self, path, threshold=30, workers=None, backend="thread", downscale_w=320, use_gray=True):
        return _detect_scenes_parallel(
            path,
            threshold=threshold,
            workers=workers,
            backend=backend,
            downscale_w=downscale_w,
            use_gray=use_gray,
        )

    def seek_ms(self, ms: int, play: bool = True, show_overlay: bool = True):
        """기존에 쓰시던 간단 시크가 있다면 이름 바꾸거나 아래 안전 래퍼를 사용하세요."""
        # 가능하면 아래 safe_seek_from_ui()만 직접 호출하세요.
        try:
            m = self.mediaplayer
        except Exception:
            return
        if not m:
            return
        try:
            length = m.get_length()
        except Exception:
            length = -1

        # 안전한 범위로 클램프 (끝 프레임 바로 앞까지만)
        if isinstance(length, int) and length > 0:
            ms = max(0, min(int(ms), int(max(0, length - 500))))
        else:
            ms = max(0, int(ms))

        self._sync_seek_ui(
            ms,
            length_ms=length if isinstance(length, int) and length > 0 else None,
            show_overlay=show_overlay,
            sync_slider=not bool(getattr(getattr(self, "sld_pos", None), "isSliderDown", lambda: False)()),
        )

        desired_rate, needs_seek_stabilize = self._prepare_seek_playback_rate(play=play)

        # 재생/일시정지 상태 설정
        try:
            if play:
                m.set_pause(0)
            else:
                m.set_pause(1)
        except Exception:
            pass

        # 바로 시크 시도
        try:
            ok = m.set_time(int(ms))
        except Exception:
            ok = -1
        if needs_seek_stabilize:
            self._nudge_play_after_seek()
            self._schedule_seek_rate_restore(desired_rate, play=play)

        # VLC가 바로 못 옮기면(또는 상태상 불안) → 재시도 루틴
        if ok == -1:
            self._retry_seek_token = getattr(self, "_retry_seek_token", 0) + 1
            token = self._retry_seek_token
            self._retry_seek_vlc(int(ms), token, tries=10, desired_rate=desired_rate, play=play)

    def _retry_seek_vlc(self, target_ms: int, token: int, tries: int = 10, desired_rate: float = 1.0, play: bool = True):
        """버퍼링/상태 전환 후 짧게 지연을 두며 set_time 재시도."""
        if tries <= 0:
            return
        # 토큰 체크로 중복 시크 경쟁 방지
        if token != getattr(self, "_retry_seek_token", token):
            return

        m = getattr(self, "mediaplayer", None)
        if not m:
            return

        # 재생 상태가 아니면 살짝 재생을 걸고 잠깐 뒤에 시크
        try:
            state = m.get_state()
        except Exception:
            state = None

        def _do_try():
            if token != getattr(self, "_retry_seek_token", token):
                return
            try:
                m.set_time(int(target_ms))
            except Exception:
                pass
            if play:
                self._nudge_play_after_seek(token)
            self._schedule_seek_rate_restore(desired_rate, play=play, token=token)
            # 목표 근처로 왔는지 확인해서 아니면 다시 예약
            try:
                cur = m.get_time()
            except Exception:
                cur = -1
            if cur < 0 or abs(cur - target_ms) > 500:
                QtCore.QTimer.singleShot(
                    80,
                    lambda: self._retry_seek_vlc(
                        target_ms,
                        token,
                        tries=tries - 1,
                        desired_rate=desired_rate,
                        play=play,
                    ),
                )

        # 상태에 따라 분기
        try:
            if state is None or str(state).lower() in ("stopped", "nothingspecial"):
                # 재생 걸고 버퍼 살짝 기다렸다가 시크
                try:
                    m.play()
                except Exception:
                    pass
                QtCore.QTimer.singleShot(120, _do_try)
            else:
                QtCore.QTimer.singleShot(60, _do_try)
        except Exception:
            QtCore.QTimer.singleShot(80, _do_try)

    def safe_seek_from_ui(self, target_ms: int):
        """
        UI 이벤트(더블클릭/엔터/버튼)에서 호출용.
        - GUI 스레드 보장 (QueuedConnection)
        - 중복 시크 경쟁 방지 토큰 갱신
        """
        self._retry_seek_token = getattr(self, "_retry_seek_token", 0) + 1
        t = int(max(0, target_ms))

        # GUI 스레드로 안전 호출
        QtCore.QMetaObject.invokeMethod(
            self,
            "_safe_seek_entry",
            QtCore.Qt.ConnectionType.QueuedConnection,
            QtCore.Q_ARG(int, t)
        )

    @QtCore.pyqtSlot(int)
    def _safe_seek_entry(self, t: int):
        # 실제 시크 실행
        self.seek_ms(t, play=True)



    def _get_frame_thumbnail_ffmpeg(self, path: str, ms: int, w=160, h=90, ffmpeg_bin: str = ""):
        return get_frame_thumbnail_ffmpeg_impl(self, path, ms, w=w, h=h, ffmpeg_bin=ffmpeg_bin)

    def _get_frame_thumbnail_safe(self, path: str, ms: int, w=160, h=90):
        return get_frame_thumbnail_safe_impl(self, path, ms, w=w, h=h)

    def build_drag_preview_pixmap(self) -> Optional[QtGui.QPixmap]:
        return build_drag_preview_pixmap_impl(self)

    def _get_player_for_audio(self):
        """
        타일의 MediaPlayer 핸들을 찾아 반환.
        프로젝트마다 속성명이 다를 수 있어 안전하게 조회.
        """
        for name in ("player", "media_player", "mediaplayer", "vlc_player"):
            p = getattr(self, name, None)
            if p is not None:
                return p
        return None
    def _on_tile_volume_changed(self, v: int):
        self.tile_volume = int(v)
        # 뮤트 상태라도 슬라이더 이동은 기록만 하고, 실제 출력은 _apply가 0 처리
        self._apply_tile_volume()
        self._show_volume_overlay()

    def _place_mute_overlay(self):
        if not hasattr(self, "mute_overlay"):
            return
        self.mute_overlay.adjustSize()
        # VLC 렌더 위에 확실히 보이도록 타일(self) 기준으로 배치
        vw_geo = self.video_widget.geometry() if hasattr(self, "video_widget") else QtCore.QRect(0, 0, 0, 0)
        x = vw_geo.x() + 10
        y = vw_geo.y() + 10
        # 요청사항: 음소거 아이콘은 타일 영상 좌측 상단에 잠깐 표시
        x = 10
        y = 10
        self.mute_overlay.move(x, y)

    def _show_mute_overlay(self, muted: bool):
        if not hasattr(self, "mute_overlay"):
            return
        # 요청사항: 음소거 시에만 잠깐 표시 후 자동으로 사라짐
        if not muted:
            self.mute_overlay.hide()
            return
        self.mute_overlay.setText("🔇")
        self._place_mute_overlay()
        self.mute_overlay.show()
        self.mute_overlay.raise_()
        self._mute_overlay_timer.start(750)

    def _place_volume_overlay(self):
        if not hasattr(self, "volume_overlay"):
            return
        self.volume_overlay.adjustSize()
        x = max(0, self.width() - self.volume_overlay.width() - 10)
        y = 10
        if hasattr(self, "seek_overlay") and self.seek_overlay.isVisible():
            y += self.seek_overlay.height() + 6
        self.volume_overlay.move(x, y)

    def _show_volume_overlay(self):
        if not hasattr(self, "volume_overlay"):
            return
        raw = max(0, min(120, int(getattr(self, "tile_volume", 120))))
        self.volume_overlay.setText(f"{raw}%")
        self._place_volume_overlay()
        self.volume_overlay.show()
        self.volume_overlay.raise_()
        self._place_rate_overlay()
        self._place_status_overlay()
        self._volume_overlay_timer.start(900)

    def _place_rate_overlay(self):
        if not hasattr(self, "rate_overlay"):
            return
        self.rate_overlay.adjustSize()
        x = max(0, self.width() - self.rate_overlay.width() - 10)
        y = 10
        if hasattr(self, "seek_overlay") and self.seek_overlay.isVisible():
            y += self.seek_overlay.height() + 6
        if hasattr(self, "volume_overlay") and self.volume_overlay.isVisible():
            y += self.volume_overlay.height() + 6
        self.rate_overlay.move(x, y)

    def _place_status_overlay(self):
        if not hasattr(self, "status_overlay"):
            return
        self.status_overlay.adjustSize()
        x = max(0, self.width() - self.status_overlay.width() - 10)
        y = 10
        if hasattr(self, "seek_overlay") and self.seek_overlay.isVisible():
            y += self.seek_overlay.height() + 6
        if hasattr(self, "volume_overlay") and self.volume_overlay.isVisible():
            y += self.volume_overlay.height() + 6
        if hasattr(self, "rate_overlay") and self.rate_overlay.isVisible():
            y += self.rate_overlay.height() + 6
        self.status_overlay.move(x, y)

    def _show_rate_overlay(self):
        if not hasattr(self, "rate_overlay"):
            return
        self.rate_overlay.setText(f"{self.playback_rate:.1f}x")
        self._place_rate_overlay()
        self.rate_overlay.show()
        self.rate_overlay.raise_()
        self._place_status_overlay()
        self._rate_overlay_timer.start(900)

    def _show_status_overlay(self, text: str, timeout_ms: int = 900):
        if not hasattr(self, "status_overlay"):
            return
        message = str(text or "").strip()
        if not message:
            return
        self.status_overlay.setText(message)
        self._place_status_overlay()
        self.status_overlay.show()
        self.status_overlay.raise_()
        self._status_overlay_timer.start(max(200, int(timeout_ms)))

    def _place_seek_overlay(self):
        if not hasattr(self, "seek_overlay"):
            return
        self.seek_overlay.adjustSize()
        x = max(0, self.width() - self.seek_overlay.width() - 10)
        y = 10
        self.seek_overlay.move(x, y)

    def _hide_seek_overlay(self):
        if not hasattr(self, "seek_overlay"):
            return
        self.seek_overlay.hide()
        self._place_volume_overlay()
        self._place_rate_overlay()
        self._place_status_overlay()

    def _show_seek_overlay_ms(self, ms: int):
        if not hasattr(self, "seek_overlay"):
            return
        self.seek_overlay.setText(self._ms_to_clock(ms))
        self._place_seek_overlay()
        self.seek_overlay.show()
        self.seek_overlay.raise_()
        self._place_volume_overlay()
        self._place_rate_overlay()
        self._place_status_overlay()
        self._seek_overlay_timer.start(1100)

    def set_tile_muted(self, on: bool):
        prev = bool(getattr(self, "tile_muted", False))
        self.tile_muted = bool(on)
        self._apply_tile_volume()
        if prev != self.tile_muted:
            self._show_mute_overlay(self.tile_muted)

    def toggle_tile_mute(self):
        self.set_tile_muted(not getattr(self, "tile_muted", False))

    def _apply_tile_volume(self):
        # 마스터 볼륨/뮤트와 타일 볼륨/뮤트를 합성해 실제 출력 볼륨을 계산
        master_muted = False
        master_volume = 100
        try:
            main = self._main_window()
            master_muted = bool(getattr(main, "master_muted", False))
            master_volume = int(getattr(main, "master_volume", 100))
        except Exception:
            pass
        master_volume = max(0, min(100, int(master_volume)))
        effective_muted = master_muted or self.tile_muted or (master_volume == 0)
        raw = max(0, min(120, int(getattr(self, "tile_volume", 120))))
        vol = 0 if effective_muted else int(round(raw * (master_volume / 100.0)))
        vol = max(0, min(120, vol))

        p = self._get_player_for_audio()
        try:
            if p is not None and hasattr(p, "audio_set_volume"):  # python-vlc
                p.audio_set_volume(vol)
            elif p is not None and hasattr(p, "setVolume"):  # QtMultimedia
                p.setVolume(min(100, vol))
        except Exception:
            pass
