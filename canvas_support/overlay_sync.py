import logging
from typing import TYPE_CHECKING

from PyQt6 import QtCore

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from canvas import Canvas
    from video_tile import VideoTile


def sync_overlay_group_geometry(canvas: "Canvas", leader_tile: "VideoTile", geometry: QtCore.QRect):
    group_id = canvas.overlay_group_id_for_tile(leader_tile)
    if not group_id:
        return
    leader_window = canvas.detached_window_for_tile(leader_tile)
    if leader_window is None or not leader_window.overlay_is_leader():
        return
    canvas._sync_overlay_group_window_mode(leader_tile)
    target_geometry = QtCore.QRect(geometry)
    leader_fullscreen = bool(
        leader_window.isFullScreen()
        or bool(leader_window.windowState() & QtCore.Qt.WindowState.WindowFullScreen)
    )
    for tile in canvas.overlay_group_tiles(group_id):
        if tile is leader_tile:
            continue
        window = canvas.detached_window_for_tile(tile)
        if window is None or leader_fullscreen:
            continue
        try:
            if window.geometry() != target_geometry:
                window._set_geometry_from_overlay_sync(target_geometry)
        except RuntimeError:
            logger.debug("overlay follower geometry sync skipped", exc_info=True)


def _sync_follower_window_mode(window, leader_fullscreen: bool, target_geometry: QtCore.QRect):
    try:
        follower_fullscreen = bool(
            window.isFullScreen()
            or bool(window.windowState() & QtCore.Qt.WindowState.WindowFullScreen)
        )
    except RuntimeError:
        logger.debug("overlay follower fullscreen probe skipped", exc_info=True)
        follower_fullscreen = False
    try:
        if leader_fullscreen and not follower_fullscreen:
            window._run_overlay_sync_action(window.showFullScreen)
        elif (not leader_fullscreen) and follower_fullscreen:
            window._run_overlay_sync_action(window.showNormal)
        if not leader_fullscreen and window.geometry() != target_geometry:
            window._set_geometry_from_overlay_sync(target_geometry)
    except RuntimeError:
        logger.debug("overlay follower window-mode sync skipped", exc_info=True)


def sync_overlay_group_window_mode(canvas: "Canvas", leader_tile: "VideoTile"):
    group_id = canvas.overlay_group_id_for_tile(leader_tile)
    if not group_id:
        return
    leader_window = canvas.detached_window_for_tile(leader_tile)
    if leader_window is None or not leader_window.overlay_is_leader():
        return
    leader_fullscreen = bool(
        leader_window.isFullScreen()
        or bool(leader_window.windowState() & QtCore.Qt.WindowState.WindowFullScreen)
    )
    target_geometry = QtCore.QRect(leader_window.geometry())
    for tile in canvas.overlay_group_tiles(group_id):
        if tile is leader_tile:
            continue
        window = canvas.detached_window_for_tile(tile)
        if window is None:
            continue
        _sync_follower_window_mode(window, leader_fullscreen, target_geometry)


def restack_overlay_group(canvas: "Canvas", group_id: str):
    tiles = canvas.overlay_group_tiles(group_id)
    if len(tiles) <= 1:
        return
    ordered_windows = [canvas.detached_window_for_tile(tile) for tile in tiles]
    ordered_windows = [window for window in ordered_windows if window is not None]
    if not ordered_windows:
        return
    leader_windows = [window for window in ordered_windows if window.overlay_is_leader()]
    if leader_windows:
        try:
            leader_windows[0].raise_()
        except RuntimeError:
            logger.debug("overlay leader restack raise skipped", exc_info=True)
    for window in ordered_windows:
        if window.overlay_is_leader():
            continue
        try:
            window.raise_()
        except RuntimeError:
            logger.debug("overlay follower restack raise skipped", exc_info=True)


def _overlay_leader_tile(canvas: "Canvas", group_id: str):
    return next(
        (
            candidate
            for candidate in canvas.overlay_group_tiles(group_id)
            if (
                canvas.detached_window_for_tile(candidate) is not None
                and canvas.detached_window_for_tile(candidate).overlay_is_leader()
            )
        ),
        None,
    )


def on_overlay_geometry_changed(canvas: "Canvas", tile: "VideoTile", geometry: QtCore.QRect):
    group_id = canvas.overlay_group_id_for_tile(tile)
    if not group_id:
        return
    window = canvas.detached_window_for_tile(tile)
    if window is None:
        return
    if window.overlay_is_leader():
        canvas._sync_overlay_group_geometry(tile, geometry)
        return
    leader_tile = _overlay_leader_tile(canvas, group_id)
    if leader_tile is None:
        return
    leader_window = canvas.detached_window_for_tile(leader_tile)
    if leader_window is None:
        return
    target_geometry = QtCore.QRect(leader_window.geometry())
    try:
        if window.geometry() != target_geometry:
            window._set_geometry_from_overlay_sync(target_geometry)
    except RuntimeError:
        logger.debug("overlay follower snap-back skipped", exc_info=True)
    canvas._restack_overlay_group(group_id)


def on_overlay_restack_requested(canvas: "Canvas", tile: "VideoTile"):
    group_id = canvas.overlay_group_id_for_tile(tile)
    if not group_id:
        return
    window = canvas.detached_window_for_tile(tile)
    if window is not None and window.overlay_is_leader():
        canvas._sync_overlay_group_window_mode(tile)
    canvas._restack_overlay_group(group_id)
