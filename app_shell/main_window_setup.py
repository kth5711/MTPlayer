import sys
from typing import Any, Dict, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from canvas import Canvas
from canvas_support import DetachedTilesCompareOverlayController
from .config import _default_config_path
from i18n import SUPPORTED_UI_LANGUAGES, language_name, normalize_ui_language
from .session import SessionManager
from .theme import SUPPORTED_UI_THEMES, apply_ui_theme, normalize_ui_theme, remember_system_theme, theme_label_key
import vlc


def initialize_main_window_core(main, config_path: Optional[str] = None) -> None:
    main.config_path = config_path or _default_config_path()
    main.session_manager = SessionManager(main.config_path)
    loaded_config = main.session_manager.load()
    main.config: Dict[str, Any] = dict(loaded_config) if isinstance(loaded_config, dict) else {}
    main.ui_language = normalize_ui_language(main.config.get("language", "ko"))
    main.ui_theme = normalize_ui_theme(main.config.get("theme", "black"))
    main.setWindowTitle("Multi-Play")
    main.resize(800, 800)
    main.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
    main.vlc_hw_decode_enabled = bool(main.config.get("vlc_hw_decode", False))

    if sys.platform == "win32":
        hw_mode = "d3d11va" if main.vlc_hw_decode_enabled else "none"
        main.vlc_instance_args = (
            f"--avcodec-hw={hw_mode}",
            "--no-video-title-show",
            "--aout=directsound",
            "--no-xlib",
            "--file-caching=200",
            "--network-caching=200",
        )
    else:
        main.vlc_instance_args = ("--avcodec-hw=vaapi", "--no-video-title-show")
    main.vlc_instance = vlc.Instance(*main.vlc_instance_args)
    if sys.platform == "win32":
        print(f"VLC hw decode mode: {'d3d11va' if main.vlc_hw_decode_enabled else 'none'}")

    app = QtWidgets.QApplication.instance()
    if app is not None:
        remember_system_theme(app)
        apply_ui_theme(app, main.ui_theme)

    main.canvas = Canvas(main, vlc_instance=main.vlc_instance)
    main.central_mode_stack = QtWidgets.QStackedWidget(main)
    main.central_mode_stack.setContentsMargins(0, 0, 0, 0)
    main.central_mode_stack.addWidget(main.canvas)
    main.opacity_mode_widget_class = DetachedTilesCompareOverlayController
    main._docked_tiles_opacity_dock_window = None
    main.setCentralWidget(main.central_mode_stack)
    main.set_main_window_opacity_percent(main.config.get("window_opacity_percent", 100), save=False)
    main.playback_rate = 1.0
    main.dynamic_shortcuts = []
    main.tile_hotkey_actions = {}
    main.seek_hotkey_steps = {}
    main._bookmark_marker_select_mode = False
    main._last_stream_url = ""


