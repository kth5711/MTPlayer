import os
from typing import List, Optional

from PyQt6 import QtCore, QtWidgets

from i18n import tr
from .ui import OpacitySliderDialog, OverlayGlobalApplyDialog, OverlayLayerOpacityDialog


def overlay_dialog_parent(tile):
    canvas = tile._canvas_host()
    if canvas is not None and hasattr(canvas, "detached_window_for_tile"):
        try:
            window = canvas.detached_window_for_tile(tile)
        except Exception:
            window = None
        if window is not None:
            return window
    return tile._main_window() or tile.window()


def dialog_available_rect_for_video(tile) -> QtCore.QRect:
    screen = QtWidgets.QApplication.screenAt(tile._video_widget_global_rect().center())
    if screen is None:
        screen = QtWidgets.QApplication.primaryScreen()
    return screen.availableGeometry() if screen is not None else QtCore.QRect()


def clamp_dialog_point(point: QtCore.QPoint, size: QtCore.QSize, available: QtCore.QRect) -> QtCore.QPoint:
    if not available.isValid():
        return QtCore.QPoint(point)
    max_x = available.right() - max(0, size.width()) + 1
    max_y = available.bottom() - max(0, size.height()) + 1
    return QtCore.QPoint(max(available.left(), min(point.x(), max_x)), max(available.top(), min(point.y(), max_y)))


def position_dialog_outside_video(tile, dialog: QtWidgets.QDialog):
    video_rect = tile._video_widget_global_rect()
    available = dialog_available_rect_for_video(tile)
    dialog.ensurePolished()
    dialog.adjustSize()
    size = dialog.sizeHint().expandedTo(dialog.minimumSizeHint())
    margin = 14
    candidates = (
        QtCore.QPoint(video_rect.right() + margin, video_rect.top()),
        QtCore.QPoint(video_rect.left() - size.width() - margin, video_rect.top()),
        QtCore.QPoint(video_rect.left(), video_rect.bottom() + margin),
        QtCore.QPoint(video_rect.left(), video_rect.top() - size.height() - margin),
    )
    for point in candidates:
        rect = QtCore.QRect(point, size)
        if (not available.isValid() or available.contains(rect)) and not rect.intersects(video_rect):
            dialog.move(point)
            return
    dialog.move(clamp_dialog_point(QtCore.QPoint(video_rect.right() + margin, video_rect.top()), size, available))


def prepare_overlay_dialog(tile, dialog: QtWidgets.QDialog):
    parent = overlay_dialog_parent(tile)
    if getattr(parent, "overlay_active", lambda: False)() or bool(getattr(parent, "_always_on_top", False)):
        dialog.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
    position_dialog_outside_video(tile, dialog)


def open_opacity_slider_dialog(tile, *, title: str, current_percent: int, on_change):
    dialog = OpacitySliderDialog(
        title=title,
        current_percent=max(10, min(100, int(current_percent))),
        on_change=on_change,
        parent=overlay_dialog_parent(tile),
    )
    prepare_overlay_dialog(tile, dialog)
    dialog.exec()


def open_tile_window_opacity_dialog_from_context(tile):
    canvas = tile._canvas_host()
    if canvas is None or not hasattr(canvas, "set_tile_window_opacity"):
        return
    current_percent = tile._tile_window_opacity_percent()
    try:
        if not bool(canvas.is_detached(tile)):
            canvas.set_tile_window_opacity(tile, current_percent / 100.0)
    except Exception:
        pass
    open_opacity_slider_dialog(
        tile,
        title=tr(tile, "타일 투명도"),
        current_percent=tile._tile_window_opacity_percent(),
        on_change=lambda opacity: tile._set_tile_window_opacity_from_context(opacity),
    )


def _tile_title(owner, target_tile) -> str:
    title = str(getattr(getattr(target_tile, "title", None), "toolTip", lambda: "")() or "").strip()
    if title:
        return title
    return str(getattr(getattr(target_tile, "title", None), "text", lambda: tr(owner, "타일"))() or tr(owner, "타일"))


def open_overlay_opacity_dialog_from_context(tile, *, target_tile=None):
    target = target_tile if target_tile is not None else tile
    open_opacity_slider_dialog(
        tile,
        title=tr(tile, "오버레이 투명도 - {title}", title=_tile_title(tile, target)),
        current_percent=tile._overlay_opacity_percent(target),
        on_change=lambda opacity, target_ref=target: tile._set_overlay_opacity_from_context(opacity, tile=target_ref),
    )


def overlay_layer_dialog_label(tile, target_tile, order: int, total: int) -> str:
    position = tr(tile, "맨 아래") if order <= 0 else (
        tr(tile, "맨 위") if order >= max(0, total - 1) else tr(tile, "{index}번째", index=order + 1)
    )
    suffix = tr(tile, " (현재)") if target_tile is tile else ""
    return tr(
        tile,
        "{index}. {position} 레이어 - {title}{suffix}",
        index=order + 1,
        position=position,
        title=_tile_title(tile, target_tile),
        suffix=suffix,
    )


