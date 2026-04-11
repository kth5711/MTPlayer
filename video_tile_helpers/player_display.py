from typing import Optional

from PyQt6 import QtCore, QtGui
import vlc

from i18n import tr


def rebuild_player_for_transform_mode(tile):
    media_path, position, playing = _capture_player_state(tile)
    target_instance, owned_instance = _target_instance_for_mode(tile)
    tile._release_mediaplayer(release_owned_instance=True)
    tile._owned_vlc_instance = owned_instance
    tile._last_bound_video_target = None
    tile._create_mediaplayer(target_instance)
    _force_bind_video_target(tile)
    if _reload_media_after_rebuild(tile, media_path, position, playing):
        return
    _refresh_rebuilt_player_ui(tile)


def _capture_player_state(tile):
    media_path = tile._current_playlist_path()
    position = _safe_player_position(tile)
    playing = _safe_player_playing(tile)
    return media_path, position, playing


def _safe_player_position(tile):
    try:
        pos = tile.mediaplayer.get_position()
        if isinstance(pos, float) and 0 <= pos <= 1:
            return pos
    except Exception:
        pass
    return None


def _safe_player_playing(tile) -> bool:
    try:
        return bool(tile.mediaplayer.is_playing())
    except Exception:
        return False


def _target_instance_for_mode(tile):
    mode = getattr(tile, "transform_mode", "none")
    if mode == "none":
        return tile.shared_vlc_instance, None
    owned_instance = vlc.Instance(*tile._transform_instance_args(mode))
    return owned_instance, owned_instance


def _force_bind_video_target(tile):
    try:
        if getattr(tile, "video_widget", None) is not None:
            tile.bind_hwnd(force=True)
    except Exception:
        pass


def _reload_media_after_rebuild(tile, media_path, position, playing) -> bool:
    if not media_path:
        return False
    if tile.set_media(media_path):
        tile._restore_session_media_state(position, playing)
        return True
    return False


def _refresh_rebuilt_player_ui(tile):
    try:
        tile.refresh_track_menus()
    except Exception:
        pass
    tile._update_play_button()


def display_geometry_spec(tile) -> Optional[str]:
    try:
        size = tile.video_widget.size()
        width = max(1, int(size.width()))
        height = max(1, int(size.height()))
        return f"{width}:{height}"
    except Exception:
        return None


def rebuild_display_mode_menu(tile):
    _rebuild_mode_menu(
        tile,
        menu=getattr(tile, "display_mode_menu", None),
        modes=tile.DISPLAY_MODES,
        current_mode=getattr(tile, "display_mode", "fit"),
        labels=tile.DISPLAY_MODE_LABELS,
        tooltips=tile.DISPLAY_MODE_TOOLTIPS,
        handler=tile.set_display_mode,
    )


def rebuild_transform_mode_menu(tile):
    _rebuild_mode_menu(
        tile,
        menu=getattr(tile, "transform_mode_menu", None),
        modes=tile.TRANSFORM_MODES,
        current_mode=getattr(tile, "transform_mode", "none"),
        labels=tile.TRANSFORM_MODE_LABELS,
        tooltips=tile.TRANSFORM_MODE_TOOLTIPS,
        handler=tile.set_transform_mode,
    )


def _rebuild_mode_menu(tile, *, menu, modes, current_mode, labels, tooltips, handler):
    if menu is None:
        return
    menu.clear()
    group = QtGui.QActionGroup(menu)
    group.setExclusive(True)
    for mode in modes:
        action = menu.addAction(tr(tile, labels.get(mode, mode)))
        action.setCheckable(True)
        action.setChecked(mode == current_mode)
        action.setToolTip(tr(tile, tooltips.get(mode, "")))
        action.triggered.connect(lambda _checked=False, m=mode: handler(m))
        group.addAction(action)


def update_display_mode_button(tile):
    _update_mode_button(
        tile,
        button=getattr(tile, "btn_display_mode", None),
        mode=getattr(tile, "display_mode", "fit"),
        labels=tile.DISPLAY_MODE_LABELS,
        tooltips=tile.DISPLAY_MODE_TOOLTIPS,
        template="영상 표시 모드: {label}\n{tooltip}\n클릭: 다음 모드, 화살표: 직접 선택",
        fallback="fit",
    )