def initialize_main_window_menus(main) -> None:
    bar = main.menuBar()
    file_menu = bar.addMenu(main._tr("파일"))
    main.file_menu = file_menu
    main.act_open = file_menu.addAction(main._tr("영상 열기"))
    main.act_open_multi = file_menu.addAction(main._tr("영상 새 타일로 열기"))
    main.act_open_folder = file_menu.addAction(main._tr("폴더 열기"))
    main.act_open_url = file_menu.addAction(main._tr("URL/스트림 열기..."))
    main.recent_media_menu = file_menu.addMenu(main._tr("최근 미디어"))
    file_menu.addSeparator()
    main.act_save_profile = file_menu.addAction(main._tr("프로필 저장"))
    main.act_load_profile = file_menu.addAction(main._tr("프로필 불러오기"))
    main.recent_profiles_menu = file_menu.addMenu(main._tr("최근 프로필"))
    file_menu.addSeparator()
    main.act_quit = file_menu.addAction(main._tr("종료"))

    view_menu = bar.addMenu(main._tr("보기"))
    main.view_menu = view_menu
    main.border_action = view_menu.addAction(main._tr("타일 테두리 표시"))
    main.border_action.setCheckable(True); main.border_action.setChecked(True)
    main.border_action.triggered.connect(main.toggle_borders)

    main.compact_action = view_menu.addAction(main._tr("영상만 보기 모드"))
    main.compact_action.setCheckable(True)
    main.compact_action.setChecked(False)
    main.compact_action.triggered.connect(main.toggle_compact_mode)
    main.addAction(main.compact_action)

    main.always_on_top_action = view_menu.addAction(main._tr("재생 중 항상 위"))
    main.always_on_top_action.setCheckable(True)
    main.always_on_top_action.setChecked(False)
    main.always_on_top_action.triggered.connect(main.toggle_always_on_top)
    main.act_docked_tiles_opacity = view_menu.addAction(main._tr("비교 오버레이 열기..."))
    main.act_docked_tiles_opacity.triggered.connect(main.open_docked_tiles_opacity_dialog)

    _initialize_layout_mode_menu(main, view_menu)

    main.act_roller_speed = view_menu.addAction("")
    main.act_roller_speed.triggered.connect(main.open_roller_speed_dialog)
    main.act_pause_roller = view_menu.addAction(main._tr("롤러 정지"))
    main.act_pause_roller.setCheckable(True); main.act_pause_roller.setChecked(False)
    main.act_pause_roller.toggled.connect(main.set_roller_paused)
    main.keep_detached_focus_mode_action = view_menu.addAction(main._tr("전체화면/스포트라이트 시 분리 유지"))
    main.keep_detached_focus_mode_action.setCheckable(True)
    main.keep_detached_focus_mode_action.setChecked(False)
    main._refresh_roller_speed_action_label()
    main._sync_layout_mode_menu_checks()

    _initialize_list_menu(main, bar)

    setting_menu = bar.addMenu(main._tr("설정"))
    main.setting_menu = setting_menu
    main.act_shortcut = setting_menu.addAction(main._tr("단축키 설정"))
    main.act_restore_last_session = setting_menu.addAction(main._tr("시작 시 마지막 세션 자동 복원"))
    main.act_restore_last_session.setCheckable(True)
    main.act_restore_last_session.setChecked(bool(main.config.get("restore_last_session", False)))
    main.language_menu = setting_menu.addMenu(main._tr("언어"))
    main.language_action_group = QtGui.QActionGroup(main)
    main.language_action_group.setExclusive(True)
    main.language_actions = {}
    for code in SUPPORTED_UI_LANGUAGES:
        action = main.language_menu.addAction(language_name(code))
        action.setCheckable(True)
        action.setData(code)
        action.triggered.connect(lambda _checked=False, c=code: main.set_ui_language(c))
        main.language_action_group.addAction(action)
        main.language_actions[code] = action
    main.theme_menu = setting_menu.addMenu(main._tr("테마"))
    main.theme_action_group = QtGui.QActionGroup(main)
    main.theme_action_group.setExclusive(True)
    main.theme_actions = {}
    for code in SUPPORTED_UI_THEMES:
        action = main.theme_menu.addAction(main._tr(theme_label_key(code)))
        action.setCheckable(True)
        action.setData(code)
        action.triggered.connect(lambda _checked=False, c=code: main.set_ui_theme(c))
        main.theme_action_group.addAction(action)
        main.theme_actions[code] = action

    main.act_open.triggered.connect(lambda: main.open_multiple_videos(distribute=True))
    main.act_open_multi.triggered.connect(lambda: main.open_multiple_videos(distribute=False))
    main.act_open_folder.triggered.connect(main.open_folder)
    main.act_open_url.triggered.connect(main.open_url_stream)
    main.act_save_profile.triggered.connect(main.save_profile)
    main.act_load_profile.triggered.connect(main.load_profile)
    main.act_quit.triggered.connect(main.close)
    main.act_shortcut.triggered.connect(main.open_shortcut_dialog)
    main.act_restore_last_session.toggled.connect(main.toggle_restore_last_session)


