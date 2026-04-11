from typing import TYPE_CHECKING

from PyQt6 import QtCore, QtGui, QtWidgets

from scene_analysis_support import open_scene_dialog, scene_analysis_button_tooltip
from i18n import tr
from video_tile_helpers.ui import BookmarkSlider, ClickableLabel
from .preview import init_seek_preview_state as init_seek_preview_state_impl
from .selection import refresh_selection_visuals

if TYPE_CHECKING:
    from video_tile import VideoTile


def init_video_tile_ui(tile: "VideoTile"):
    _init_title_buttons(tile)
    _init_track_controls(tile)
    _init_playback_controls(tile)
    _init_layout(tile)
    _connect_tile_signals(tile)
    _init_runtime_helpers(tile)


def _init_title_buttons(tile: "VideoTile"):
    tile.title = ClickableLabel(tr(tile, "(열기)"))
    tile.title.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
    tile.title.setToolTip(tr(tile, "이 타일에 미디어를 열려면 클릭하세요"))
    tile.title.setMinimumWidth(30)
    tile.title.setMaximumWidth(100)
    tile.title.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
    tile._fit_open_title_hitbox()
    _apply_initial_open_title_style(tile)
    tile.title.clicked.connect(tile._on_add_clicked)
    tile.btn_scenes = QtWidgets.QPushButton(tr(tile, "씬분석")); tile.btn_scenes.setToolTip(scene_analysis_button_tooltip(tile))
    tile.btn_scenes.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
    tile.btn_scenes.setMinimumHeight(24)
    tile.btn_scenes.setStyleSheet("QPushButton { padding: 0 6px; min-width: 0px; }")
    tile.btn_bookmark = QtWidgets.QPushButton("★")
    tile.btn_bookmark.setToolTip(tr(tile, "현재 위치를 북마크에 추가"))
    _configure_symbol_button(tile.btn_bookmark, font_size=13)
    tile.btn_play = QtWidgets.QPushButton("")
    _configure_symbol_button(tile.btn_play, font_size=13)
    tile.btn_stop = QtWidgets.QPushButton("■")
    _configure_symbol_button(tile.btn_stop, font_size=12)
    tile.btn_export_menu = _popup_tool_button(tile, "✂")
    tile.btn_export_menu.setToolTip(tr(tile, "내보내기 메뉴"))
    _configure_symbol_tool_button(tile.btn_export_menu, font_size=16)
    tile.btn_export_menu.setStyleSheet("QToolButton::menu-indicator { image: none; width: 0px; }")
    tile.export_menu = QtWidgets.QMenu(tile.btn_export_menu)
    tile.btn_export_menu.setMenu(tile.export_menu)
    tile.action_export_gif = tile.export_menu.addAction("GIF")
    tile.action_export_clip = tile.export_menu.addAction("Clip")
    tile.action_export_screenshot = tile.export_menu.addAction(tr(tile, "스크린샷"))
    tile.action_export_frameset = tile.export_menu.addAction(tr(tile, "프레임셋"))
    tile.btn_close = QtWidgets.QPushButton("📸")
    tile.btn_close.setToolTip(tr(tile, "현재 프레임 스크린샷 저장"))
    tile.btn_close.setFixedWidth(28)
    tile.btn_frameset = QtWidgets.QPushButton("FS")
    tile.btn_frameset.setToolTip(tr(tile, "현재 구간 프레임셋 저장"))
    tile.btn_frameset.setFixedWidth(28)
    tile.btn_frameset.setVisible(False)
    tile._open_stub = QtWidgets.QPushButton(tr(tile, "열기"), tile)
    tile._open_stub.setObjectName("btn_open_stub")
    tile._open_stub.setVisible(False)
    tile._open_stub.setEnabled(False)
    tile._open_stub.setFixedSize(0, 0)
    tile.btn_open = tile._open_stub


