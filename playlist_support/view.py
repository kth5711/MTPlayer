import os

from PyQt6 import QtCore, QtWidgets

from i18n import tr
from .tile_state import apply_playlist_tile_header_style
from video_tile_helpers.playlist_bookmarks import (
    playlist_entry_bookmark_cursor,
    playlist_entry_bookmark_positions,
)


def update_playlist(main, force: bool = False):
    if _playlist_refresh_blocked(main, force):
        return
    tree = main.playlist_widget
    main._playlist_refresh_pending = False
    main._playlist_refresh_force = False
    state = _capture_tree_state(tree)
    tree.setUpdatesEnabled(False)
    try:
        main._apply_playlist_sort()
        tree.clear()
        _populate_playlist_tree(main, tree, main._playlist_filter_text(), state)
    finally:
        tree.setUpdatesEnabled(True)


def _playlist_refresh_blocked(main, force: bool) -> bool:
    if force:
        return False
    dock = getattr(main, "playlist_dock", None)
    try:
        if dock is not None and not dock.isVisible():
            main._playlist_refresh_pending = True
            main._playlist_refresh_force = False
            return True
    except Exception:
        pass
    return False


def _populate_playlist_tree(main, tree, query: str, state):
    for tile_index, tile in enumerate(main.canvas.tiles):
        payload = _tile_row_payload(main, tile_index, tile, query)
        if payload is None:
            continue
        top_item, child_payloads = payload
        tree.addTopLevelItem(top_item)
        for row_index, path, duration_text in child_payloads:
            _add_playlist_leaf(main, top_item, tile, tile_index, row_index, path, duration_text, state)
        _restore_item_state(top_item, _playlist_item_key(top_item), state, default_expanded=True)
    _restore_tree_current_item(tree, state)


def _tile_row_payload(main, tile_index: int, tile, query: str):
    playlist = getattr(tile, "playlist", [])
    current_index = _tile_current_index(tile)
    is_playing = main._playlist_tile_is_playing(tile)
    child_rows, tile_match = _tile_child_rows(main, playlist, query, tile_index)
    if query and not child_rows and not tile_match:
        return None
    child_rows = child_rows if (query and not tile_match) else list(enumerate(playlist))
    child_payloads, total_duration_ms, total_duration_known = _child_duration_payloads(main, child_rows)
    top_item = _build_tile_item(main, tile_index, total_duration_ms, total_duration_known)
    top_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, {"type": "tile", "tile_idx": tile_index})
    top_item.setTextAlignment(1, int(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter))
    top_item._playlist_current_index = current_index  # type: ignore[attr-defined]
    top_item._playlist_is_playing = is_playing  # type: ignore[attr-defined]
    apply_playlist_tile_header_style(
        main,
        top_item,
        has_current=(current_index >= 0),
        is_playing=is_playing,
    )
    return top_item, child_payloads


def _tile_current_index(tile) -> int:
    try:
        return int(getattr(tile, "current_index", -1))
    except Exception:
        return -1


def _tile_child_rows(main, playlist, query: str, tile_index: int):
    filtered = [(row, path) for row, path in enumerate(playlist) if main._playlist_path_matches_filter(path, query)]
    tile_label = tr(main, "타일 {index}", index=tile_index + 1)
    tile_match = bool(query and query in tile_label.lower())
    return filtered, tile_match


def _child_duration_payloads(main, child_rows):
    total_duration_ms = 0
    total_duration_known = False
    payloads = []
    for row_index, path in child_rows:
        duration_ms, duration_text = main._playlist_duration_info(path)
        if duration_ms is not None:
            total_duration_ms += duration_ms
            total_duration_known = True
        payloads.append((row_index, path, duration_text))
    return payloads, total_duration_ms, total_duration_known


def _build_tile_item(main, tile_index: int, total_duration_ms: int, total_duration_known: bool):
    duration_text = tr(main, "합계 {duration}", duration=main._format_duration_ms(total_duration_ms)) if total_duration_known else ""
    return QtWidgets.QTreeWidgetItem([tr(main, "타일 {index}", index=tile_index + 1), duration_text])


