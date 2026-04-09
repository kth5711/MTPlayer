from PyQt6 import QtCore, QtGui, QtWidgets

from i18n import tr
from .context_menu_media import add_export_actions, add_repeat_mode_menu, add_track_menus
from .overlay_dialog import PRESET_TOP_PERCENTS
from .view_mode_menu import add_display_mode_menu, add_transform_mode_menu


def _context_menu_window(tile):
    canvas = getattr(tile, "_canvas_host", lambda: None)()
    if canvas is not None and hasattr(canvas, "detached_window_for_tile"):
        try:
            window = canvas.detached_window_for_tile(tile)
        except Exception:
            window = None
        if window is not None: return window
    try:
        return tile.window()
    except Exception:
        return tile


def _prepare_context_menu_window(window):
    if window is None: return
    apply_focus_once = getattr(window, "_apply_focus_once", None)
    if callable(apply_focus_once):
        try:
            apply_focus_once()
            return
        except Exception:
            pass
    restore_focus = getattr(window, "restore_focus", None)
    if callable(restore_focus):
        try:
            restore_focus()
            return
        except Exception:
            pass
    try:
        window.raise_()
    except Exception:
        pass
    try:
        window.activateWindow()
    except Exception:
        pass


def bind_tile_context_menu(tile, widget):
    if widget is None:
        return
    widget.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
    widget.customContextMenuRequested.connect(
        lambda pos, w=widget: tile._show_tile_context_menu(w.mapToGlobal(pos))
    )


def finalize_tile_context_menu(tile, menu):
    if getattr(tile, "_active_context_menu", None) is menu: tile._active_context_menu = None
    parent_window = getattr(menu, "_overlay_parent_window", None)
    if parent_window is not None and getattr(parent_window, "overlay_active", lambda: False)():
        request_restack = getattr(parent_window, "_request_overlay_restack", None)
        if callable(request_restack):
            try:
                request_restack(delays=(0, 80))
            except Exception:
                pass
    try:
        menu.deleteLater()
    except Exception:
        pass


def exec_tile_context_menu(tile, menu, global_pos: QtCore.QPoint):
    if getattr(tile, "_active_context_menu", None) is not menu:
        try:
            menu.deleteLater()
        except Exception:
            pass
        return
    try:
        parent_window = getattr(menu, "_overlay_parent_window", None)
        if parent_window is not None: _prepare_context_menu_window(parent_window)
        menu.exec(global_pos)
    except Exception:
        finalize_tile_context_menu(tile, menu)


def _tile_opacity_label(tile, canvas) -> str:
    return tr(tile, "개별타일투명도(분리)")


def _fit_media_label(tile, canvas) -> str:
    label = tr(tile, "영상 크기 맞춤")
    try:
        if not bool(canvas.is_detached(tile)):
            label = tr(tile, "영상 크기 맞춤 (선택 시 분리창)")
    except Exception:
        pass
    return label


def _overlay_stack_label(tile, overlay_targets, overlay_target_mode: str) -> str:
    if len(overlay_targets) < 2:
        return tr(tile, "오버레이 스택 만들기 (미디어 2개 이상 필요)")
    if overlay_target_mode == "selected":
        return tr(tile, "현재 + 선택 타일 오버레이 스택 만들기 ({count}개)", count=len(overlay_targets))
    return tr(tile, "열린 미디어 타일 전체 오버레이 스택 만들기 ({count}개)", count=len(overlay_targets))


def _overlay_layer_dialog_label(tile) -> str:
    return tr(tile, "레이어 투명도 조절... ({count}개)", count=len(tile._overlay_group_tiles()))


def _zoom_menu_label(tile) -> str:
    try:
        current = int(getattr(tile, "zoom_percent", 100) or 100)
    except Exception:
        current = 100
    return tr(tile, "확대: {percent}%", percent=current)


def _add_compare_sync_menu(tile, menu):
    submenu = menu.addMenu(tr(tile, "비교/동기화"))
    submenu.addAction(tr(tile, "타임코드 이동..."), tile._jump_to_timecode_from_context)
    submenu.addAction(tr(tile, "이 타일 기준 전체 동기화"), tile._sync_other_tiles_to_this_timecode)
    submenu.addAction(tr(tile, "포커스 검토 창"), tile._open_focus_review_from_context)


def _add_zoom_menu(tile, menu):
    submenu = menu.addMenu(_zoom_menu_label(tile))
    group = QtGui.QActionGroup(submenu)
    group.setExclusive(True)
    current = int(getattr(tile, "zoom_percent", 100) or 100)
    for percent in getattr(tile, "ZOOM_PERCENTS", (100, 125, 150, 200)):
        action = submenu.addAction(f"{int(percent)}%")
        action.setCheckable(True)
        action.setChecked(int(percent) == current)
        action.triggered.connect(lambda _checked=False, p=int(percent): tile.set_zoom_percent(p))
        group.addAction(action)