def update_transform_mode_button(tile):
    _update_mode_button(
        tile,
        button=getattr(tile, "btn_transform_mode", None),
        mode=getattr(tile, "transform_mode", "none"),
        labels=tile.TRANSFORM_MODE_LABELS,
        tooltips=tile.TRANSFORM_MODE_TOOLTIPS,
        template="영상 방향: {label}\n{tooltip}\n클릭: 시계 방향 90도 회전\n화살표: 직접 선택",
        fallback="none",
    )


def _update_mode_button(tile, *, button, mode, labels, tooltips, template, fallback):
    if button is None:
        return
    label = tr(tile, labels.get(mode, labels[fallback]))
    tooltip = tr(tile, tooltips.get(mode, ""))
    button.setText(label)
    button.setToolTip(tr(tile, template, label=label, tooltip=tooltip).strip())


def cycle_display_mode(tile):
    tile.set_display_mode(_next_mode(getattr(tile, "display_mode", "fit"), tile.DISPLAY_MODES))


def cycle_transform_mode(tile):
    tile.set_transform_mode(_next_mode(getattr(tile, "transform_mode", "none"), tile.ROTATION_TOGGLE_MODES))


def _next_mode(current_mode, modes):
    try:
        idx = modes.index(current_mode)
    except ValueError:
        idx = 0
    return modes[(idx + 1) % len(modes)]


def set_display_mode(tile, mode: str):
    tile.display_mode = mode if mode in tile.DISPLAY_MODES else "fit"
    tile._rebuild_display_mode_menu()
    tile._update_display_mode_button()
    tile._apply_display_mode()
    _show_mode_status_overlay(tile, getattr(tile, "display_mode", "fit"), tile.DISPLAY_MODE_LABELS)


def set_transform_mode(tile, mode: str):
    mode = mode if mode in tile.TRANSFORM_MODES else "none"
    if mode == getattr(tile, "transform_mode", "none"):
        tile._rebuild_transform_mode_menu()
        tile._update_transform_mode_button()
        return
    tile.transform_mode = mode
    tile._rebuild_transform_mode_menu()
    tile._update_transform_mode_button()
    if tile.is_static_image():
        tile._refresh_image_display()
        _show_mode_status_overlay(tile, getattr(tile, "transform_mode", "none"), tile.TRANSFORM_MODE_LABELS)
        return
    tile._rebuild_player_for_transform_mode()
    _show_mode_status_overlay(tile, getattr(tile, "transform_mode", "none"), tile.TRANSFORM_MODE_LABELS)


def _show_mode_status_overlay(tile, mode: str, labels: dict[str, str]) -> None:
    show_overlay = getattr(tile, "_show_status_overlay", None)
    if not callable(show_overlay):
        return
    label = tr(tile, labels.get(mode, str(mode or "")))
    show_overlay(label)


def apply_display_mode(tile):
    if tile.is_static_image():
        tile._refresh_image_display()
        return
    player = getattr(tile, "mediaplayer", None)
    if player is None:
        return
    geometry = tile._display_geometry_spec()
    _reset_video_geometry(player)
    _apply_display_mode_to_player(player, getattr(tile, "display_mode", "fit"), geometry)


def _reset_video_geometry(player):
    _set_player_value(player.video_set_crop_geometry, None, "")
    _set_player_value(player.video_set_aspect_ratio, None, "")
    try:
        player.video_set_scale(0.0)
    except Exception:
        pass


def _set_player_value(setter, primary, fallback):
    try:
        setter(primary)
    except Exception:
        try:
            setter(fallback)
        except Exception:
            pass


def _apply_display_mode_to_player(player, mode: str, geometry: Optional[str]):
    if mode == "stretch" and geometry:
        _call_player_setter(player.video_set_aspect_ratio, geometry)
    elif mode == "crop" and geometry:
        _call_player_setter(player.video_set_crop_geometry, geometry)
    elif mode == "original":
        _call_player_setter(player.video_set_scale, 1.0)


def _call_player_setter(setter, value):
    try:
        setter(value)
    except Exception:
        pass