def _init_track_controls(tile: "VideoTile"):
    tile.sld_vol = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    tile.sld_vol.setRange(0, 120)
    tile.sld_vol.setSingleStep(5)
    tile.sld_vol.setPageStep(5)
    tile.sld_vol.setValue(tile.tile_volume)
    tile.sld_vol.setFixedWidth(110)
    tile.sld_vol.setVisible(False)
    tile.sld_vol.setToolTip(tr(tile, "이 타일의 볼륨 (0~120)"))
    tile.btn_volume_toggle = QtWidgets.QToolButton(tile)
    _configure_volume_toggle_button(tile)
    tile.btn_volume_toggle.setAutoRaise(True)
    tile.btn_volume_toggle.setCheckable(False)
    tile.btn_volume_toggle.setToolTip(tr(tile, "클릭: 음소거, 좌우 드래그: 볼륨 조절"))
    _init_track_menus(tile)
    _init_view_mode_buttons(tile)
    try:
        tile.sld_vol.valueChanged.disconnect()
    except Exception:
        pass
    tile.sld_vol.valueChanged.connect(tile._on_tile_volume_changed)


def _init_track_menus(tile: "VideoTile"):
    tile.btn_audio_tracks = _popup_tool_button(tile, tr(tile, "오디오"))
    tile.audio_menu = QtWidgets.QMenu(tile.btn_audio_tracks)
    tile.btn_audio_tracks.setMenu(tile.audio_menu)
    tile.audio_menu.aboutToShow.connect(tile.refresh_track_menus)
    tile.btn_audio_tracks.setVisible(False)
    tile.btn_subtitle_tracks = _popup_tool_button(tile, tr(tile, "자막"))
    tile.subtitle_menu = QtWidgets.QMenu(tile.btn_subtitle_tracks)
    tile.btn_subtitle_tracks.setMenu(tile.subtitle_menu)
    tile.subtitle_menu.aboutToShow.connect(tile.refresh_track_menus)
    tile.btn_subtitle_tracks.setVisible(False)


def _popup_tool_button(tile: "VideoTile", text: str):
    button = QtWidgets.QToolButton(tile)
    button.setText(text)
    button.setAutoRaise(True)
    button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
    return button


def _configure_symbol_button(button: QtWidgets.QPushButton, *, font_size: int) -> None:
    button.setFixedSize(30, 24)
    font = button.font()
    font.setPointSize(font_size)
    font.setBold(True)
    button.setFont(font)


def _configure_symbol_tool_button(button: QtWidgets.QToolButton, *, font_size: int) -> None:
    button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
    button.setFixedSize(30, 24)
    font = button.font()
    font.setPointSize(font_size)
    font.setBold(True)
    button.setFont(font)
    button.setContentsMargins(0, 0, 0, 0)


def _configure_volume_toggle_button(tile: "VideoTile"):
    button = tile.btn_volume_toggle
    button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
    button.setFixedSize(30, 24)
    button.setIconSize(QtCore.QSize(16, 16))
    button.setContentsMargins(0, 0, 0, 0)
    button.setStyleSheet("QToolButton { padding: 4px 0 0 0; }")
    icon = tile.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaVolume)
    if icon.isNull():
        button.setText("🔉")
        return
    button.setText("")
    button.setIcon(icon)


def _apply_initial_open_title_style(tile: "VideoTile"):
    window_lightness = 0
    try:
        window_lightness = int(tile.palette().color(QtGui.QPalette.ColorRole.Window).lightness())
    except Exception:
        window_lightness = 0
    dark_palette = window_lightness < 140
    normal = "#d7dee7" if dark_palette else "#405261"
    hover = "#ffffff" if dark_palette else "#11181f"
    tile.title.setStyleSheet(
        "QLabel { color: %s; }\nQLabel:hover { text-decoration: underline; color: %s; }" % (normal, hover)
    )