def _add_overlay_audio_mode_menu(tile, overlay_menu):
    audio_menu = overlay_menu.addMenu(tr(tile, "오디오 모드"))
    current_mode = str(tile._overlay_audio_mode() or "leader")
    for label, mode in ((tr(tile, "leader만"), "leader"), (tr(tile, "기존 상태 유지"), "preserve")):
        action = audio_menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(current_mode == mode)
        action.triggered.connect(lambda _checked=False, m=mode: tile._set_overlay_audio_mode_from_context(m))


def _add_overlay_preset_menu(tile, overlay_menu):
    preset_menu = overlay_menu.addMenu(
        tr(tile, "스택 전체 적용 프리셋 ({percent}%)", percent=tile._overlay_global_apply_percent())
    )
    current_value = int(tile._overlay_global_apply_percent())
    for label, top_percent in PRESET_TOP_PERCENTS:
        translated_label = tr(tile, label)
        action = preset_menu.addAction(f"{translated_label} ({top_percent}%)")
        action.setCheckable(True)
        action.setChecked(current_value == int(top_percent))
        action.triggered.connect(
            lambda _checked=False, name=label, value=top_percent: tile._apply_overlay_opacity_preset_from_context(name, value)
        )


def _add_overlay_menu(tile, menu, canvas):
    menu.addAction(_tile_opacity_label(tile, canvas), tile._open_tile_window_opacity_dialog_from_context)
    act_fit_media_size = menu.addAction(_fit_media_label(tile, canvas), tile._fit_media_size_from_context)
    if tile.current_media_pixel_size() is None:
        act_fit_media_size.setEnabled(False)
    try:
        overlay_group_id = str(canvas.overlay_group_id_for_tile(tile) or "").strip()
    except Exception:
        overlay_group_id = ""
    try:
        overlay_targets, overlay_target_mode = tile._overlay_stack_targets_info()
    except Exception:
        overlay_targets, overlay_target_mode = [], "none"
    overlay_menu = menu.addMenu(tr(tile, "오버레이"))
    act_overlay_stack = overlay_menu.addAction(_overlay_stack_label(tile, overlay_targets, overlay_target_mode))
    act_overlay_stack.triggered.connect(tile._create_overlay_stack_from_context)
    _add_overlay_preset_menu(tile, overlay_menu)
    if overlay_group_id:
        overlay_menu.addSeparator()
        overlay_menu.addAction(tr(tile, "오버레이 스택 해제"), tile._clear_overlay_stack_from_context)
        _add_overlay_audio_mode_menu(tile, overlay_menu)
        overlay_menu.addAction(_overlay_layer_dialog_label(tile), tile._open_overlay_layer_opacity_dialog_from_context)


def show_tile_context_menu(tile, global_pos: QtCore.QPoint):
    current_menu = getattr(tile, "_active_context_menu", None)
    if current_menu is not None:
        try:
            current_menu.close()
        except Exception:
            pass
    menu_parent = _context_menu_window(tile) or tile
    menu = QtWidgets.QMenu(menu_parent)
    menu.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
    menu._overlay_parent_window = menu_parent
    if getattr(menu_parent, "overlay_active", lambda: False)() or bool(getattr(menu_parent, "_always_on_top", False)): menu.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
    tile._active_context_menu = menu
    menu.aboutToHide.connect(lambda m=menu: tile._finalize_tile_context_menu(m))
    menu.addAction(tr(tile, "파일 추가"), tile._add_files); menu.addAction(tr(tile, "폴더 추가"), tile._add_folder)
    menu.addAction(tr(tile, "URL/스트림 열기..."), tile._open_url_stream_from_context); menu.addAction(tr(tile, "북마크 추가"), tile._add_bookmark)
    menu.addSeparator()
    _add_compare_sync_menu(tile, menu)
    menu.addSeparator()
    add_repeat_mode_menu(tile, menu); add_display_mode_menu(tile, menu)
    add_transform_mode_menu(tile, menu)
    _add_zoom_menu(tile, menu)
    canvas = tile._canvas_host()
    if canvas is not None:
        menu.addSeparator()
        _add_overlay_menu(tile, menu, canvas)
    menu.addSeparator()
    add_track_menus(tile, menu)
    menu.addSeparator()
    action = menu.addAction(tr(tile, "자막 생성"), tile._generate_subtitle_from_context)
    action.setEnabled(not bool(getattr(tile, "_export_worker_busy", False)))
    translate_action = menu.addAction(tr(tile, "자막 번역"), tile._translate_subtitle_from_context)
    translate_action.setEnabled(not bool(getattr(tile, "_export_worker_busy", False)))
    menu.addAction(tr(tile, "자막 열기"), tile._open_subtitle_file)
    add_export_actions(tile, menu)
    popup_pos = QtCore.QPoint(global_pos); _prepare_context_menu_window(menu_parent)
    QtCore.QTimer.singleShot(0, lambda m=menu, p=popup_pos: tile._exec_tile_context_menu(m, p))