def _initialize_layout_mode_menu(main, view_menu) -> None:
    main.layout_mode_menu = view_menu.addMenu(main._tr("타일 배치 방식"))
    main.layout_mode_group = QtGui.QActionGroup(main)
    main.layout_mode_group.setExclusive(True)
    main.layout_mode_actions = {}
    main.roller_layout_menus = {}
    main.roller_layout_actions = {}
    roller_modes = {Canvas.LAYOUT_ROLLER_ROW, Canvas.LAYOUT_ROLLER_COLUMN}
    for mode, label in Canvas.LAYOUT_LABELS.items():
        if mode in roller_modes:
            continue
        action = main.layout_mode_menu.addAction(main._tr(label))
        action.setCheckable(True)
        action.setData(mode)
        action.triggered.connect(lambda _checked=False, m=mode: main.set_layout_mode(m))
        main.layout_mode_group.addAction(action)
        main.layout_mode_actions[mode] = action
    main.layout_mode_menu.addSeparator()
    for mode in (Canvas.LAYOUT_ROLLER_ROW, Canvas.LAYOUT_ROLLER_COLUMN):
        submenu = main.layout_mode_menu.addMenu(main._tr(Canvas.LAYOUT_LABELS[mode]))
        main.roller_layout_menus[mode] = submenu
        for count in Canvas.ROLLER_VISIBLE_COUNT_OPTIONS:
            action = submenu.addAction(main._tr("{count}개", count=count))
            action.setCheckable(True)
            action.setData((mode, count))
            action.triggered.connect(lambda _checked=False, m=mode, c=count: main.set_roller_layout_mode(m, c))
            main.layout_mode_group.addAction(action)
            main.roller_layout_actions[(mode, count)] = action


def _initialize_list_menu(main, bar) -> None:
    list_menu = bar.addMenu(main._tr("리스트"))
    main.list_menu = list_menu
    main.bookmark_menu = list_menu
    main.act_toggle_playlist_dock = list_menu.addAction(main._tr("플레이리스트 창 (도킹)"))
    main.act_toggle_playlist_dock.setCheckable(True)
    main.act_toggle_playlist_dock.setChecked(False)
    main.addAction(main.act_toggle_playlist_dock)
    list_menu.addSeparator()
    main.act_toggle_bookmark_dock = list_menu.addAction(main._tr("북마크 창 (도킹)"))
    main.act_toggle_bookmark_dock.setCheckable(True)
    main.act_toggle_bookmark_dock.setChecked(False)
    main.addAction(main.act_toggle_bookmark_dock)
    main.act_toggle_bookmark_marks = list_menu.addAction(main._tr("재생바 북마크 표시"))
    main.act_toggle_bookmark_marks.setCheckable(True)
    main.act_toggle_bookmark_marks.setChecked(True)