def _init_view_mode_buttons(tile: "VideoTile"):
    tile.btn_display_mode = QtWidgets.QToolButton(tile)
    tile.btn_display_mode.setAutoRaise(True)
    tile.btn_display_mode.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup)
    tile.btn_display_mode.setMinimumWidth(54)
    tile.display_mode_menu = QtWidgets.QMenu(tile.btn_display_mode)
    tile.btn_display_mode.setMenu(tile.display_mode_menu)
    tile._rebuild_display_mode_menu(); tile._update_display_mode_button(); tile.btn_display_mode.setVisible(False)
    tile.btn_transform_mode = QtWidgets.QToolButton(tile)
    tile.btn_transform_mode.setAutoRaise(True)
    tile.btn_transform_mode.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup)
    tile.btn_transform_mode.setMinimumWidth(62)
    tile.transform_mode_menu = QtWidgets.QMenu(tile.btn_transform_mode)
    tile.btn_transform_mode.setMenu(tile.transform_mode_menu)
    tile._rebuild_transform_mode_menu(); tile._update_transform_mode_button(); tile.btn_transform_mode.setVisible(False)


def _init_playback_controls(tile: "VideoTile"):
    tile.sld_pos = BookmarkSlider(QtCore.Qt.Orientation.Horizontal, tile)
    tile.sld_pos.setRange(0, 100000)
    tile.sld_pos.setMouseTracking(True)
    tile.sld_pos.installEventFilter(tile)
    tile.btn_A = QtWidgets.QPushButton("A")
    tile._fit_ab_loop_button_hitbox()
    tile.btn_B = QtWidgets.QPushButton("B", tile)
    tile.btn_B.setVisible(False)
    tile.btn_B.setEnabled(False)
    tile.btn_repeat_mode = QtWidgets.QPushButton(tr(tile, "반복: 끔"))
    tile.btn_repeat_mode.setToolTip(tr(tile, "클릭할 때마다 반복 안 함 -> 현재 영상 1개 반복 -> 플레이리스트 반복으로 변경"))
    tile.btn_repeat_mode.setMinimumWidth(88)
    tile.btn_repeat_mode.setVisible(False)
    tile.lbl_selected = QtWidgets.QLabel("", tile)
    tile.lbl_selected.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    tile.lbl_selected.setFixedSize(24, 20)
    tile.lbl_selected.setToolTip(tr(tile, "타일 선택 상태"))
    refresh_selection_visuals(tile)
    tile.btn_gif = QtWidgets.QPushButton("GIF")
    tile.btn_clip = QtWidgets.QPushButton("Clip")
    tile.lbl_loop_status = QtWidgets.QLabel(tr(tile, "구간 반복: OFF"), tile)
    tile.lbl_loop_status.setVisible(False)
    tile.lbl_time = QtWidgets.QLabel("00:00 / 00:00")
    tile.lbl_time.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    tile._fit_time_label_hitbox()
    tile.lbl_rate = QtWidgets.QLabel(tr(tile, "배속: {rate:.1f}x", rate=tile.playback_rate))
    tile.lbl_rate.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter); tile.lbl_rate.setMinimumWidth(68)
    tile.lbl_rate.setVisible(False)


def _init_layout(tile: "VideoTile"):
    tile.control_bar = QtWidgets.QWidget(tile)
    tile.control_bar.setMinimumSize(0, 0)
    tile.control_bar.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed)
    _populate_control_bar(tile)
    tile.controls_container = QtWidgets.QWidget(tile)
    tile.controls_container.setObjectName("tile_controls_container")
    tile.controls_container.setMinimumSize(0, 0)
    tile.controls_container.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed)
    controls_layout = QtWidgets.QVBoxLayout(tile.controls_container)
    controls_layout.setContentsMargins(0, 0, 0, 0)
    controls_layout.setSpacing(0)
    tile.sld_pos.setMinimumWidth(0)
    tile.sld_pos.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed)
    controls_layout.addWidget(tile.sld_pos)
    controls_layout.addWidget(tile.control_bar)
    layout = QtWidgets.QVBoxLayout(tile)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(tile.video_widget, 1)
    layout.addWidget(tile.controls_container)


def _populate_control_bar(tile: "VideoTile"):
    ctrl = QtWidgets.QHBoxLayout(tile.control_bar)
    ctrl.setContentsMargins(0, 0, 0, 0)
    ctrl.setSpacing(4)
    grouped_widgets = (
        tile.title, tile.lbl_time, None,
        tile.btn_bookmark, tile.btn_play, tile.btn_stop, tile.btn_volume_toggle, tile.sld_vol, tile.btn_A, None,
        tile.btn_display_mode, tile.btn_transform_mode,
    )
    for widget in grouped_widgets:
        if widget is None:
            ctrl.addSpacing(12)
            continue
        ctrl.addWidget(widget, 0)
    ctrl.addStretch(1)
    ctrl.addWidget(tile.btn_scenes, 0)
    ctrl.addWidget(tile.btn_export_menu, 0)
    ctrl.addWidget(tile.lbl_selected, 0)


