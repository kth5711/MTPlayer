import uuid
from typing import TYPE_CHECKING, List, Optional

from PyQt6 import QtCore

if TYPE_CHECKING:
    from canvas import Canvas
    from video_tile import VideoTile

DEFAULT_OVERLAY_AUDIO_MODE = "leader"


def normalize_overlay_audio_mode(value: str) -> str:
    return "preserve" if str(value or "").strip().lower() == "preserve" else DEFAULT_OVERLAY_AUDIO_MODE


def overlay_group_id_for_tile(canvas: "Canvas", tile: "VideoTile") -> str:
    window = canvas.detached_window_for_tile(tile)
    if window is None:
        return ""
    return window.overlay_group_id()


def overlay_group_tiles(canvas: "Canvas", group_id: str) -> List["VideoTile"]:
    normalized = str(group_id or "").strip()
    if not normalized:
        return []
    grouped: List["VideoTile"] = []
    for tile, window in list(canvas.detached_windows.items()):
        if window is None or window.overlay_group_id() != normalized:
            continue
        grouped.append(tile)
    return sorted(
        grouped,
        key=lambda tile: (
            canvas.detached_window_for_tile(tile).overlay_order()
            if canvas.detached_window_for_tile(tile) is not None else 0
        ),
    )


def overlay_default_opacity(canvas: "Canvas", order: int, total_count: int) -> float:
    total = max(1, int(total_count))
    normalized_order = max(0, min(max(0, total - 1), int(order)))
    if total <= 1 or normalized_order <= 0:
        return 1.0
    top_fraction = max(0.01, min(1.0, float(canvas.overlay_global_apply_percent()) / 100.0))
    progress = float(normalized_order) / float(max(1, total - 1))
    return max(0.01, min(1.0, float(top_fraction ** progress)))


def overlay_audio_mode_for_tile(canvas: "Canvas", tile: "VideoTile") -> str:
    window = canvas.detached_window_for_tile(tile)
    if window is None or not window.overlay_active():
        return DEFAULT_OVERLAY_AUDIO_MODE
    return normalize_overlay_audio_mode(getattr(window, "overlay_audio_mode", lambda: DEFAULT_OVERLAY_AUDIO_MODE)())


def reapply_overlay_group_opacity_rule(canvas: "Canvas", group_id: str):
    normalized = str(group_id or "").strip()
    if not normalized:
        return
    group_tiles = overlay_group_tiles(canvas, normalized)
    total_count = len(group_tiles)
    for tile in group_tiles:
        window = canvas.detached_window_for_tile(tile)
        if window is None or not window.overlay_active():
            continue
        window.set_overlay_state(
            normalized,
            order=window.overlay_order(),
            leader=window.overlay_is_leader(),
            opacity=overlay_default_opacity(canvas, window.overlay_order(), total_count),
            emit_sync=False,
        )
    canvas._restack_overlay_group(normalized)


def _overlay_ordered_media_tiles(
    canvas: "Canvas",
    leader_tile: "VideoTile",
    candidates: List["VideoTile"],
) -> List["VideoTile"]:
    ordered: List["VideoTile"] = []
    seen: set["VideoTile"] = set()
    for tile in [leader_tile] + list(candidates):
        if tile in seen or tile not in canvas.tiles:
            continue
        has_media = bool(getattr(tile, "playlist", None)) or bool(getattr(tile, "is_static_image", lambda: False)())
        if not has_media:
            continue
        ordered.append(tile)
        seen.add(tile)
    return ordered


def _clear_touched_overlay_groups(canvas: "Canvas", ordered: List["VideoTile"]):
    touched_groups = {overlay_group_id_for_tile(canvas, tile) for tile in ordered}
    for group_id in sorted(group_id for group_id in touched_groups if group_id):
        clear_overlay_stack_for_group(canvas, group_id, restore_focus=False)


def _detach_overlay_followers(
    canvas: "Canvas",
    ordered: List["VideoTile"],
    anchor_geometry: QtCore.QRect,
):
    for tile in ordered[1:]:
        if not canvas.is_detached(tile):
            canvas.detach_tile(tile, restore_focus=False)
        follower_window = canvas.detached_window_for_tile(tile)
        if follower_window is not None:
            follower_window.setGeometry(anchor_geometry)


