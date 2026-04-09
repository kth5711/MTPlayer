# main.py

import sys, os, multiprocessing
from typing import List, Optional, Dict, Any
from PyQt6 import QtCore, QtGui, QtWidgets

from app_shell.config import _default_config_path
from canvas import Canvas  # canvas.py 임포트
from canvas_support import DetachedTilesCompareOverlayController
from app_shell.interaction import (
    apply_fullscreen_ui_mode as apply_fullscreen_ui_mode_impl,
    apply_hotkey_action as apply_hotkey_action_impl,
    capture_managed_focus_window as capture_managed_focus_window_impl,
    clear_tile_drag_state as clear_tile_drag_state_impl,
    current_shortcuts_or_defaults as current_shortcuts_or_defaults_impl,
    cycle_display_mode_all_or_selected as cycle_display_mode_all_or_selected_impl,
    cycle_repeat_mode_all_or_selected as cycle_repeat_mode_all_or_selected_impl,
    detached_window_for_fullscreen_action as detached_window_for_fullscreen_action_impl,
    event_filter as event_filter_impl,
    event_to_shortcut_token as event_to_shortcut_token_impl,
    exit_fullscreen as exit_fullscreen_impl,
    finish_tile_drag as finish_tile_drag_impl,
    flush_fullscreen_hover as flush_fullscreen_hover_impl,
    flush_fullscreen_hover_preserving_hidden_cursor as flush_fullscreen_hover_preserving_hidden_cursor_impl,
    focused_text_input_widget as focused_text_input_widget_impl,
    fullscreen_hover_tile_at_global as fullscreen_hover_tile_at_global_impl,
    handle_drag_mouse_move as handle_drag_mouse_move_impl,
    handle_drag_mouse_release as handle_drag_mouse_release_impl,
    handle_fullscreen_hover_at as handle_fullscreen_hover_at_impl,
    handle_key_press_event as handle_key_press_event_impl,
    handle_key_release_event as handle_key_release_event_impl,
    handle_main_mouse_press as handle_main_mouse_press_impl,
    handle_seek_key_event as handle_seek_key_event_impl,
    handle_shortcut_override_event as handle_shortcut_override_event_impl,
    hide_cursor as hide_cursor_impl,
    hide_ui as hide_ui_impl,
    hotkey_action_for_event as hotkey_action_for_event_impl,
    is_main_window_active as is_main_window_active_impl,
    keep_detached_tiles_for_focus_modes as keep_detached_tiles_for_focus_modes_impl,
    key_press_event as key_press_event_impl,
    move_tile_drag_preview as move_tile_drag_preview_impl,
    normalize_shortcut_mapping as normalize_shortcut_mapping_impl,
    normalize_shortcut_token as normalize_shortcut_token_impl,
    on_tile_drag_preview_ready as on_tile_drag_preview_ready_impl,
    queue_fullscreen_hover as queue_fullscreen_hover_impl,
    rebind_shortcuts as rebind_shortcuts_impl,
    rebuild_seek_hotkeys as rebuild_seek_hotkeys_impl,
    rebuild_tile_hotkeys as rebuild_tile_hotkeys_impl,
    refresh_fullscreen_hover_from_cursor as refresh_fullscreen_hover_from_cursor_impl,
    register_tile_hotkey as register_tile_hotkey_impl,
    restore_managed_window_focus as restore_managed_window_focus_impl,
    restore_window_focus as restore_window_focus_impl,
    schedule_fullscreen_hover_refresh_from_cursor as schedule_fullscreen_hover_refresh_from_cursor_impl,
    seek_step_for_event as seek_step_for_event_impl,
    select_tile_by_index as select_tile_by_index_impl,
    set_action_shortcut as set_action_shortcut_impl,
    should_bypass_global_key_handling as should_bypass_global_key_handling_impl,
    show_all_tile_controls as show_all_tile_controls_impl,
    show_cursor as show_cursor_impl,
    show_tile_drag_preview as show_tile_drag_preview_impl,
    show_top_ui as show_top_ui_impl,
    show_ui as show_ui_impl,
    start_tile_drag_candidate as start_tile_drag_candidate_impl,
    sync_windowed_ui_from_compact_mode as sync_windowed_ui_from_compact_mode_impl,
    tile_from_event_source as tile_from_event_source_impl,
    toggle_fullscreen as toggle_fullscreen_impl,
    toggle_mute as toggle_mute_impl,
    toggle_select_all_tiles as toggle_select_all_tiles_impl,
    update_tile_drag as update_tile_drag_impl,
    vol_step as vol_step_impl,
)
from main_playlist import (
    adjust_tile_current_index_after_row_removal as adjust_tile_current_index_after_row_removal_impl,
    apply_playlist_current_item_style as apply_playlist_current_item_style_impl,
    apply_playlist_sort as apply_playlist_sort_impl,
    create_playlist_dock as create_playlist_dock_impl,
    duration_cache_signature as duration_cache_signature_impl,
    flush_playlist_refresh as flush_playlist_refresh_impl,
    format_duration_ms as format_duration_ms_impl,
    normalize_playlist_path as normalize_playlist_path_impl,
    on_files_moved_between_tiles as on_files_moved_between_tiles_impl,
    on_playlist_context_menu as on_playlist_context_menu_impl,
    on_playlist_sort_changed as on_playlist_sort_changed_impl,
    on_playlist_sort_order_toggled as on_playlist_sort_order_toggled_impl,
    play_from_playlist as play_from_playlist_impl,
    play_from_tile_row as play_from_tile_row_impl,
    pl_delete_selected as pl_delete_selected_impl,
    pl_open_files_into_tile as pl_open_files_into_tile_impl,
    pl_open_folder_into_tile as pl_open_folder_into_tile_impl,
    pl_open_selected_in_explorer as pl_open_selected_in_explorer_impl,
    playlist_current_path_for_tile as playlist_current_path_for_tile_impl,
    playlist_duration_info as playlist_duration_info_impl,
    playlist_filter_text as playlist_filter_text_impl,
    playlist_first_number_key as playlist_first_number_key_impl,
    playlist_first_visible_char as playlist_first_visible_char_impl,
    playlist_is_ascii_alpha_lead as playlist_is_ascii_alpha_lead_impl,
    playlist_is_hangul_lead as playlist_is_hangul_lead_impl,
    playlist_natural_key as playlist_natural_key_impl,
    playlist_path_matches_filter as playlist_path_matches_filter_impl,
    playlist_sort_descending as playlist_sort_descending_impl,
    playlist_sort_key_for_path as playlist_sort_key_for_path_impl,
    playlist_sort_mode as playlist_sort_mode_impl,
    playlist_sort_name as playlist_sort_name_impl,
    playlist_tile_is_playing as playlist_tile_is_playing_impl,
    probe_duration_ms as probe_duration_ms_impl,
    refresh_playlist_ui_texts as refresh_playlist_ui_texts_impl,
    request_playlist_refresh as request_playlist_refresh_impl,
    set_playlist_sort_controls as set_playlist_sort_controls_impl,
    sorted_playlist_for_mode as sorted_playlist_for_mode_impl,
    sync_playlist_sort_order_button_text as sync_playlist_sort_order_button_text_impl,
    tile_idx_from_selection as tile_idx_from_selection_impl,
    toggle_playlist_visibility as toggle_playlist_visibility_impl,
    trash_path as trash_path_impl,
    trash_playlist_entry as trash_playlist_entry_impl,
    update_playlist as update_playlist_impl,
)
from app_shell.playlist_current import (
    remove_current_playlist_items as remove_current_playlist_items_impl,
    trash_current_playlist_items as trash_current_playlist_items_impl,
)
from main_bookmarks import (
    add_bookmark_category as add_bookmark_category_impl,
    add_bookmark_from_current as add_bookmark_from_current_impl,
    add_bookmarks_for_path_positions as add_bookmarks_for_path_positions_impl,
    add_bookmarks_for_path_ranges as add_bookmarks_for_path_ranges_impl,
    add_bookmark_from_tile as add_bookmark_from_tile_impl,
    bookmark_categories_payload as bookmark_categories_payload_impl,
    bookmark_marks_visible as bookmark_marks_visible_impl,
    bookmark_payload as bookmark_payload_impl,
    bookmark_positions_for_path as bookmark_positions_for_path_impl,
    classify_selected_bookmarks as classify_selected_bookmarks_impl,
    create_bookmark_dock as create_bookmark_dock_impl,
    delete_selected_bookmarks as delete_selected_bookmarks_impl,
    jump_to_selected_bookmark as jump_to_selected_bookmark_impl,
    load_bookmark_categories as load_bookmark_categories_impl,
    load_bookmarks as load_bookmarks_impl,
    refresh_bookmark_dock as refresh_bookmark_dock_impl,
    refresh_bookmark_marks as refresh_bookmark_marks_impl,
    refresh_bookmark_ui_texts as refresh_bookmark_ui_texts_impl,
    select_bookmarks_for_path_positions as select_bookmarks_for_path_positions_impl,
    selected_bookmark_positions_for_path as selected_bookmark_positions_for_path_impl,
    set_bookmark_marks_visible as set_bookmark_marks_visible_impl,
    toggle_bookmark_visibility as toggle_bookmark_visibility_impl,
)
from bookmarks import bind_bookmark_context_menu as bind_bookmark_context_menu_impl
from app_shell.state import (
    apply_profile_payload as apply_profile_payload_impl,
    apply_view_state as apply_view_state_impl,
    build_profile_payload as build_profile_payload_impl,
    build_session_payload as build_session_payload_impl,
    close_event as close_event_impl,
    default_tile_count as default_tile_count_impl,
    load_config_and_restore as load_config_and_restore_impl,
    load_profile as load_profile_impl,
    prune_recent_media as prune_recent_media_impl,
    profile_start_dir as profile_start_dir_impl,
    push_recent_media as push_recent_media_impl,
    push_recent_media_many as push_recent_media_many_impl,
    recent_media_entries as recent_media_entries_impl,
    prune_recent_profiles as prune_recent_profiles_impl,
    push_recent_profile as push_recent_profile_impl,
    recent_profile_paths as recent_profile_paths_impl,
    refresh_recent_media_menu as refresh_recent_media_menu_impl,
    refresh_recent_profiles_menu as refresh_recent_profiles_menu_impl,
    remember_profile_dir as remember_profile_dir_impl,
    reset_session_before_restore as reset_session_before_restore_impl,
    restore_session_payload as restore_session_payload_impl,
    restore_window_state as restore_window_state_impl,
    save_config as save_config_impl,
    save_profile as save_profile_impl,
    window_state_payload as window_state_payload_impl,
)
from app_shell.session import SessionManager
from app_shell.shortcut_dialog import ShortcutDialog
from app_shell.app_icon import multi_play_app_icon
from app_shell.dock_chrome import refresh_aux_dock_chrome
from app_shell.theme import apply_ui_theme, normalize_ui_theme, remember_system_theme, theme_label_key
from i18n import SUPPORTED_UI_LANGUAGES, language_name, normalize_ui_language, tr
from video_tile_helpers.support import VIDEO_FILE_EXTENSIONS, media_file_dialog_filter
from PyQt6.QtWidgets import QMessageBox
import vlc
from app_shell.main_window_setup import (
    initialize_main_window_controls,
    initialize_main_window_core,
    initialize_main_window_menus,
    initialize_main_window_post_restore,
    initialize_main_window_runtime,
)