def initialize_main_window_controls(main, bind_bookmark_context_menu) -> None:
    main.master_corner_widget = QtWidgets.QWidget(main.menuBar())
    main.master_corner_layout = QtWidgets.QHBoxLayout(main.master_corner_widget)
    main.master_corner_layout.setContentsMargins(0, 0, 0, 0)
    main.master_corner_layout.setSpacing(6)

    main.btn_docked_tiles_opacity = None

    main.sld_docked_tiles_opacity = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, main.master_corner_widget)
    main.sld_docked_tiles_opacity.setRange(1, 100)
    main.sld_docked_tiles_opacity.setSingleStep(1)
    main.sld_docked_tiles_opacity.setPageStep(5)
    main.sld_docked_tiles_opacity.setFixedWidth(160)
    main.sld_docked_tiles_opacity.setValue(int(getattr(main, "window_opacity_percent", 100)))
    main.master_corner_layout.addWidget(main.sld_docked_tiles_opacity, 1)

    main.btn_opacity_mode_fullscreen = QtWidgets.QPushButton(main._tr("전체화면"), main.master_corner_widget)
    main.btn_opacity_mode_fullscreen.setAutoDefault(False)
    main.btn_opacity_mode_fullscreen.setDefault(False)
    main.btn_opacity_mode_fullscreen.hide()
    main.master_corner_layout.addWidget(main.btn_opacity_mode_fullscreen, 0)

    main.btn_opacity_mode_redock = QtWidgets.QPushButton(main._tr("복귀"), main.master_corner_widget)
    main.btn_opacity_mode_redock.setAutoDefault(False)
    main.btn_opacity_mode_redock.setDefault(False)
    main.btn_opacity_mode_redock.hide()
    main.master_corner_layout.addWidget(main.btn_opacity_mode_redock, 0)

    main.sld_master = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, main.master_corner_widget)
    main.sld_master.setRange(0, 100)
    main.sld_master.setSingleStep(5)
    main.sld_master.setPageStep(5)
    main.sld_master.setValue(80)
    main.sld_master.valueChanged.connect(main.on_master_volume)
    main.sld_master.sliderReleased.connect(main._snap_master)
    main.sld_master.hide()
    main.menuBar().setCornerWidget(main.master_corner_widget, QtCore.Qt.Corner.TopRightCorner)

    main.sld_docked_tiles_opacity.valueChanged.connect(main._set_active_opacity_mode_percent)
    main.btn_opacity_mode_fullscreen.clicked.connect(main._toggle_active_opacity_mode_fullscreen)
    main.btn_opacity_mode_redock.clicked.connect(main._close_active_opacity_mode)

    toolbar = main.addToolBar("Control")
    main.control_toolbar = toolbar
    btn_minus = QtWidgets.QPushButton("-")
    btn_plus = QtWidgets.QPushButton("+")
    btn_minus.clicked.connect(main.remove_last)
    btn_plus.clicked.connect(main.add_video)
    toolbar.addWidget(btn_minus)
    toolbar.addWidget(btn_plus)

    for key_text, handler in (
        ("F11", main.toggle_fullscreen),
        ("Escape", main._handle_escape),
        ("Delete", main._remove_from_playlist),
        ("Shift+Delete", main._remove_and_trash_file),
        ("Ctrl+Delete", main._delete_tile),
    ):
        shortcut = QtGui.QShortcut(QtGui.QKeySequence(key_text), main)
        shortcut.setContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        shortcut.activated.connect(handler)

    main._create_playlist_dock()
    main._create_bookmark_dock()
    bind_bookmark_context_menu(main)
    main.act_toggle_playlist_dock.triggered.connect(main.toggle_playlist_visibility)
    main.act_toggle_bookmark_dock.triggered.connect(main.toggle_bookmark_visibility)
    main.act_toggle_bookmark_marks.toggled.connect(main.set_bookmark_marks_visible)

    main._playlist_refresh_timer = QtCore.QTimer(main)
    main._playlist_refresh_timer.setSingleShot(True)
    main._playlist_refresh_timer.timeout.connect(main._flush_playlist_refresh)
    main._playlist_refresh_pending = False
    main._playlist_refresh_force = False
    main._playlist_duration_cache = {}
    main._playlist_duration_pending = {}
    main.update_playlist(force=True)
    main._apply_ui_language()


def initialize_main_window_runtime(main) -> None:
    main._last_master_before_mute = 100
    main.normal_geometry = None
    main.master_volume = 80
    main.master_muted = False
    main._fullscreen_ui_mode = None
    main._fullscreen_ui_tile = None
    main._fullscreen_hover_pending_pos = None
    main._fullscreen_hover_timer = QtCore.QTimer(main)
    main._fullscreen_hover_timer.setSingleShot(True)
    main._fullscreen_hover_timer.setInterval(40)
    main._fullscreen_hover_timer.timeout.connect(main._flush_fullscreen_hover)
    main._tile_drag = None
    main._tile_drag_cursor = False
    main._tile_drag_preview = None
    main._refresh_recent_profiles_menu()


def initialize_main_window_post_restore(main) -> None:
    main.cursor_hide_timer = QtCore.QTimer(main)
    main.cursor_hide_timer.setSingleShot(True)
    main.cursor_hide_timer.setInterval(1500)
    main.cursor_hide_timer.timeout.connect(main._hide_cursor)
    QtWidgets.QApplication.instance().installEventFilter(main)

    main.auto_save_timer = QtCore.QTimer(main)
    main.auto_save_timer.setInterval(15000)
    main.auto_save_timer.timeout.connect(lambda: main.save_config(auto=True))
    main.auto_save_timer.start()
    print("Settings auto-save timer started (light checkpoint mode).")
