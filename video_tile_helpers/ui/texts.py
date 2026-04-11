from typing import TYPE_CHECKING

from PyQt6 import QtCore, QtGui, QtWidgets

from scene_analysis_support import scene_analysis_button_tooltip
from i18n import tr
from video_tile_helpers.init_core import refresh_feedback_overlay_styles
from video_tile_helpers.selection import refresh_selection_visuals

if TYPE_CHECKING:
    from video_tile import VideoTile


def refresh_video_tile_ui_texts(tile: "VideoTile"):
    has_media = bool(getattr(tile, "playlist", None))
    has_media = has_media or bool(getattr(tile, "is_static_image", lambda: False)())
    _refresh_labels(tile, has_media)
    _refresh_actions(tile)
    _refresh_mode_buttons(tile)
    _refresh_theme_styles(tile)


def _refresh_labels(tile: "VideoTile", has_media: bool):
    if not has_media and hasattr(tile, "title"):
        tile.title.setText(tr(tile, "(열기)"))
        if hasattr(tile, "_fit_open_title_hitbox"):
            tile._fit_open_title_hitbox()
    if hasattr(tile, "title"):
        tooltip = tile.title.toolTip() or ""
        if not has_media:
            tooltip = tr(tile, "이 타일에 미디어를 열려면 클릭하세요")
        tile.title.setToolTip(tooltip)
    _set_text(tile, "btn_scenes", "씬분석")
    _set_text(tile, "btn_audio_tracks", "오디오")
    _set_text(tile, "btn_subtitle_tracks", "자막")
    _set_text(tile, "_open_stub", "열기")
    _set_label_text(tile, "lbl_loop_status", "구간 반복: OFF")
    if hasattr(tile, "lbl_rate"):
        tile.lbl_rate.setText(tr(tile, "배속: {rate:.1f}x", rate=getattr(tile, "playback_rate", 1.0)))


def _refresh_actions(tile: "VideoTile"):
    _set_dynamic_tooltip(tile, "btn_scenes", scene_analysis_button_tooltip(tile))
    _set_tooltip(tile, "btn_bookmark", "현재 위치를 북마크에 추가")
    _set_tooltip(tile, "btn_export_menu", "내보내기 메뉴")
    _set_tooltip(tile, "btn_close", "현재 프레임 스크린샷 저장")
    _set_tooltip(tile, "btn_frameset", "현재 구간 프레임셋 저장")
    _set_tooltip(tile, "sld_vol", "이 타일의 볼륨 (0~120)")
    _set_tooltip(tile, "btn_volume_toggle", "클릭: 음소거, 좌우 드래그: 볼륨 조절")
    _set_tooltip(tile, "btn_repeat_mode", "클릭할 때마다 반복 안 함 -> 현재 영상 1개 반복 -> 플레이리스트 반복으로 변경")
    _set_action_text(tile, "action_export_gif", "GIF")
    _set_action_text(tile, "action_export_clip", "Clip")
    _set_action_text(tile, "action_export_screenshot", "스크린샷")
    _set_action_text(tile, "action_export_frameset", "프레임셋")
    if hasattr(tile, "action_mute_selected"):
        tile.action_mute_selected.setText(tr(tile, "선택 타일 음소거/해제"))


def _refresh_mode_buttons(tile: "VideoTile"):
    try:
        tile._rebuild_display_mode_menu()
        tile._update_display_mode_button()
        tile._rebuild_transform_mode_menu()
        tile._update_transform_mode_button()
    except Exception:
        pass
    try:
        tile._update_repeat_button()
    except Exception:
        pass


def _refresh_theme_styles(tile: "VideoTile"):
    _refresh_open_title_style(tile)
    _refresh_volume_toggle_icon(tile)
    refresh_selection_visuals(tile)
    _refresh_selection_widgets(tile)
    refresh_feedback_overlay_styles(tile)


def _refresh_open_title_style(tile: "VideoTile"):
    label = getattr(tile, "title", None)
    if label is None:
        return
    palette = label.palette()
    base_is_dark = _palette_is_dark(palette)
    normal = "#d7dee7" if base_is_dark else "#405261"
    hover = "#ffffff" if base_is_dark else "#11181f"
    label.setStyleSheet(
        "QLabel { color: %s; }\n"
        "QLabel:hover { text-decoration: underline; color: %s; }" % (normal, hover)
    )


def _refresh_volume_toggle_icon(tile: "VideoTile"):
    button = getattr(tile, "btn_volume_toggle", None)
    if button is None:
        return
    button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
    button.setFixedSize(30, 24)
    button.setIconSize(QtCore.QSize(16, 16))
    button.setContentsMargins(0, 0, 0, 0)
    button.setStyleSheet("QToolButton { padding: 4px 0 0 0; }")
    icon = tile.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaVolume)
    if icon.isNull():
        button.setIcon(QtGui.QIcon())
        button.setText("🔉")
        return
    button.setText("")
    button.setIcon(icon)


def _refresh_selection_widgets(tile: "VideoTile"):
    for widget in (
        getattr(tile, "lbl_selected", None),
        getattr(tile, "control_bar", None),
        getattr(tile, "controls_container", None),
        tile,
    ):
        if widget is None:
            continue
        try:
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)
        except Exception:
            pass
        try:
            widget.update()
        except Exception:
            pass


def _palette_is_dark(palette: QtGui.QPalette) -> bool:
    try:
        return int(palette.color(QtGui.QPalette.ColorRole.Window).lightness()) < 140
    except Exception:
        return True


def _set_text(tile: "VideoTile", name: str, text: str):
    widget = getattr(tile, name, None)
    if widget is not None:
        widget.setText(tr(tile, text))


def _set_label_text(tile: "VideoTile", name: str, text: str):
    label = getattr(tile, name, None)
    if label is not None:
        label.setText(tr(tile, text))


def _set_tooltip(tile: "VideoTile", name: str, text: str):
    widget = getattr(tile, name, None)
    if widget is not None:
        widget.setToolTip(tr(tile, text))


def _set_dynamic_tooltip(tile: "VideoTile", name: str, text: str):
    widget = getattr(tile, name, None)
    if widget is not None:
        widget.setToolTip(str(text or ""))


def _set_action_text(tile: "VideoTile", name: str, text: str):
    action = getattr(tile, name, None)
    if action is not None:
        action.setText(tr(tile, text))