class MainWin(QtWidgets.QMainWindow):
    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self.setWindowIcon(multi_play_app_icon())
        initialize_main_window_core(self, config_path)
        initialize_main_window_menus(self)
        initialize_main_window_controls(self, bind_bookmark_context_menu_impl)
        initialize_main_window_runtime(self)
        self.load_config_and_restore()
        self.rebind_shortcuts(self.config.get("shortcuts"))
        initialize_main_window_post_restore(self)

    def current_ui_language(self) -> str:
        return normalize_ui_language(getattr(self, "ui_language", self.config.get("language", "ko")))

    def current_ui_theme(self) -> str:
        return normalize_ui_theme(getattr(self, "ui_theme", self.config.get("theme", "black")))

    def _tr(self, text: str, **kwargs: Any) -> str:
        return tr(self, text, **kwargs)

    def _refresh_layout_mode_menu_texts(self):
        self.layout_mode_menu.setTitle(self._tr("타일 배치 방식"))
        for mode, action in getattr(self, "layout_mode_actions", {}).items():
            action.setText(self._tr(Canvas.LAYOUT_LABELS.get(mode, mode)))
        for mode, submenu in getattr(self, "roller_layout_menus", {}).items():
            submenu.setTitle(self._tr(Canvas.LAYOUT_LABELS.get(mode, mode)))
        for (_mode, count), action in getattr(self, "roller_layout_actions", {}).items():
            action.setText(self._tr("{count}개", count=count))

    def _refresh_language_menu_texts(self):
        self.language_menu.setTitle(self._tr("언어"))
        current = self.current_ui_language()
        for code, action in getattr(self, "language_actions", {}).items():
            with QtCore.QSignalBlocker(action):
                action.setText(language_name(code))
                action.setChecked(code == current)

    def _refresh_theme_menu_texts(self):
        self.theme_menu.setTitle(self._tr("테마"))
        current = self.current_ui_theme()
        for code, action in getattr(self, "theme_actions", {}).items():
            with QtCore.QSignalBlocker(action):
                action.setText(self._tr(theme_label_key(code)))
                action.setChecked(code == current)

    def _refresh_open_scene_dialog_language(self):
        for tile in list(getattr(self.canvas, "tiles", []) or []):
            dialog = getattr(tile, "_sceneDlg", None)
            if dialog is None:
                continue
            try:
                dialog.setWindowTitle(self._tr("씬분석 (씬변화 / 유사씬)"))
            except Exception:
                pass

    def _apply_ui_language(self):
        self.config["language"] = self.current_ui_language()
        self.setWindowTitle("Multi-Play")
        self.file_menu.setTitle(self._tr("파일"))
        self.act_open.setText(self._tr("영상 열기"))
        self.act_open_multi.setText(self._tr("영상 새 타일로 열기"))
        self.act_open_folder.setText(self._tr("폴더 열기"))
        self.act_open_url.setText(self._tr("URL/스트림 열기..."))
        self.recent_media_menu.setTitle(self._tr("최근 미디어"))
        self.act_save_profile.setText(self._tr("프로필 저장"))
        self.act_load_profile.setText(self._tr("프로필 불러오기"))
        self.recent_profiles_menu.setTitle(self._tr("최근 프로필"))
        self.act_quit.setText(self._tr("종료"))
        self.view_menu.setTitle(self._tr("보기"))
        self.border_action.setText(self._tr("타일 테두리 표시"))
        self.compact_action.setText(self._tr("영상만 보기 모드"))
        self.always_on_top_action.setText(self._tr("재생 중 항상 위"))
        self.act_docked_tiles_opacity.setText(self._tr("비교 오버레이 열기..."))
        compare_button = getattr(self, "btn_docked_tiles_opacity", None)
        if compare_button is not None:
            compare_button.setText(self._tr("비교"))
            compare_button.setToolTip(self._tr("비교 오버레이 열기..."))
        if hasattr(self, "btn_opacity_mode_fullscreen"):
            self.btn_opacity_mode_fullscreen.setText(self._tr("전체화면"))
        if hasattr(self, "btn_opacity_mode_redock"):
            self.btn_opacity_mode_redock.setText(self._tr("복귀"))
        self._refresh_layout_mode_menu_texts()
        self.act_pause_roller.setText(self._tr("롤러 정지"))
        self.keep_detached_focus_mode_action.setText(self._tr("전체화면/스포트라이트 시 분리 유지"))
        self.list_menu.setTitle(self._tr("리스트"))
        self.bookmark_menu.setTitle(self._tr("리스트"))
        self.act_toggle_playlist_dock.setText(self._tr("플레이리스트 창 (도킹)"))
        self.act_toggle_bookmark_dock.setText(self._tr("북마크 창 (도킹)"))
        self.act_toggle_bookmark_marks.setText(self._tr("재생바 북마크 표시"))
        self.setting_menu.setTitle(self._tr("설정"))
        self.act_shortcut.setText(self._tr("단축키 설정"))
        self.act_restore_last_session.setText(self._tr("시작 시 마지막 세션 자동 복원"))
        self._refresh_language_menu_texts()
        self._refresh_theme_menu_texts()
        self._refresh_roller_speed_action_label()
        self._refresh_recent_media_menu()
        self._refresh_recent_profiles_menu()
        if hasattr(self, "playlist_widget"):
            self._refresh_playlist_ui_texts()
            self._set_playlist_sort_controls(self._playlist_sort_mode(), self._playlist_sort_descending())
        if hasattr(self, "bookmark_widget"):
            self._refresh_bookmark_ui_texts()
        for tile in list(getattr(self.canvas, "tiles", []) or []):
            if hasattr(tile, "_refresh_ui_texts"):
                try:
                    tile._refresh_ui_texts()
                except Exception:
                    pass
        self._refresh_open_scene_dialog_language()

    def set_ui_language(self, language: str, *, save: bool = True, announce: bool = True):
        normalized = normalize_ui_language(language)
        if normalized == self.current_ui_language():
            self._refresh_language_menu_texts()
            return
        self.ui_language = normalized
        self.config["language"] = normalized
        self._apply_ui_language()
        if save:
            self.save_config()
        if announce:
            try:
                self.statusBar().showMessage(f"{self._tr('언어')}: {language_name(normalized)}", 3000)
            except Exception:
                pass

    def _apply_ui_theme(self, *, save: bool = False, announce: bool = False):
        normalized = self.current_ui_theme()
        self.ui_theme = normalized
        self.config["theme"] = normalized
        app = QtWidgets.QApplication.instance()
        if app is not None:
            apply_ui_theme(app, normalized)
        for dock_name in ("playlist_dock", "bookmark_dock"):
            dock = getattr(self, dock_name, None)
            if dock is not None:
                refresh_aux_dock_chrome(dock)
        try:
            self.request_playlist_refresh(force=True)
        except Exception:
            pass
        active_overlay = self.active_opacity_mode_widget()
        if active_overlay is not None and hasattr(active_overlay, "refresh_theme_styles"):
            try:
                active_overlay.refresh_theme_styles()
            except Exception:
                pass
        for tile in list(getattr(self.canvas, "tiles", []) or []):
            if hasattr(tile, "_refresh_ui_texts"):
                try:
                    tile._refresh_ui_texts()
                except Exception:
                    pass
                try:
                    tile.update()
                except Exception:
                    pass
        try:
            self.update()
        except Exception:
            pass
        if hasattr(self, "theme_actions"):
            self._refresh_theme_menu_texts()
        if announce:
            try:
                self.statusBar().showMessage(
                    self._tr("테마 변경: {name}", name=self._tr(theme_label_key(normalized))),
                    3000,
                )
            except Exception:
                pass
        if save:
            self.save_config()

    def set_ui_theme(self, theme: str, *, save: bool = True, announce: bool = True):
        normalized = normalize_ui_theme(theme)
        if normalized == self.current_ui_theme():
            self._refresh_theme_menu_texts()
            return
        self.ui_theme = normalized
        self._apply_ui_theme(save=save, announce=announce)

    def _handle_escape(self):
        try:
            self.cursor_hide_timer.stop()
        except Exception:
            pass
        if self._exit_active_opacity_mode_fullscreen_if_needed():
            return
        detached_window = self._detached_window_for_fullscreen_action()
        if detached_window is not None:
            try:
                detached_window.exit_fullscreen_mode()
                return
            except Exception:
                pass
        if bool(self.windowState() & QtCore.Qt.WindowState.WindowFullScreen) or self.isFullScreen():
            self.exit_fullscreen()

    def _default_tile_count(self) -> int:
        return default_tile_count_impl(self)

    def _window_state_payload(self) -> Dict[str, Any]:
        return window_state_payload_impl(self)

    def _build_session_payload(self) -> Dict[str, Any]:
        return build_session_payload_impl(self)

    def _build_profile_payload(self) -> Dict[str, Any]:
        return build_profile_payload_impl(self)

    def _profile_start_dir(self) -> str:
        return profile_start_dir_impl(self)

    def _remember_profile_dir(self, path: str):
        return remember_profile_dir_impl(self, path)

    def _recent_profile_paths(self) -> list[str]:
        return recent_profile_paths_impl(self)

    def _recent_media_entries(self) -> list[dict[str, str]]:
        return recent_media_entries_impl(self)

    def _push_recent_media(self, source: str, kind: str = "path"):
        return push_recent_media_impl(self, source, kind=kind)

    def _push_recent_media_many(self, sources, kind: str = "path"):
        return push_recent_media_many_impl(self, sources, kind=kind)

    def _push_recent_profile(self, path: str):
        return push_recent_profile_impl(self, path)

    def _refresh_recent_media_menu(self):
        return refresh_recent_media_menu_impl(self)

    def _refresh_recent_profiles_menu(self):
        return refresh_recent_profiles_menu_impl(self)

    def _prune_recent_media(self):
        return prune_recent_media_impl(self)

    def _prune_recent_profiles(self):
        return prune_recent_profiles_impl(self)

    def _restore_window_state(self, payload: Any):
        return restore_window_state_impl(self, payload)

    def _apply_view_state(self, payload: Any):
        return apply_view_state_impl(self, payload)

    def _reset_session_before_restore(self):
        return reset_session_before_restore_impl(self)

    def _restore_session_payload(self, payload: Any):
        return restore_session_payload_impl(self, payload)

    def _apply_profile_payload(self, payload: Any):
        return apply_profile_payload_impl(self, payload)

    def load_config_and_restore(self):
        return load_config_and_restore_impl(self)

    def save_config(self, *, auto: bool = False):
        return save_config_impl(self, auto=auto)

    def save_profile(self):
        return save_profile_impl(self)

    def load_profile(self, path: Optional[str] = None):
        return load_profile_impl(self, path=path)

    def closeEvent(self, e: QtGui.QCloseEvent):
        return close_event_impl(self, e)

    def current_shortcuts_or_defaults(self) -> Dict[str, str]:
        return current_shortcuts_or_defaults_impl(self)

    def _normalize_shortcut_mapping(self, mapping: Optional[Dict[str, str]]) -> Dict[str, str]:
        return normalize_shortcut_mapping_impl(self, mapping)

    def _set_action_shortcut(self, action: Optional[QtGui.QAction], key_str: str):
        return set_action_shortcut_impl(self, action, key_str)

    def _rebuild_seek_hotkeys(self, mapping: Dict[str, str]):
        return rebuild_seek_hotkeys_impl(self, mapping)

    def rebind_shortcuts(self, mapping: Optional[Dict[str, str]]):
        return rebind_shortcuts_impl(self, mapping)

    def _cycle_repeat_mode_all_or_selected(self):
        return cycle_repeat_mode_all_or_selected_impl(self)

    def _cycle_display_mode_all_or_selected(self):
        return cycle_display_mode_all_or_selected_impl(self)

    def _toggle_select_all_tiles(self):
        return toggle_select_all_tiles_impl(self)

    def _vol_step(self, direction: int):
        return vol_step_impl(self, direction)

    def _toggle_mute(self):
        return toggle_mute_impl(self)

    def toggle_fullscreen(self):
        return toggle_fullscreen_impl(self)

    def _hide_cursor(self):
        return hide_cursor_impl(self)

    def _show_cursor(self):
        return show_cursor_impl(self)

    def _hide_ui(self):
        return hide_ui_impl(self)

    def _show_ui(self):
        return show_ui_impl(self)

    def _sync_windowed_ui_from_compact_mode(self):
        return sync_windowed_ui_from_compact_mode_impl(self)

    def _restore_window_focus(self):
        return restore_window_focus_impl(self)

    def _capture_managed_focus_window(self):
        return capture_managed_focus_window_impl(self)

    def _restore_managed_window_focus(self, preferred=None):
        return restore_managed_window_focus_impl(self, preferred=preferred)

    def keep_detached_tiles_for_focus_modes(self) -> bool:
        return keep_detached_tiles_for_focus_modes_impl(self)

    def _detached_window_for_fullscreen_action(self):
        return detached_window_for_fullscreen_action_impl(self)

    def _is_main_window_active(self) -> bool:
        return is_main_window_active_impl(self)

    def _focused_text_input_widget(self):
        return focused_text_input_widget_impl(self)

    def _foreground_aux_window_at_global(self, gp: QtCore.QPoint):
        try:
            app = QtWidgets.QApplication.instance()
            if app is None:
                return None
            top = app.activeWindow()
            if top is None:
                return None
            top = top.window()
            if top is None or top is self or self.canvas.is_managed_window(top):
                return None
            if not top.isVisible():
                return None
            if top.frameGeometry().contains(gp):
                return top
        except Exception:
            return None
        return None

    def _should_bypass_global_mouse_handling(
        self,
        gp: QtCore.QPoint,
        source_window: Optional[QtWidgets.QWidget] = None,
    ) -> bool:
        try:
            top = source_window.window() if isinstance(source_window, QtWidgets.QWidget) else source_window
            if top is not None and top is not self and not self.canvas.is_managed_window(top):
                return True
        except Exception:
            return True
        return self._foreground_aux_window_at_global(gp) is not None

    def _should_bypass_global_key_handling(self) -> bool:
        return should_bypass_global_key_handling_impl(self)

    def _normalize_shortcut_token(self, raw: str) -> str:
        return normalize_shortcut_token_impl(self, raw)

    def _event_to_shortcut_token(self, event: QtGui.QKeyEvent) -> str:
        return event_to_shortcut_token_impl(self, event)

    def _register_tile_hotkey(self, key_str: str, action: tuple[str, int]):
        return register_tile_hotkey_impl(self, key_str, action)

    def _rebuild_tile_hotkeys(self, mapping: Dict[str, str]):
        return rebuild_tile_hotkeys_impl(self, mapping)

    def _hotkey_action_for_event(self, event: QtGui.QKeyEvent):
        return hotkey_action_for_event_impl(self, event)

    def _select_tile_by_index(self, n: int, multi: bool = False) -> bool:
        return select_tile_by_index_impl(self, n, multi=multi)

    def _apply_hotkey_action(self, action) -> bool:
        return apply_hotkey_action_impl(self, action)

    def _seek_step_for_event(self, event: QtGui.QKeyEvent):
        return seek_step_for_event_impl(self, event)

    def _handle_seek_key_event(self, event: QtGui.QKeyEvent) -> bool:
        return handle_seek_key_event_impl(self, event)

    def _tile_from_event_source(self, obj, gp: Optional[QtCore.QPoint] = None):
        return tile_from_event_source_impl(self, obj, gp)

    def _clear_tile_drag_state(self):
        return clear_tile_drag_state_impl(self)

    def _on_tile_drag_preview_ready(self, pixmap):
        return on_tile_drag_preview_ready_impl(self, pixmap)

    def _show_tile_drag_preview(self, tile, gp: QtCore.QPoint, grab_offset: QtCore.QPoint):
        return show_tile_drag_preview_impl(self, tile, gp, grab_offset)

    def _move_tile_drag_preview(self, gp: QtCore.QPoint, grab_offset: QtCore.QPoint):
        return move_tile_drag_preview_impl(self, gp, grab_offset)

    def _start_tile_drag_candidate(self, tile, gp: QtCore.QPoint):
        return start_tile_drag_candidate_impl(self, tile, gp)

    def _update_tile_drag(self, gp: QtCore.QPoint) -> bool:
        return update_tile_drag_impl(self, gp)

    def _finish_tile_drag(self, gp: QtCore.QPoint) -> bool:
        return finish_tile_drag_impl(self, gp)

    def _handle_drag_mouse_move(self, event: QtGui.QMouseEvent) -> bool:
        return handle_drag_mouse_move_impl(self, event)

    def _handle_drag_mouse_release(self, event: QtGui.QMouseEvent) -> bool:
        return handle_drag_mouse_release_impl(self, event)

    def _handle_main_mouse_press(self, obj, event: QtGui.QMouseEvent) -> bool:
        return handle_main_mouse_press_impl(self, obj, event)

    def _handle_shortcut_override_event(self, event: QtGui.QKeyEvent) -> bool:
        return handle_shortcut_override_event_impl(self, event)

    def _handle_key_press_event(self, event: QtGui.QKeyEvent) -> bool:
        return handle_key_press_event_impl(self, event)

    def _handle_key_release_event(self, event: QtGui.QKeyEvent) -> bool:
        return handle_key_release_event_impl(self, event)

    def _fullscreen_hover_tile_at_global(self, pos: QtCore.QPoint):
        return fullscreen_hover_tile_at_global_impl(self, pos)

    def _queue_fullscreen_hover(self, pos: QtCore.QPoint):
        return queue_fullscreen_hover_impl(self, pos)

    def _flush_fullscreen_hover(self):
        return flush_fullscreen_hover_impl(self)

    def _refresh_fullscreen_hover_from_cursor(self):
        return refresh_fullscreen_hover_from_cursor_impl(self)

    def _flush_fullscreen_hover_preserving_hidden_cursor(self):
        return flush_fullscreen_hover_preserving_hidden_cursor_impl(self)

    def _schedule_fullscreen_hover_refresh_from_cursor(self):
        return schedule_fullscreen_hover_refresh_from_cursor_impl(self)

    def _handle_fullscreen_hover_at(self, pos: QtCore.QPoint, *, preserve_hidden_cursor: bool = False) -> bool:
        return handle_fullscreen_hover_at_impl(
            self, pos, preserve_hidden_cursor=preserve_hidden_cursor
        )

    def eventFilter(self, obj, event):
        return event_filter_impl(self, obj, event)

    def changeEvent(self, event: QtCore.QEvent):
        old_state = QtCore.Qt.WindowState.WindowNoState
        if isinstance(event, QtGui.QWindowStateChangeEvent):
            old_state = event.oldState()
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.Type.WindowStateChange:
            self._handle_main_window_state_change(old_state)

    def _floating_aux_docks(self):
        docks = []
        for name in ("playlist_dock", "bookmark_dock"):
            dock = getattr(self, name, None)
            if dock is None:
                continue
            try:
                if not dock.isFloating() or not dock.isVisible():
                    continue
            except RuntimeError:
                continue
            docks.append(dock)
        return docks

    def _set_native_window_owner(self, hwnd: int, owner_hwnd: int) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes
        except Exception:
            return
        if not hwnd:
            return
        user32 = ctypes.windll.user32
        GWLP_HWNDPARENT = -8
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        SWP_FRAMECHANGED = 0x0020
        try:
            if ctypes.sizeof(ctypes.c_void_p) >= 8:
                setter = user32.SetWindowLongPtrW
                setter.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
                setter.restype = ctypes.c_void_p
                setter(ctypes.c_void_p(int(hwnd)), GWLP_HWNDPARENT, ctypes.c_void_p(int(owner_hwnd or 0)))
            else:
                setter = user32.SetWindowLongW
                setter.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
                setter.restype = ctypes.c_long
                setter(ctypes.c_void_p(int(hwnd)), GWLP_HWNDPARENT, int(owner_hwnd or 0))
            user32.SetWindowPos(
                ctypes.c_void_p(int(hwnd)),
                ctypes.c_void_p(0),
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
            )
        except Exception:
            return

    def _sync_aux_dock_owner(self, dock):
        if sys.platform != "win32" or dock is None:
            return
        try:
            hwnd = int(dock.winId())
        except Exception:
            return
        try:
            floating = bool(dock.isFloating())
        except Exception:
            floating = False
        owner_hwnd = 0 if floating else int(self.winId())
        self._set_native_window_owner(hwnd, owner_hwnd)

    def _handle_main_window_state_change(self, old_state):
        try:
            minimized = bool(self.windowState() & QtCore.Qt.WindowState.WindowMinimized) or self.isMinimized()
        except RuntimeError:
            return
        was_minimized = bool(old_state & QtCore.Qt.WindowState.WindowMinimized)
        if minimized and not was_minimized:
            self._floating_aux_docks_before_minimize = list(self._floating_aux_docks())
            self._restore_floating_aux_docks_after_minimize()
            return
        if not minimized:
            self._floating_aux_docks_before_minimize = []

    def _restore_floating_aux_docks_after_minimize(self):
        docks = list(getattr(self, "_floating_aux_docks_before_minimize", []) or [])
        if not docks:
            return

        def _restore_once():
            for dock in docks:
                try:
                    if dock is None or not dock.isFloating():
                        continue
                    if bool(dock.windowState() & QtCore.Qt.WindowState.WindowMinimized) or not dock.isVisible():
                        dock.showNormal()
                    else:
                        dock.show()
                    dock.raise_()
                except RuntimeError:
                    continue

        for delay_ms in (0, 120):
            QtCore.QTimer.singleShot(delay_ms, _restore_once)

    def _show_top_ui(self, visible: bool):
        return show_top_ui_impl(self, visible)

    def _show_all_tile_controls(self, visible: bool):
        return show_all_tile_controls_impl(self, visible)

    def _apply_fullscreen_ui_mode(self, mode: str, tile=None):
        return apply_fullscreen_ui_mode_impl(self, mode, tile)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        return key_press_event_impl(self, event)

    def exit_fullscreen(self):
        return exit_fullscreen_impl(self)

    def _snap_master(self):
        v = self.sld_master.value()
        snapped = int(round(v / 5) * 5)
        if snapped != v:
            self.sld_master.setValue(snapped)
        else:
            self.on_master_volume(snapped)

    def on_master_volume(self, value):
        self.canvas.set_master_volume(value)

    def add_video(self):
        self.canvas.add_tile()
        self.setFocus()

    def remove_last(self):
        if self.canvas.tiles:
            self.canvas.remove_tile(self.canvas.tiles[-1])

    def open_files_into_new_tiles(self):
        while self.canvas.tiles:
            self.canvas.remove_tile(self.canvas.tiles[-1])
        start_dir = getattr(self, "last_dir", "") or os.path.expanduser("~")
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, self._tr("영상 열기"), start_dir)
        if not files:
            return
        self.last_dir = os.path.dirname(files[0])
        self.config["last_dir"] = self.last_dir
        self._push_recent_media_many(files, kind="path")
        for i, path in enumerate(files):
            self.add_video()
            tile = self.canvas.tiles[-1]
            tile.add_to_playlist(path, play_now=True if i == 0 else False)
        self.update_playlist()
        self.setFocus()

    def open_multiple_videos(self, distribute=True):
        start_dir = self.config.get("last_dir", "") or ""
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, self._tr("영상 열기"), start_dir)
        if not files:
            return
        self.config["last_dir"] = os.path.dirname(files[0])
        self._push_recent_media_many(files, kind="path")

        if not distribute:
            while self.canvas.tiles:
                self.canvas.remove_tile(self.canvas.tiles[-1])
            needed = len(files)
            while len(self.canvas.tiles) < needed:
                self.canvas.add_tile()
            for i, path in enumerate(files):
                t = self.canvas.tiles[i]
                t.clear_playlist()
                t.add_to_playlist(path, play_now=False)
        else:
            if not self.canvas.tiles:
                for _ in range(4):
                    self.canvas.add_tile()
            n_tiles = len(self.canvas.tiles)
            for t in self.canvas.tiles:
                t.clear_playlist()
            for i, path in enumerate(files):
                t = self.canvas.tiles[i % n_tiles]
                t.add_to_playlist(path, play_now=False)

        self.update_playlist()
        self.canvas.relayout()
        QtCore.QTimer.singleShot(0, self.canvas.play_all)
        self.setFocus()

    def _normalize_url_stream_input(self, raw: str) -> str:
        text = str(raw or "").strip()
        if not text:
            return ""
        try:
            qurl = QtCore.QUrl.fromUserInput(text)
        except Exception:
            return text
        if not qurl.isValid():
            return text
        if qurl.isLocalFile():
            local_path = qurl.toLocalFile().strip()
            if local_path:
                return local_path
        if qurl.scheme():
            return qurl.toString()
        return text

    def _stream_display_name(self, source: str) -> str:
        text = str(source or "").strip()
        if not text:
            return ""
        try:
            qurl = QtCore.QUrl(text)
            if qurl.isLocalFile():
                base = os.path.basename(qurl.toLocalFile())
                if base:
                    return base
            if qurl.scheme():
                name = qurl.fileName().strip()
                if name:
                    return name
                host = qurl.host().strip()
                if host:
                    return host
        except Exception:
            pass
        return os.path.basename(text) or text

    def _target_tile_for_url_stream(self):
        selected = self.canvas.get_selected_tiles()
        if selected:
            return selected[0]
        spotlight = self.canvas.spotlight_tile()
        if spotlight is not None:
            return spotlight
        if self.canvas.tiles:
            return self.canvas.tiles[0]
        self.add_video()
        if self.canvas.tiles:
            return self.canvas.tiles[-1]
        return None

    def _open_recent_media_path_into_tile(self, tile, path: str) -> bool:
        if tile is None:
            return False
        normalized = os.path.abspath(os.path.normpath(str(path or "").strip()))
        if not normalized or not os.path.exists(normalized):
            QMessageBox.warning(
                self,
                self._tr("최근 미디어"),
                self._tr("파일을 찾을 수 없습니다.\n\n{path}", path=normalized),
            )
            self._prune_recent_media()
            return False
        prev_playlist = list(getattr(tile, "playlist", []) or [])
        try:
            prev_index = int(getattr(tile, "current_index", -1))
        except Exception:
            prev_index = -1
        try:
            was_playing = bool(getattr(getattr(tile, "mediaplayer", None), "is_playing", lambda: False)())
        except Exception:
            was_playing = False
        try:
            tile.clear_playlist()
            if not tile.add_to_playlist(normalized, play_now=True):
                raise RuntimeError(getattr(tile, "_last_set_media_error", "") or self._tr("파일을 열지 못했습니다."))
            if hasattr(tile, "_notify_playlist_changed"):
                tile._notify_playlist_changed(focus_mainwin=False)
            else:
                self.update_playlist()
            try:
                tile.setFocus()
            except Exception:
                pass
            self.statusBar().showMessage(self._tr("최근 미디어 열기: {value}", value=normalized), 3000)
            return True
        except Exception as exc:
            try:
                tile.clear_playlist()
                tile.playlist = list(prev_playlist)
                tile.current_index = int(prev_index)
                if 0 <= int(prev_index) < len(prev_playlist):
                    if tile.set_media(prev_playlist[int(prev_index)], show_error_dialog=False) and was_playing:
                        tile.play()
            except Exception:
                pass
            QMessageBox.warning(
                self,
                self._tr("최근 미디어"),
                self._tr("파일을 열지 못했습니다.\n\n{path}\n\n{error}", path=normalized, error=exc),
            )
            return False

    def _set_tile_stream_label(self, tile, source: str):
        if tile is None:
            return
        label = self._stream_display_name(source)
        try:
            fm = tile.title.fontMetrics()
            width = tile.title.maximumWidth()
            elided = fm.elidedText(label, QtCore.Qt.TextElideMode.ElideRight, width)
            tile.title.setText(elided)
            tile.title.setToolTip(source)
        except Exception:
            try:
                tile.title.setText(label)
                tile.title.setToolTip(source)
            except Exception:
                pass

    def _open_url_stream_into_tile(self, tile, source: str) -> bool:
        if tile is None:
            return False
        source = self._normalize_url_stream_input(source)
        if not source:
            return False
        prev_playlist = list(getattr(tile, "playlist", []) or [])
        try:
            prev_index = int(getattr(tile, "current_index", -1))
        except Exception:
            prev_index = -1
        try:
            was_playing = bool(getattr(getattr(tile, "mediaplayer", None), "is_playing", lambda: False)())
        except Exception:
            was_playing = False
        try:
            tile.clear_playlist()
            tile.playlist = [source]
            tile.current_index = 0
            if not tile.set_media(source, show_error_dialog=False):
                raise RuntimeError(getattr(tile, "_last_set_media_error", "") or self._tr("URL/스트림을 열지 못했습니다."))
            tile.play()
            self._set_tile_stream_label(tile, source)
            if hasattr(tile, "_notify_playlist_changed"):
                tile._notify_playlist_changed(focus_mainwin=False)
            else:
                self.update_playlist()
            try:
                tile.setFocus()
            except Exception:
                pass
            self.statusBar().showMessage(self._tr("URL/스트림 열기: {source}", source=source), 3000)
            return True
        except Exception as exc:
            try:
                tile.clear_playlist()
                tile.playlist = list(prev_playlist)
                tile.current_index = int(prev_index)
                if 0 <= int(prev_index) < len(prev_playlist):
                    if tile.set_media(prev_playlist[int(prev_index)], show_error_dialog=False) and was_playing:
                        tile.play()
            except Exception:
                pass
            QMessageBox.warning(
                self,
                self._tr("URL/스트림 열기"),
                self._tr("URL/스트림을 열지 못했습니다.\n\n{source}\n\n{error}", source=source, error=exc),
            )
            return False

    def open_url_stream(self):
        default_url = getattr(self, "_last_stream_url", "") or ""
        text, ok = QtWidgets.QInputDialog.getText(
            self,
            self._tr("URL/스트림 열기"),
            self._tr("URL 또는 스트림 주소를 입력하세요:"),
            QtWidgets.QLineEdit.EchoMode.Normal,
            default_url,
        )
        if not ok:
            return
        source = self._normalize_url_stream_input(text)
        if not source:
            QMessageBox.information(self, self._tr("URL/스트림 열기"), self._tr("주소를 입력하세요."))
            return
        tile = self._target_tile_for_url_stream()
        if self._open_url_stream_into_tile(tile, source):
            self._last_stream_url = source
            self._push_recent_media(source, kind="url")

    def open_recent_media(self, entry: Optional[Dict[str, str]] = None):
        if not isinstance(entry, dict):
            return
        kind = str(entry.get("kind", "path") or "path").strip().lower()
        value = str(entry.get("value", "") or "").strip()
        if not value:
            return
        target = self._target_tile_for_url_stream()
        if kind == "url":
            if self._open_url_stream_into_tile(target, value):
                self._last_stream_url = value
                self._push_recent_media(value, kind="url")
            return
        if self._open_recent_media_path_into_tile(target, value):
            self._push_recent_media(value, kind="path")

    def open_shortcut_dialog(self):
        current = self.current_shortcuts_or_defaults()
        dlg = ShortcutDialog(current, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            new_shortcuts = dlg.get_shortcuts()
            self.config["shortcuts"] = new_shortcuts
            self.rebind_shortcuts(new_shortcuts)
            self.save_config()

    def toggle_restore_last_session(self, checked: bool):
        enabled = bool(checked)
        self.config["restore_last_session"] = enabled
        self.save_config()
        self.statusBar().showMessage(
            self._tr("시작 시 마지막 세션 자동 복원: 켜짐" if enabled else "시작 시 마지막 세션 자동 복원: 꺼짐"),
            3000,
        )

    def _spotlight_hotkey(self, n: int):
        self._clear_tile_drag_state()
        if not self.keep_detached_tiles_for_focus_modes():
            self.canvas.redock_all_detached()
        idx = n - 1
        if 0 <= idx < len(self.canvas.tiles):
            if getattr(self.canvas, "spotlight_index", None) == idx:
                self.canvas.set_spotlight(None)
            else:
                self.canvas.set_spotlight(idx)
                target = self.canvas.tiles[idx]
                if getattr(self.canvas, "spotlight_index", None) == idx and getattr(target, "playlist", None):
                    target.play()
            self._restore_window_focus()

    def toggle_borders(self, checked: bool):
        self.canvas.set_borders_visible(checked)

    def set_layout_mode(self, mode: str):
        normalized = Canvas.normalize_layout_mode(mode)
        self.canvas.set_layout_mode(normalized)
        self._sync_layout_mode_menu_checks()

    def _sync_layout_mode_menu_checks(self):
        normalized = self.canvas.layout_mode()
        action = getattr(self, "layout_mode_actions", {}).get(normalized)
        if normalized in {Canvas.LAYOUT_ROLLER_ROW, Canvas.LAYOUT_ROLLER_COLUMN}:
            action = getattr(self, "roller_layout_actions", {}).get(
                (normalized, self.canvas.roller_visible_count())
            )
        if action is not None and not action.isChecked():
            action.setChecked(True)

    def set_roller_visible_count(self, count: int):
        normalized = Canvas.normalize_roller_visible_count(count)
        self.canvas.set_roller_visible_count(normalized)
        self._sync_layout_mode_menu_checks()

    def _refresh_roller_speed_action_label(self):
        action = getattr(self, "act_roller_speed", None)
        if action is None:
            return
        action.setText(
            self._tr("롤러 속도 조절... ({speed} px/s)", speed=self.canvas.roller_speed_px_per_sec())
        )

    def set_roller_speed(self, speed: int):
        self.canvas.set_roller_speed(speed)
        self._refresh_roller_speed_action_label()

    def set_roller_layout_mode(self, mode: str, count: int):
        normalized_mode = Canvas.normalize_layout_mode(mode)
        if normalized_mode not in {Canvas.LAYOUT_ROLLER_ROW, Canvas.LAYOUT_ROLLER_COLUMN}:
            return
        normalized_count = Canvas.normalize_roller_visible_count(count)
        self.canvas.set_roller_visible_count(normalized_count)
        self.canvas.set_layout_mode(normalized_mode)
        self._sync_layout_mode_menu_checks()

    def set_roller_paused(self, paused: bool):
        normalized = bool(paused)
        self.canvas.set_roller_paused(normalized)
        action = getattr(self, "act_pause_roller", None)
        if action is not None and action.isChecked() != normalized:
            action.setChecked(normalized)

    def open_roller_speed_dialog(self):
        current = self.canvas.roller_speed_px_per_sec()
        value, ok = QtWidgets.QInputDialog.getInt(
            self,
            self._tr("롤러 속도"),
            self._tr("롤러 속도 (px/s):"),
            current,
            Canvas.ROLLER_SPEED_MIN,
            Canvas.ROLLER_SPEED_MAX,
            5,
        )
        if not ok:
            return
        self.set_roller_speed(value)
        self.statusBar().showMessage(
            self._tr("롤러 속도: {speed} px/s", speed=self.canvas.roller_speed_px_per_sec()),
            3000,
        )

    def is_opacity_mode_active(self) -> bool:
        widget = getattr(self, "_docked_tiles_opacity_dock_window", None)
        return widget is not None

    def active_opacity_mode_widget(self):
        widget = getattr(self, "_docked_tiles_opacity_dock_window", None)
        if widget is None:
            return None
        return widget if self.is_opacity_mode_active() else None

    def _normalize_window_opacity_percent(self, value: Any) -> int:
        try:
            normalized = int(round(float(value)))
        except (TypeError, ValueError):
            normalized = 100
        return max(1, min(100, normalized))

    def current_main_window_opacity_percent(self) -> int:
        return int(self._normalize_window_opacity_percent(getattr(self, "window_opacity_percent", 100)))

    def set_main_window_opacity_percent(self, value: Any, *, save: bool = True) -> None:
        normalized = self._normalize_window_opacity_percent(value)
        self.window_opacity_percent = normalized
        self.config["window_opacity_percent"] = normalized
        try:
            self.setWindowOpacity(max(0.01, min(1.0, float(normalized) / 100.0)))
        except Exception:
            pass
        self._sync_opacity_mode_corner_controls()
        if save:
            try:
                self.save_config()
            except Exception:
                pass

    def _sync_opacity_mode_button_state(self) -> None:
        button = getattr(self, "btn_docked_tiles_opacity", None)
        if button is None:
            return
        try:
            with QtCore.QSignalBlocker(button):
                button.setChecked(bool(self.is_opacity_mode_active()))
        except Exception:
            pass

    def _sync_opacity_mode_corner_controls(self) -> None:
        active = self.active_opacity_mode_widget()
        is_active = active is not None
        for name in ("btn_opacity_mode_fullscreen", "btn_opacity_mode_redock"):
            widget = getattr(self, name, None)
            if widget is None:
                continue
            try:
                widget.setVisible(False)
            except Exception:
                pass
        slider = getattr(self, "sld_docked_tiles_opacity", None)
        if slider is not None:
            try:
                slider.setVisible(not is_active)
                with QtCore.QSignalBlocker(slider):
                    slider.setValue(
                        active.shared_percent()
                        if active is not None
                        else self.current_main_window_opacity_percent()
                    )
            except Exception:
                pass
        fullscreen_button = getattr(self, "btn_opacity_mode_fullscreen", None)
        if fullscreen_button is not None:
            try:
                fullscreen_button.setVisible(False)
            except Exception:
                pass

    def _set_active_opacity_mode_percent(self, value: int) -> None:
        active = self.active_opacity_mode_widget()
        if active is None:
            self.set_main_window_opacity_percent(int(value))
            return
        try:
            active.set_shared_percent(int(value))
        except Exception:
            pass

    def _toggle_active_opacity_mode_fullscreen(self) -> None:
        self.toggle_fullscreen()

    def _exit_active_opacity_mode_fullscreen_if_needed(self) -> bool:
        if not self.is_opacity_mode_active():
            return False
        if not self._is_fullscreen():
            return False
        self.exit_fullscreen()
        return True

    def _close_active_opacity_mode(self) -> None:
        active = self.active_opacity_mode_widget()
        if active is None:
            return
        try:
            active.close()
        except Exception:
            pass

    def _set_opacity_mode_chrome_visible(self, visible: bool) -> None:
        visible = bool(visible)
        try:
            self.menuBar().setVisible(visible)
        except Exception:
            pass
        toolbar = getattr(self, "control_toolbar", None)
        if toolbar is not None:
            try:
                toolbar.setVisible(visible)
            except Exception:
                pass
        try:
            status = self.statusBar()
            if status is not None:
                status.setVisible(visible)
        except Exception:
            pass

    def _finalize_opacity_mode_widget(self, widget) -> None:
        if getattr(self, "_docked_tiles_opacity_dock_window", None) is widget:
            self._docked_tiles_opacity_dock_window = None
        self._set_opacity_mode_chrome_visible(True)
        self._sync_opacity_mode_button_state()
        self._sync_opacity_mode_corner_controls()

    def _show_opacity_mode_widget(self, widget) -> None:
        if widget is None:
            return
        self._set_opacity_mode_chrome_visible(True)
        self._sync_opacity_mode_button_state()
        self._sync_opacity_mode_corner_controls()
        widget.show()
        widget.raise_()
        try:
            widget.activateWindow()
            widget.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
        except Exception:
            pass

    def open_docked_tiles_opacity_dialog(self):
        existing = getattr(self, "_docked_tiles_opacity_dock_window", None)
        if self.is_opacity_mode_active() and existing is not None:
            try:
                existing._show_overlay_transient()
                existing.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
            except Exception:
                pass
            return
        if not hasattr(self.canvas, "docked_media_tiles"):
            return
        targets = list(self.canvas.docked_media_tiles())
        if not targets:
            QtWidgets.QMessageBox.information(
                self,
                self._tr("비교 오버레이"),
                self._tr("도킹 상태의 미디어 타일이 없습니다."),
            )
            return
        current_percent = self.current_main_window_opacity_percent()
        compare_percent = min(current_percent, 60)
        if existing is not None:
            try:
                existing.close()
            except Exception:
                pass
            self._finalize_opacity_mode_widget(existing)
        dock = DetachedTilesCompareOverlayController(
            self.canvas,
            targets,
            parent=self,
            title=self._tr("비교 오버레이"),
            initial_percent=compare_percent,
            initial_offset_ms=-1000,
        )
        dock.closed.connect(lambda page=dock: self._finalize_opacity_mode_widget(page))
        dock.destroyed.connect(lambda *_args, page=dock: self._finalize_opacity_mode_widget(page))
        dock.sharedPercentChanged.connect(lambda *_args: self._sync_opacity_mode_corner_controls())
        dock.fullscreenChanged.connect(lambda *_args: self._sync_opacity_mode_corner_controls())
        self._docked_tiles_opacity_dock_window = dock
        self._show_opacity_mode_widget(dock)

    def toggle_compact_mode(self, checked: bool):
        focus_target = self._capture_managed_focus_window()
        self.canvas.set_compact_mode(checked)
        self.canvas.set_detached_windows_compact_mode(checked)
        if self._is_fullscreen():
            if checked:
                self._apply_fullscreen_ui_mode("hidden")
            else:
                self._show_cursor()
        else:
            self._sync_windowed_ui_from_compact_mode()
        try:
            self._restore_managed_window_focus(focus_target)
        except Exception:
            pass

    def _delete_selected(self):
        selected = self.canvas.get_selected_tiles()
        for t in selected:
            self.canvas.remove_tile(t)

    def _remove_from_playlist(self):
        remove_current_playlist_items_impl(self)

    def _remove_and_trash_file(self):
        trash_current_playlist_items_impl(self)

    def _delete_tile(self):
        for t in self.canvas.get_selected_tiles(for_delete=True):
            self.canvas.remove_tile(t)

    def open_files_into_tile(self, tile):
        start_dir = self.config.get("last_dir", "") or os.path.expanduser("~")
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            self._tr("미디어 열기"),
            start_dir,
            media_file_dialog_filter(),
        )
        if not files:
            return
        self.last_dir = os.path.dirname(files[0])
        self.config["last_dir"] = self.last_dir
        self._push_recent_media_many(files, kind="path")
        tile.clear_playlist()
        for i, path in enumerate(files):
            tile.add_to_playlist(path, play_now=(i == 0))
        self.update_playlist()
        self.setFocus()

    def _apply_always_on_top(self, checked: bool):
        was_visible = self.isVisible()
        was_maximized = self.isMaximized()
        was_fullscreen = self.isFullScreen() or bool(
            self.windowState() & QtCore.Qt.WindowState.WindowFullScreen
        )
        geom = self.geometry()
        flags = self.windowFlags()
        if checked:
            self.setWindowFlags(flags | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~QtCore.Qt.WindowType.WindowStaysOnTopHint)
        if was_fullscreen:
            self.showFullScreen()
        elif was_maximized:
            self.showMaximized()
        elif was_visible:
            self.showNormal()
            self.setGeometry(geom)
        else:
            self.setGeometry(geom)
        if was_visible:
            try:
                self.raise_()
            except Exception:
                pass
            try:
                self.activateWindow()
            except Exception:
                pass
        self.canvas.set_detached_windows_on_top(checked)
        self.config["always_on_top"] = checked

    def toggle_always_on_top(self, checked: bool):
        self._apply_always_on_top(checked)

    def open_folder(self):
        # 마지막 경로 or 홈
        start_dir = self.config.get("last_dir", "") or os.path.expanduser("~")
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, self._tr("폴더 열기"), start_dir)
        if not folder:
            return

        self.config["last_dir"] = folder

        # ✅ 하위 폴더까지 재귀적으로 수집
        files = []
        for root, dirs, filenames in os.walk(folder, topdown=True):
            dirs.sort()  # 폴더명 정렬(안정적인 순서)
            filenames.sort()  # 파일명 정렬
            for name in filenames:
                if os.path.splitext(name)[1].lower() in VIDEO_FILE_EXTENSIONS:
                    p = os.path.join(root, name)
                    if os.path.isfile(p):
                        files.append(p)

        if not files:
            QtWidgets.QMessageBox.warning(
                self,
                self._tr("안내"),
                self._tr("해당 폴더(하위 포함)에 영상 파일이 없습니다."),
            )
            return

        # 타일 없으면 기본 4개 생성
        if not self.canvas.tiles:
            for _ in range(4):
                self.canvas.add_tile()

        # 기존 플레이리스트 초기화
        n_tiles = len(self.canvas.tiles)
        for t in self.canvas.tiles:
            t.clear_playlist()

        # 균등 분배 로드 (처음 n_tiles개는 즉시 재생)
        for i, path in enumerate(files):
            t = self.canvas.tiles[i % n_tiles]
            QtCore.QTimer.singleShot(
                0,
                lambda t=t, p=path, play=(i < n_tiles): t.add_to_playlist(p, play_now=play)
            )

        QtCore.QTimer.singleShot(0, self.update_playlist)
        self.canvas.relayout()
        self.setFocus()

    def _is_fullscreen(self) -> bool:
        return bool(self.windowState() & QtCore.Qt.WindowState.WindowFullScreen) or self.isFullScreen()

    def _is_compact_mode(self) -> bool:
        try:
            return bool(self.compact_action.isChecked())
        except Exception:
            return False

    def _show_tile_ui(self, tile):
        """[수정] 특정 타일의 UI만 표시 (하단 영역 호버)"""
        self._show_top_ui(False) # 🟢 상단은 명시적으로 숨김
        for t in self.canvas.tiles:
            try:
                # 컴팩트 모드가 아닐 때, 해당 타일만 표시
                is_target = (t is tile)
                show = is_target and (not self._is_compact_mode())
                t.show_controls(show)
            except Exception:
                pass

    def _selected_tiles(self):
        out = []
        try:
            for t in self.canvas.tiles:
                if getattr(t, "is_selected", False):
                    out.append(t)
        except Exception:
            pass
        return out

    def mute_selected_tiles(self, on: bool | None = None):
        tiles = self._selected_tiles()
        if not tiles:
            return
        for t in tiles:
            try:
                if on is None:
                    t.toggle_tile_mute()
                else:
                    t.set_tile_muted(bool(on))
            except Exception:
                pass

    def _toggle_tile_mute_selected(self):
        tiles = self.canvas.get_selected_tiles()
        if not tiles:
            return
        all_muted = all(getattr(t, "tile_muted", False) for t in tiles)
        for t in tiles:
            try:
                t.set_tile_muted(not all_muted)
            except Exception:
                pass

    def _create_playlist_dock(self):
        create_playlist_dock_impl(self)

    def _create_bookmark_dock(self):
        create_bookmark_dock_impl(self)

    def _bookmark_categories_payload(self) -> list[str]:
        return bookmark_categories_payload_impl(self)

    def _bookmark_payload(self) -> list[dict[str, Any]]:
        return bookmark_payload_impl(self)

    def _bookmark_positions_for_path(self, path: Optional[str]) -> list[int]:
        return bookmark_positions_for_path_impl(self, path)

    def _selected_bookmark_positions_for_path(self, path: Optional[str]) -> list[int]:
        return selected_bookmark_positions_for_path_impl(self, path)

    def _select_bookmarks_for_path_positions(self, path: Optional[str], positions_ms, *, toggle: bool = False) -> bool:
        return select_bookmarks_for_path_positions_impl(self, path, positions_ms, toggle=toggle)

    def bookmark_marks_visible(self) -> bool:
        return bookmark_marks_visible_impl(self)

    def _refresh_bookmark_marks(self):
        return refresh_bookmark_marks_impl(self)

    def set_bookmark_marks_visible(self, checked: bool):
        return set_bookmark_marks_visible_impl(self, checked)

    def _load_bookmarks(self, payload: Any):
        return load_bookmarks_impl(self, payload)

    def _load_bookmark_categories(self, payload: Any):
        return load_bookmark_categories_impl(self, payload)

    def _refresh_bookmark_dock(self, *, keep_selection: bool = True):
        return refresh_bookmark_dock_impl(self, keep_selection=keep_selection)

    def _refresh_bookmark_ui_texts(self):
        return refresh_bookmark_ui_texts_impl(self)

    def toggle_bookmark_visibility(self, checked: Optional[bool] = None):
        return toggle_bookmark_visibility_impl(self, checked)

    def add_bookmark_from_current(self):
        return add_bookmark_from_current_impl(self)

    def _add_bookmark_category(self):
        return add_bookmark_category_impl(self)

    def _add_bookmarks_for_path_positions(self, path: str, positions_ms):
        return add_bookmarks_for_path_positions_impl(self, path, positions_ms)

    def _add_bookmarks_for_path_ranges(self, path: str, ranges_ms):
        return add_bookmarks_for_path_ranges_impl(self, path, ranges_ms)

    def add_bookmark_from_tile(self, tile):
        return add_bookmark_from_tile_impl(self, tile)

    def _jump_to_selected_bookmark(self):
        return jump_to_selected_bookmark_impl(self)

    def _delete_selected_bookmarks(self):
        return delete_selected_bookmarks_impl(self)

    def _classify_selected_bookmarks(self):
        return classify_selected_bookmarks_impl(self)

    def request_playlist_refresh(self, *, force: bool = False, delay_ms: int = 0):
        request_playlist_refresh_impl(self, force=force, delay_ms=delay_ms)

    def _flush_playlist_refresh(self):
        flush_playlist_refresh_impl(self)

    def toggle_playlist_visibility(self, checked: Optional[bool] = None):
        toggle_playlist_visibility_impl(self, checked)

    def _refresh_playlist_ui_texts(self):
        refresh_playlist_ui_texts_impl(self)

    def _adjust_tile_current_index_after_row_removal(
        self,
        tile,
        removed_rows: list[int],
        was_playing_override: Optional[bool] = None,
    ):
        adjust_tile_current_index_after_row_removal_impl(
            self,
            tile,
            removed_rows,
            was_playing_override=was_playing_override,
        )

    def _playlist_filter_text(self) -> str:
        return playlist_filter_text_impl(self)

    def _playlist_sort_mode(self) -> str:
        return playlist_sort_mode_impl(self)

    def _playlist_sort_descending(self) -> bool:
        return playlist_sort_descending_impl(self)

    def _set_playlist_sort_controls(self, mode: str, descending: bool):
        set_playlist_sort_controls_impl(self, mode, descending)

    def _sync_playlist_sort_order_button_text(self):
        sync_playlist_sort_order_button_text_impl(self)

    def _on_playlist_sort_changed(self):
        on_playlist_sort_changed_impl(self)

    def _on_playlist_sort_order_toggled(self, checked: bool):
        on_playlist_sort_order_toggled_impl(self, checked)

    def _playlist_sort_name(self, path: str) -> str:
        return playlist_sort_name_impl(self, path)

    def _playlist_natural_key(self, text: str):
        return playlist_natural_key_impl(self, text)

    def _playlist_first_number_key(self, text: str):
        return playlist_first_number_key_impl(self, text)

    def _playlist_first_visible_char(self, text: str) -> str:
        return playlist_first_visible_char_impl(self, text)

    def _playlist_is_ascii_alpha_lead(self, text: str) -> bool:
        return playlist_is_ascii_alpha_lead_impl(self, text)

    def _playlist_is_hangul_lead(self, text: str) -> bool:
        return playlist_is_hangul_lead_impl(self, text)

    def _playlist_sort_key_for_path(self, path: str, mode: str):
        return playlist_sort_key_for_path_impl(self, path, mode)

    def _sorted_playlist_for_mode(self, plist: list[str], mode: str, descending: bool) -> list[str]:
        return sorted_playlist_for_mode_impl(self, plist, mode, descending)

    def _apply_playlist_sort(self):
        apply_playlist_sort_impl(self)

    def _playlist_path_matches_filter(self, path: str, query: str) -> bool:
        return playlist_path_matches_filter_impl(self, path, query)

    def _normalize_playlist_path(self, path: Optional[str]) -> str:
        return normalize_playlist_path_impl(self, path)

    def _playlist_current_path_for_tile(self, tile) -> str:
        return playlist_current_path_for_tile_impl(self, tile)

    def _playlist_tile_is_playing(self, tile) -> bool:
        return playlist_tile_is_playing_impl(self, tile)

    def _apply_playlist_current_item_style(self, leaf, *, is_current: bool, is_playing: bool):
        apply_playlist_current_item_style_impl(self, leaf, is_current=is_current, is_playing=is_playing)

    def _duration_cache_signature(self, path: str) -> tuple[int, int]:
        return duration_cache_signature_impl(self, path)

    def _format_duration_ms(self, ms: int) -> str:
        return format_duration_ms_impl(self, ms)

    def _probe_duration_ms(self, path: str) -> Optional[int]:
        return probe_duration_ms_impl(self, path)

    def _playlist_duration_info(self, path: str) -> tuple[Optional[int], str]:
        return playlist_duration_info_impl(self, path)

    def update_playlist(self, force: bool = False):
        update_playlist_impl(self, force=force)

    def _tile_idx_from_selection(self):
        return tile_idx_from_selection_impl(self)

    def _on_playlist_context_menu(self, pos):
        on_playlist_context_menu_impl(self, pos)

    def _pl_open_files_into_tile(self):
        pl_open_files_into_tile_impl(self)

    def _trash_path(self, path: str) -> bool:
        return trash_path_impl(self, path)

    def _trash_playlist_entry(self, tile, row: int, path: str) -> tuple[bool, bool]:
        return trash_playlist_entry_impl(self, tile, row, path)

    def _pl_open_folder_into_tile(self):
        pl_open_folder_into_tile_impl(self)

    def _pl_delete_selected(self, trash: bool):
        pl_delete_selected_impl(self, trash)

    def _pl_open_selected_in_explorer(self):
        pl_open_selected_in_explorer_impl(self)

    def _on_files_moved_between_tiles(self, dst_tile_idx: int, entries: list[tuple[int, int, str]]):
        on_files_moved_between_tiles_impl(self, dst_tile_idx, entries)

    def _play_from_tile_row(self, payload, row: Optional[int] = None):
        play_from_tile_row_impl(self, payload, row)

    def play_from_playlist(self, item, column):
        play_from_playlist_impl(self, item, column)

    def open_keymap_dialog(self):
        self.open_shortcut_dialog()

    def _tile_at_global(self, gp: QtCore.QPoint, preferred_window: Optional[QtWidgets.QWidget] = None):
        try:
            tiles = list(getattr(self.canvas, "tiles", []))
            if not tiles:
                return None
            preferred_top = preferred_window.window() if isinstance(preferred_window, QtWidgets.QWidget) else preferred_window

            # 빠른 경로: 포인터 아래 위젯에서 부모 체인을 타고 타일을 찾는다.
            tile_set = set(tiles)
            w = QtWidgets.QApplication.widgetAt(gp)
            if preferred_top is not None and w is not None:
                top = w.window()
                if top is not preferred_top:
                    return None
            while w is not None:
                if w in tile_set:
                    return w
                w = w.parentWidget()

            # 폴백: 기하 검사(기존 방식)
            for t in tiles:
                if preferred_top is not None and t.window() is not preferred_top:
                    continue
                r = t.rect()
                grect = QtCore.QRect(t.mapToGlobal(r.topLeft()), t.mapToGlobal(r.bottomRight()))
                if grect.contains(gp):
                    return t
        except Exception:
            pass
        return None

    def _is_main_window_click_source(self, obj, gp: QtCore.QPoint) -> bool:
        try:
            source_top = obj.window() if isinstance(obj, QtWidgets.QWidget) else None
            w = obj if isinstance(obj, QtWidgets.QWidget) else None
            if w is None:
                w = QtWidgets.QApplication.widgetAt(gp)

            if w is not None:
                top = w.window()
                if source_top is not None and top is not source_top:
                    return False
                return top is self or self.canvas.is_managed_window(top)

            # widgetAt가 None인 경우(일부 네이티브 렌더 영역)에는
            # 관리 중인 창이 활성 상태이고 포인터 아래에 타일이 있을 때만 허용
            return bool(self._is_main_window_active() and self._tile_at_global(gp, preferred_window=source_top) is not None)
        except Exception:
            return False

    def _select_by_global_point(
        self,
        gp: QtCore.QPoint,
        mods: QtCore.Qt.KeyboardModifier,
        toggle_single_off: bool = True,
        source_window: Optional[QtWidgets.QWidget] = None,
    ):
        tiles = getattr(self.canvas, "tiles", [])
        if not tiles:
            return

        tile = self._tile_at_global(gp, preferred_window=source_window)
        if tile is None:
            return

        # 안전: 최초 호출 시 인덱스 상태 보장
        if not hasattr(self, "_last_sel_idx"):
            self._last_sel_idx = None

        # 도우미
        def _idx_of(t):
            try:
                return tiles.index(t)
            except ValueError:
                return None

        def _clear_and_select_one(target):
            for t in selected_tiles:
                if t is not target:
                    t.set_selection("off")
            if getattr(target, "selection_mode", "off") != "normal":
                target.set_selection("normal")
            self._last_sel_idx = _idx_of(target)

        # 현재 선택 목록
        selected_tiles = [t for t in tiles if getattr(t, "is_selected", False)]

        # --- 기본(수정키 없음): 같은 타일 재선택 시 해제 토글 ---
        if mods == QtCore.Qt.KeyboardModifier.NoModifier:
            only_this_selected = (
                len(selected_tiles) == 1
                and selected_tiles[0] is tile
                and getattr(tile, "selection_mode", "off") == "normal"
            )
            if toggle_single_off and getattr(tile, "is_selected", False) and only_this_selected:
                # 같은 타일을 다시 선택 → 해제
                tile.set_selection("off")
                self._last_sel_idx = None
                return
            # 그 외에는 단일 선택으로 수렴
            _clear_and_select_one(tile)
            return

        # --- Ctrl: 다중 개별 토글 ---
        if mods & QtCore.Qt.KeyboardModifier.ControlModifier:
            if getattr(tile, "is_selected", False):
                tile.set_selection("off")
            else:
                tile.set_selection("normal")
            self._last_sel_idx = _idx_of(tile)
            return

        # --- Shift: '삭제전용' 단일 토글(범위 없음 요청 반영) ---
        if mods & QtCore.Qt.KeyboardModifier.ShiftModifier:
            # 현재 타일만 빨간(삭제전용) 토글
            is_delete = (getattr(tile, "selection_mode", "") == "delete")
            tile.set_selection("off" if is_delete else "delete")
            self._last_sel_idx = _idx_of(tile)
            return

        # 그 외 키조합은 안전하게 단일 선택으로 처리
        _clear_and_select_one(tile)


if __name__ == "__main__":
    multiprocessing.freeze_support()

    # ✅ DPI 꼬임 방지 (먼저!)
    QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(
        QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(multi_play_app_icon())
    remember_system_theme(app)

    w = MainWin()
    w.show()

    sys.exit(app.exec())
