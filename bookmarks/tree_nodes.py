from typing import Iterable, Optional

from PyQt6 import QtWidgets

from .shared import BOOKMARK_ROLE, NODE_CATEGORY_ROLE, NODE_KEY_ROLE, NODE_TYPE_ROLE, normalize_category
from .state import refresh_bookmark_marks


def iter_tree_items(parent) -> Iterable[QtWidgets.QTreeWidgetItem]:
    for idx in range(parent.childCount()):
        item = parent.child(idx)
        yield item
        yield from iter_tree_items(item)


def iter_bookmark_items(widget: QtWidgets.QTreeWidget) -> Iterable[QtWidgets.QTreeWidgetItem]:
    for item in iter_tree_items(widget.invisibleRootItem()):
        if item.data(0, NODE_TYPE_ROLE) == "bookmark":
            yield item


def collect_bookmark_ids_from_item(item: QtWidgets.QTreeWidgetItem) -> list[str]:
    if item.data(0, NODE_TYPE_ROLE) == "bookmark":
        bookmark_id = item.data(0, BOOKMARK_ROLE)
        return [bookmark_id] if isinstance(bookmark_id, str) and bookmark_id else []
    out: list[str] = []
    for child in iter_tree_items(item):
        if child.data(0, NODE_TYPE_ROLE) != "bookmark":
            continue
        bookmark_id = child.data(0, BOOKMARK_ROLE)
        if isinstance(bookmark_id, str) and bookmark_id:
            out.append(bookmark_id)
    return out


def item_key(item: QtWidgets.QTreeWidgetItem) -> Optional[str]:
    value = item.data(0, NODE_KEY_ROLE)
    return value if isinstance(value, str) and value else None


def expanded_item_keys(widget: QtWidgets.QTreeWidget) -> set[str]:
    keys: set[str] = set()
    for item in iter_tree_items(widget.invisibleRootItem()):
        key = item_key(item)
        if key and item.isExpanded():
            keys.add(key)
    return keys


def bookmark_tree_item(label0: str, label1: str = "", label2: str = "") -> QtWidgets.QTreeWidgetItem:
    return QtWidgets.QTreeWidgetItem([label0, label1, label2])


def category_item(main, category: str) -> Optional[QtWidgets.QTreeWidgetItem]:
    widget = getattr(main, "bookmark_widget", None)
    if widget is None:
        return None
    wanted = normalize_category(category)
    for idx in range(widget.topLevelItemCount()):
        item = widget.topLevelItem(idx)
        if item is None or item.data(0, NODE_TYPE_ROLE) != "category":
            continue
        if normalize_category(item.data(0, NODE_CATEGORY_ROLE)) == wanted:
            return item
    return None


def focus_category_item(main, category: str) -> bool:
    item = category_item(main, category)
    widget = getattr(main, "bookmark_widget", None)
    if item is None or widget is None:
        return False
    widget.blockSignals(True)
    try:
        widget.clearSelection()
        item.setSelected(True)
        item.setExpanded(True)
        widget.setCurrentItem(item)
    finally:
        widget.blockSignals(False)
    refresh_bookmark_marks(main)
    return True