def _apply_overlay_group_state(
    canvas: "Canvas",
    leader_tile: "VideoTile",
    ordered: List["VideoTile"],
    group_id: str,
    anchor_geometry: QtCore.QRect,
    was_detached_before_overlay: dict["VideoTile", bool],
):
    total_count = len(ordered)
    for order, tile in enumerate(ordered):
        window = canvas.detached_window_for_tile(tile)
        if window is None:
            continue
        if bool(was_detached_before_overlay.get(tile, False)):
            try:
                window._overlay_restore_window_opacity = float(window.window_opacity_value())
            except Exception:
                try:
                    window._overlay_restore_window_opacity = float(getattr(tile, "detached_window_opacity", 1.0))
                except Exception:
                    window._overlay_restore_window_opacity = 1.0
        else:
            window._overlay_restore_window_opacity = 1.0
            try:
                tile.detached_window_opacity = 1.0
            except Exception:
                pass
        if order > 0:
            window._overlay_restore_tile_muted = bool(getattr(tile, "tile_muted", False))
            if not bool(getattr(tile, "tile_muted", False)):
                tile.set_tile_muted(True)
        else:
            window._overlay_restore_tile_muted = None
        window.set_overlay_state(
            group_id,
            order=order,
            leader=(tile is leader_tile),
            opacity=overlay_default_opacity(canvas, order, total_count),
            emit_sync=False,
        )
        if tile is not leader_tile:
            window.setGeometry(anchor_geometry)


def _apply_overlay_group_audio_mode(canvas: "Canvas", group_id: str, mode: str):
    normalized_mode = normalize_overlay_audio_mode(mode)
    for order, tile in enumerate(overlay_group_tiles(canvas, group_id)):
        window = canvas.detached_window_for_tile(tile)
        if window is None:
            continue
        window.set_overlay_audio_mode(normalized_mode)
        if order <= 0:
            continue
        restore_muted = window._overlay_restore_tile_muted
        if normalized_mode == "preserve":
            if restore_muted is not None:
                tile.set_tile_muted(bool(restore_muted))
            continue
        if not bool(getattr(tile, "tile_muted", False)):
            tile.set_tile_muted(True)


def overlay_stack_tiles(
    canvas: "Canvas",
    leader_tile: "VideoTile",
    tiles: Optional[List["VideoTile"]] = None,
) -> bool:
    ordered = _overlay_ordered_media_tiles(canvas, leader_tile, list(tiles or canvas.get_selected_tiles()))
    if len(ordered) < 2:
        return False
    was_detached_before_overlay = {tile: bool(canvas.is_detached(tile)) for tile in ordered}
    _clear_touched_overlay_groups(canvas, ordered)

    if not canvas.is_detached(leader_tile):
        canvas.detach_tile(leader_tile, restore_focus=False)
    leader_window = canvas.detached_window_for_tile(leader_tile)
    if leader_window is None:
        return False
    anchor_geometry = QtCore.QRect(leader_window.geometry())
    _detach_overlay_followers(canvas, ordered, anchor_geometry)

    group_id = uuid.uuid4().hex
    _apply_overlay_group_state(
        canvas,
        leader_tile,
        ordered,
        group_id,
        anchor_geometry,
        was_detached_before_overlay,
    )
    _apply_overlay_group_audio_mode(canvas, group_id, DEFAULT_OVERLAY_AUDIO_MODE)
    canvas._sync_overlay_group_geometry(leader_tile, anchor_geometry)
    canvas._restack_overlay_group(group_id)
    leader_window.restore_focus()
    canvas._restack_overlay_group(group_id)
    return True


def set_overlay_opacity_for_tile(canvas: "Canvas", tile: "VideoTile", opacity: float):
    window = canvas.detached_window_for_tile(tile)
    if window is None or not window.overlay_active():
        return
    window.set_overlay_state(
        window.overlay_group_id(),
        order=window.overlay_order(),
        leader=window.overlay_is_leader(),
        opacity=opacity,
        emit_sync=False,
    )
    canvas._restack_overlay_group(window.overlay_group_id())


def clear_overlay_stack(canvas: "Canvas", tile: "VideoTile"):
    group_id = overlay_group_id_for_tile(canvas, tile)
    if not group_id:
        return
    group_tiles = list(overlay_group_tiles(canvas, group_id))
    if not group_tiles:
        return
    canvas._restore_main_window_if_minimized()
    for group_tile in group_tiles:
        if canvas.is_detached(group_tile):
            canvas.redock_tile(group_tile)


def set_overlay_audio_mode_for_tile(canvas: "Canvas", tile: "VideoTile", mode: str):
    group_id = overlay_group_id_for_tile(canvas, tile)
    if not group_id:
        return
    _apply_overlay_group_audio_mode(canvas, group_id, mode)


def clear_overlay_stack_for_group(canvas: "Canvas", group_id: str, *, restore_focus: bool = True):
    focus_window = None
    for tile in overlay_group_tiles(canvas, group_id):
        window = canvas.detached_window_for_tile(tile)
        if window is None: continue
        if focus_window is None: focus_window = window
        restore_muted = window._overlay_restore_tile_muted
        restore_opacity = window._overlay_restore_window_opacity
        window._overlay_restore_tile_muted = None
        window._overlay_restore_window_opacity = None
        window.clear_overlay_state(restore_focus=False)
        if restore_opacity is not None:
            try:
                tile.detached_window_opacity = float(restore_opacity)
            except Exception:
                pass
            window.set_window_opacity_value(float(restore_opacity))
        if restore_muted is not None: tile.set_tile_muted(bool(restore_muted))
    if restore_focus and focus_window is not None:
        focus_window.restore_focus()
