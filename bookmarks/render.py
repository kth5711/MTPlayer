import os

from PyQt6 import QtCore, QtGui

from i18n import tr

from .shared import BOOKMARK_ROLE, DEFAULT_CATEGORY, NODE_CATEGORY_ROLE, NODE_KEY_ROLE, NODE_PATH_ROLE, NODE_TYPE_ROLE, display_category, format_range_ms, normalize_category
from .selection import selected_leaf_ids
from .state import bookmark_category_names, bookmark_end_ms, bookmark_payload, category_sort_key
from .tree_nodes import bookmark_tree_item, expanded_item_keys


def refresh_bookmark_dock(main, *, keep_selection: bool = True):
    widget = getattr(main, "bookmark_widget", None)
    if widget is None:
        return
    query = _bookmark_filter_query(main)
    selected_ids = selected_leaf_ids(main) if keep_selection else set()
    expanded_keys = expanded_item_keys(widget) if keep_selection else set()
    widget.setUpdatesEnabled(False)
    try:
        _populate_bookmark_tree(main, widget, selected_ids, expanded_keys, query)
    finally:
        widget.setUpdatesEnabled(True)
    _update_bookmark_title(main)


def _populate_bookmark_tree(main, widget, selected_ids: set[str], expanded_keys: set[str], query: str):
    widget.clear()
    entries = _filtered_bookmark_entries(main, query)
    categories = _add_category_nodes(main, widget, expanded_keys, entries, query)
    files: dict[tuple[str, str], object] = {}
    current_item = None
    for entry in entries:
        current_item = _append_bookmark_entry(
            main,
            categories,
            files,
            entry,
            expanded_keys,
            selected_ids,
            current_item,
        )
    widget.expandToDepth(0)
    widget.resizeColumnToContents(0)
    widget.resizeColumnToContents(1)
    _set_current_item(widget, current_item)


def _sorted_bookmark_entries(main) -> list[dict]:
    return sorted(
        bookmark_payload(main),
        key=lambda item: (
            normalize_category(item.get("category", DEFAULT_CATEGORY)).lower(),
            os.path.basename(str(item.get("path", ""))).lower(),
            str(item.get("path", "")).lower(),
            int(item.get("position_ms", 0)),
            int(item.get("end_ms", -1) or -1),
        ),
    )


def _filtered_bookmark_entries(main, query: str) -> list[dict]:
    entries = _sorted_bookmark_entries(main)
    if not query:
        return entries
    return [entry for entry in entries if _bookmark_entry_matches(main, entry, query)]


def _bookmark_entry_matches(main, entry: dict, query: str) -> bool:
    path = str(entry.get("path", ""))
    category = display_category(main, normalize_category(entry.get("category", DEFAULT_CATEGORY)))
    time_label = format_range_ms(int(entry.get("position_ms", 0)), bookmark_end_ms(entry))
    haystacks = (os.path.basename(path) or path, path, category, time_label)
    return any(query in str(text or "").casefold() for text in haystacks)


def _add_category_nodes(main, widget, expanded_keys: set[str], entries: list[dict], query: str):
    categories = {}
    for category in _category_names_for_render(main, entries, query):
        categories[category] = _create_category_item(main, widget, category, expanded_keys)
    return categories


def _category_names_for_render(main, entries: list[dict], query: str):
    if not query:
        return sorted(bookmark_category_names(main), key=category_sort_key)
    categories = {normalize_category(entry.get("category", DEFAULT_CATEGORY)) for entry in entries}
    return sorted(categories, key=category_sort_key)


def _create_category_item(main, widget, category: str, expanded_keys: set[str]):
    item = bookmark_tree_item(display_category(main, category))
    item.setData(0, NODE_TYPE_ROLE, "category")
    item.setData(0, NODE_KEY_ROLE, f"cat:{category}")
    item.setData(0, NODE_CATEGORY_ROLE, category)
    widget.addTopLevelItem(item)
    item.setExpanded(f"cat:{category}" in expanded_keys or True)
    return item


def _append_bookmark_entry(main, categories, files, entry, expanded_keys, selected_ids, current_item):
    path = str(entry.get("path", ""))
    category = normalize_category(entry.get("category", DEFAULT_CATEGORY))
    file_item = _file_item(main, categories, files, category, path, expanded_keys)
    leaf = _bookmark_leaf(entry, path, category)
    file_item.addChild(leaf)
    _apply_missing_path_style(path, file_item, leaf)
    return _restore_leaf_selection(leaf, file_item, categories[category], selected_ids, current_item)


def _file_item(main, categories, files, category: str, path: str, expanded_keys: set[str]):
    file_key = (category, path)
    if file_key in files:
        return files[file_key]
    file_item = bookmark_tree_item(os.path.basename(path) or path, path)
    file_item.setData(0, NODE_TYPE_ROLE, "file")
    file_item.setData(0, NODE_KEY_ROLE, f"file:{category}:{path}")
    file_item.setData(0, NODE_PATH_ROLE, path)
    file_item.setData(0, NODE_CATEGORY_ROLE, category)
    file_item.setToolTip(0, path)
    file_item.setToolTip(1, path)
    categories[category].addChild(file_item)
    file_item.setExpanded(f"file:{category}:{path}" in expanded_keys)
    files[file_key] = file_item
    return file_item


def _bookmark_leaf(entry, path: str, category: str):
    time_label = format_range_ms(int(entry.get("position_ms", 0)), bookmark_end_ms(entry))
    leaf = bookmark_tree_item(time_label, "")
    leaf.setData(0, NODE_TYPE_ROLE, "bookmark")
    leaf.setData(0, NODE_KEY_ROLE, f"bookmark:{entry.get('id', '')}")
    leaf.setData(0, BOOKMARK_ROLE, str(entry.get("id", "")))
    leaf.setData(0, NODE_PATH_ROLE, path)
    leaf.setData(0, NODE_CATEGORY_ROLE, category)
    leaf.setToolTip(0, path)
    leaf.setToolTip(1, path)
    return leaf


def _apply_missing_path_style(path: str, file_item, leaf):
    if os.path.exists(path):
        return
    brush = QtGui.QBrush(QtGui.QColor("#c66"))
    for col in range(3):
        leaf.setForeground(col, brush)
        file_item.setForeground(col, brush)


def _restore_leaf_selection(leaf, file_item, category_item, selected_ids: set[str], current_item):
    if str(leaf.data(0, BOOKMARK_ROLE)) not in selected_ids:
        return current_item
    leaf.setSelected(True)
    file_item.setExpanded(True)
    category_item.setExpanded(True)
    return leaf


def _set_current_item(widget, current_item):
    if current_item is not None:
        widget.setCurrentItem(current_item)
        return
    if widget.topLevelItemCount() > 0:
        widget.setCurrentItem(widget.topLevelItem(0))


def _update_bookmark_title(main):
    dock = getattr(main, "bookmark_dock", None)
    if dock is None:
        return
    dock.setWindowTitle(tr(main, "북마크 ({count})", count=len(bookmark_payload(main))))


def _bookmark_filter_query(main) -> str:
    edit = getattr(main, "bookmark_filter_edit", None)
    if edit is None:
        return ""
    return " ".join(str(edit.text() or "").split()).strip().casefold()