def _add_playlist_leaf(main, top_item, tile, tile_index: int, row_index: int, path: str, duration_text: str, state):
    leaf = QtWidgets.QTreeWidgetItem([os.path.basename(path), duration_text])
    leaf.setToolTip(0, path)
    leaf.setData(0, QtCore.Qt.ItemDataRole.UserRole, {"type": "file", "tile_idx": tile_index, "row": row_index, "path": path})
    leaf.setTextAlignment(1, int(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter))
    main._apply_playlist_current_item_style(
        leaf,
        is_current=(row_index == getattr(top_item, "_playlist_current_index", -1)),
        is_playing=bool(getattr(top_item, "_playlist_is_playing", False)),
    )
    top_item.addChild(leaf)
    _add_bookmark_children(
        main,
        leaf,
        tile,
        tile_index,
        row_index,
        path,
        getattr(top_item, "_playlist_current_index", -1),
        bool(getattr(top_item, "_playlist_is_playing", False)),
        state,
    )


def _add_bookmark_children(main, leaf, tile, tile_index: int, row_index: int, path: str, current_index: int, is_playing: bool, state):
    positions = playlist_entry_bookmark_positions(tile, row_index)
    cursor = playlist_entry_bookmark_cursor(tile, row_index)
    for subindex, position_ms in enumerate(positions):
        child = QtWidgets.QTreeWidgetItem(
            [tr(main, "북마크 {time}", time=main._format_duration_ms(position_ms)), main._format_duration_ms(position_ms)]
        )
        child.setData(
            0,
            QtCore.Qt.ItemDataRole.UserRole,
            {"type": "bookmark", "tile_idx": tile_index, "row": row_index, "path": path, "bookmark_subindex": subindex, "position_ms": position_ms},
        )
        child.setTextAlignment(1, int(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter))
        main._apply_playlist_current_item_style(
            child,
            is_current=(row_index == current_index and subindex == int(cursor or 0)),
            is_playing=is_playing,
        )
        leaf.addChild(child)
        _restore_item_state(child, _playlist_item_key(child), state)
    if positions:
        _restore_item_state(leaf, _playlist_item_key(leaf), state, default_expanded=True)


def _capture_tree_state(tree):
    if tree is None or int(tree.topLevelItemCount()) == 0:
        return {
            "has_prior_state": False,
            "expanded": set(),
            "selected": set(),
            "current": None,
        }
    expanded = set()
    selected = set()
    current = _playlist_item_key(tree.currentItem())
    for item in _iter_tree_items(tree):
        key = _playlist_item_key(item)
        if key is None:
            continue
        if item.isExpanded():
            expanded.add(key)
        if item.isSelected():
            selected.add(key)
    return {
        "has_prior_state": True,
        "expanded": expanded,
        "selected": selected,
        "current": current,
    }


def _iter_tree_items(tree):
    for index in range(int(tree.topLevelItemCount())):
        top = tree.topLevelItem(index)
        if top is None:
            continue
        yield from _iter_item_with_children(top)


def _iter_item_with_children(item):
    yield item
    for index in range(int(item.childCount())):
        child = item.child(index)
        if child is None:
            continue
        yield from _iter_item_with_children(child)


def _playlist_item_key(item):
    if item is None:
        return None
    meta = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
    if not isinstance(meta, dict):
        return None
    kind = str(meta.get("type") or "")
    if kind == "tile":
        return ("tile", int(meta.get("tile_idx", -1)))
    if kind == "file":
        return ("file", int(meta.get("tile_idx", -1)), int(meta.get("row", -1)), str(meta.get("path", "")))
    if kind == "bookmark":
        return (
            "bookmark",
            int(meta.get("tile_idx", -1)),
            int(meta.get("row", -1)),
            int(meta.get("bookmark_subindex", -1)),
            int(meta.get("position_ms", -1)),
        )
    return None


def _restore_item_state(item, key, state, *, default_expanded: bool = False):
    if key is None or item is None:
        return
    selected_keys = state.get("selected", set())
    if key in selected_keys:
        item.setSelected(True)
    has_prior_state = bool(state.get("has_prior_state"))
    if default_expanded:
        expanded_keys = state.get("expanded", set())
        item.setExpanded((key in expanded_keys) if has_prior_state else True)


def _restore_tree_current_item(tree, state) -> None:
    current_key = state.get("current")
    if current_key is None:
        return
    for item in _iter_tree_items(tree):
        if _playlist_item_key(item) != current_key:
            continue
        tree.setCurrentItem(item)
        return