def _connect_tile_signals(tile: "VideoTile"):
    tile._update_add_button()
    tile.btn_scenes.clicked.connect(lambda: open_scene_dialog(tile))
    tile.btn_bookmark.clicked.connect(tile._add_bookmark)
    tile.btn_play.clicked.connect(tile.toggle_play)
    tile.btn_stop.clicked.connect(tile.stop)
    tile.btn_close.clicked.connect(tile.capture_screenshot)
    tile.btn_frameset.clicked.connect(tile.save_frame_set)
    tile.btn_display_mode.clicked.connect(tile.cycle_display_mode)
    tile.btn_transform_mode.clicked.connect(tile.cycle_transform_mode)
    tile.sld_vol.sliderReleased.connect(tile.snap_volume_to_step)
    tile.sld_vol.sliderMoved.connect(tile.snap_volume_preview)
    tile.sld_pos.sliderReleased.connect(tile.set_position)
    tile.sld_pos.sliderMoved.connect(tile._on_seek_slider_moved)
    tile.btn_A.clicked.connect(tile.cycle_ab_loop)
    tile.btn_repeat_mode.clicked.connect(tile.cycle_repeat_mode)
    tile.btn_gif.clicked.connect(tile.export_gif)
    tile.btn_clip.clicked.connect(tile.export_clip)
    tile.action_export_gif.triggered.connect(tile.export_gif)
    tile.action_export_clip.triggered.connect(tile.export_clip)
    tile.action_export_screenshot.triggered.connect(tile.capture_screenshot)
    tile.action_export_frameset.triggered.connect(tile.save_frame_set)
    tile.export_menu.aboutToShow.connect(lambda: _refresh_export_menu_actions(tile))


def _init_runtime_helpers(tile: "VideoTile"):
    tile.timer = QtCore.QTimer(tile)
    tile.timer.setInterval(500)
    tile.timer.timeout.connect(tile.update_position)
    tile.timer.start()
    init_seek_preview_state_impl(tile)
    tile.action_mute_selected = QtGui.QAction(tr(tile, "선택 타일 음소거/해제"), tile)
    tile.action_mute_selected.triggered.connect(tile._trigger_mute_selected_tiles)
    tile.addAction(tile.action_mute_selected)
    for widget in (tile, tile.title, tile.sld_pos, tile.control_bar, tile.controls_container):
        tile._bind_tile_context_menu(widget)
    tile.title.installEventFilter(tile)
    tile.btn_volume_toggle.installEventFilter(tile)
    tile._update_play_button()
    tile._update_ab_controls()
    tile._update_repeat_button()
    tile._apply_controls_visibility()
    _refresh_export_menu_actions(tile)
    tile._bookmark_marks_state = None
    tile._last_bookmark_snap_ms = None


def _refresh_export_menu_actions(tile: "VideoTile"):
    try:
        current_path = tile._current_playlist_path() or tile._current_media_path()
    except Exception:
        current_path = None
    has_media = bool(current_path)
    is_image = bool(getattr(tile, "is_static_image", lambda: False)())
    export_busy = bool(getattr(tile, "_export_worker_busy", False))
    action_screenshot = getattr(tile, "action_export_screenshot", None)
    if action_screenshot is not None:
        action_screenshot.setEnabled(has_media)
    action_frameset = getattr(tile, "action_export_frameset", None)
    if action_frameset is not None:
        action_frameset.setEnabled(has_media and not is_image)
    action_gif = getattr(tile, "action_export_gif", None)
    if action_gif is not None:
        action_gif.setEnabled(has_media and not is_image and not export_busy)
    action_clip = getattr(tile, "action_export_clip", None)
    if action_clip is not None:
        action_clip.setEnabled(has_media and not is_image and not export_busy)
