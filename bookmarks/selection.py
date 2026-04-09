from typing import Any, Dict, Optional

from PyQt6 import QtWidgets

from .shared import BOOKMARK_ROLE, NODE_CATEGORY_ROLE, NODE_PATH_ROLE, NODE_TYPE_ROLE, bookmark_matches_path, normalize_category, normalize_path
from .state import refresh_bookmark_marks
from .tree_nodes import collect_bookmark_ids_from_item, iter_bookmark_items


def selected_bookmark_ids(main) -> list[str]:
    widget = getattr(main, "bookmark_widget", None)
    if widget is None:
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for item in widget.selectedItems():
        for bookmark_id in collect_bookmark_ids_from_item(item):
            if bookmark_id in seen:
                continue
            seen.add(bookmark_id)
            ids.append(bookmark_id)
    return ids


def selected_category_names(main) -> list[str]:
    return _selected_values(main, "category", NODE_CATEGORY_ROLE)


def selected_direct_bookmark_ids(main) -> list[str]:
    return _selected_values(main, "bookmark", BOOKMARK_ROLE)


def _selected_values(main, node_type: str, role: int) -> list[str]:
    widget = getattr(main, "bookmark_widget", None)
    if widget is None:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in widget.selectedItems():
        if item.data(0, NODE_TYPE_ROLE) != node_type:
            continue
        value = str(item.data(0, role) or "").strip()
        if not value:
            continue
        normalized = normalize_category(value) if node_type == "category" else value
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def selected_file_nodes(main) -> list[tuple[str, str]]:
    widget = getattr(main, "bookmark_widget", None)
    if widget is None:
        return []
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in widget.selectedItems():
        if item.data(0, NODE_TYPE_ROLE) != "file":
            continue
        path = str(item.data(0, NODE_PATH_ROLE) or "")
        category = normalize_category(item.data(0, NODE_CATEGORY_ROLE))
        key = (path, category)
        if not path or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def selected_bookmark_positions_for_path(main, path: Optional[str]) -> list[int]:
    if not path:
        return []
    selected_ids = set(selected_bookmark_ids(main))
    if not selected_ids:
        return []
    positions = {
        int(entry.get("position_ms", 0))
        for entry in getattr(main, "bookmarks", []) or []
        if str(entry.get("id", "")) in selected_ids and bookmark_matches_path(entry, path)
    }
    return sorted(positions)


def select_bookmarks_for_path_positions(main, path: Optional[str], positions_ms, *, toggle: bool = False) -> bool:
    widget = getattr(main, "bookmark_widget", None)
    if widget is None or not path:
        return False
    wanted_positions = {max(0, int(ms)) for ms in (positions_ms or [])}
    if not wanted_positions:
        widget.clearSelection()
        refresh_bookmark_marks(main)
        return False
    matching_ids = _matching_bookmark_ids(main, normalize_path(path), wanted_positions)
    if not matching_ids:
        return False
    _apply_bookmark_selection(widget, _selection_target_ids(main, matching_ids, toggle))
    refresh_bookmark_marks(main)
    return True


def _matching_bookmark_ids(main, normalized_path: str, wanted_positions: set[int]) -> set[str]:
    return {
        str(entry.get("id", ""))
        for entry in getattr(main, "bookmarks", []) or []
        if bookmark_matches_path(entry, normalized_path) and int(entry.get("position_ms", 0)) in wanted_positions
    }


def _selection_target_ids(main, matching_ids: set[str], toggle: bool) -> set[str]:
    current_ids = set(selected_bookmark_ids(main))
    if toggle and matching_ids.issubset(current_ids):
        return current_ids - matching_ids
    return set(matching_ids)


def _apply_bookmark_selection(widget: QtWidgets.QTreeWidget, target_ids: set[str]):
    widget.blockSignals(True)
    try:
        widget.clearSelection()
        current_item = None
        for item in iter_bookmark_items(widget):
            bookmark_id = item.data(0, BOOKMARK_ROLE)
            if isinstance(bookmark_id, str) and bookmark_id in target_ids:
                item.setSelected(True)
                current_item = item
                _expand_item_parents(item)
        if current_item is not None:
            widget.setCurrentItem(current_item)
    finally:
        widget.blockSignals(False)


def _expand_item_parents(item: QtWidgets.QTreeWidgetItem):
    parent = item.parent()
    while parent is not None:
        parent.setExpanded(True)
        parent = parent.parent()


def bookmark_by_id(main, bookmark_id: str) -> Optional[Dict[str, Any]]:
    for entry in getattr(main, "bookmarks", []) or []:
        if str(entry.get("id", "")) == bookmark_id:
            return entry
    return None


def selected_leaf_ids(main) -> set[str]:
    return set(selected_bookmark_ids(main))


def selected_entries(main) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for bookmark_id in selected_bookmark_ids(main):
        if bookmark_id in seen:
            continue
        seen.add(bookmark_id)
        entry = bookmark_by_id(main, bookmark_id)
        if entry is not None:
            out.append(entry)
    return out