def overlay_layer_opacity_items(tile) -> List[tuple]:
    group_tiles = tile._overlay_group_tiles()
    total = len(group_tiles)
    return [
        (target_tile, overlay_layer_dialog_label(tile, target_tile, order, total), tile._overlay_opacity_percent(target_tile))
        for order, target_tile in enumerate(group_tiles)
    ]


def open_overlay_layer_opacity_dialog_from_context(tile):
    items = overlay_layer_opacity_items(tile)
    if not items:
        return
    dialog = OverlayLayerOpacityDialog(
        title=tr(tile, "오버레이 레이어 투명도"),
        layer_items=[(label, percent) for _tile, label, percent in items],
        current_top_percent=tile._overlay_global_apply_percent(),
        on_layer_change=lambda index, opacity, overlay_items=items: tile._set_overlay_opacity_from_context(opacity, tile=overlay_items[index][0]),
        on_preset_change=tile._apply_overlay_opacity_preset_from_context,
        parent=overlay_dialog_parent(tile),
    )
    prepare_overlay_dialog(tile, dialog)
    dialog.exec()


def open_overlay_global_apply_dialog_from_context(tile):
    canvas = tile._canvas_host()
    if canvas is None or not hasattr(canvas, "set_overlay_global_apply_percent"):
        return
    dialog = OverlayGlobalApplyDialog(
        title=tr(tile, "오버레이 전체 적용"),
        current_value=tile._overlay_global_apply_percent(),
        on_change=tile._set_overlay_global_apply_from_context,
        parent=overlay_dialog_parent(tile),
    )
    prepare_overlay_dialog(tile, dialog)
    dialog.exec()


def create_overlay_stack_from_context(tile):
    canvas = tile._canvas_host()
    if canvas is None or not hasattr(canvas, "overlay_stack_tiles"):
        return
    targets = tile._overlay_stack_targets()
    if len(targets) < 2:
        QtWidgets.QMessageBox.information(tile, tr(tile, "오버레이"), tr(tile, "오버레이하려면 미디어가 열린 타일을 2개 이상 선택하세요."))
        return
    if not canvas.overlay_stack_tiles(tile, tiles=targets):
        QtWidgets.QMessageBox.warning(tile, tr(tile, "오버레이"), tr(tile, "선택 타일 오버레이 스택 생성에 실패했습니다."))


def clear_overlay_stack_from_context(tile):
    canvas = tile._canvas_host()
    if canvas is None or not hasattr(canvas, "clear_overlay_stack"):
        return
    canvas.clear_overlay_stack(tile)


def _show_mainwin_status(tile, text: str):
    mainwin = tile._main_window()
    if mainwin is None or not hasattr(mainwin, "statusBar"):
        return
    try:
        mainwin.statusBar().showMessage(text, 2500)
    except Exception:
        pass


def _save_mainwin_config(tile):
    mainwin = tile._main_window()
    if mainwin is None or not hasattr(mainwin, "save_config"):
        return
    try:
        mainwin.save_config()
    except Exception:
        pass


def set_overlay_global_apply_from_context(tile, value: int):
    canvas = tile._canvas_host()
    if canvas is None or not hasattr(canvas, "set_overlay_global_apply_percent"):
        return
    canvas.set_overlay_global_apply_percent(value, apply_existing=True)
    _show_mainwin_status(tile, tr(tile, "오버레이 전체 적용: {value}%", value=int(value)))
    _save_mainwin_config(tile)


def apply_overlay_opacity_preset_from_context(tile, preset_name: str, top_percent: int):
    set_overlay_global_apply_from_context(tile, top_percent)
    _show_mainwin_status(
        tile,
        tr(tile, "오버레이 프리셋: {preset_name} ({top_percent}%)", preset_name=preset_name, top_percent=int(top_percent)),
    )


def set_overlay_audio_mode_from_context(tile, mode: str):
    canvas = tile._canvas_host()
    if canvas is None or not hasattr(canvas, "set_overlay_audio_mode_for_tile"):
        return
    canvas.set_overlay_audio_mode_for_tile(tile, mode)
    label = tr(tile, "기존 상태 유지") if str(mode) == "preserve" else tr(tile, "leader만")
    _show_mainwin_status(tile, tr(tile, "오버레이 오디오 모드: {label}", label=label))
    _save_mainwin_config(tile)


def set_tile_window_opacity_from_context(tile, opacity: float):
    canvas = tile._canvas_host()
    if canvas is None or not hasattr(canvas, "set_tile_window_opacity"):
        return
    canvas.set_tile_window_opacity(tile, opacity)
