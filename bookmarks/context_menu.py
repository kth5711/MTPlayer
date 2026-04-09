import os
import subprocess
import sys
from typing import Any

from PyQt6 import QtCore, QtWidgets
from .open import load_targets_into_tiles as load_targets_into_tiles_impl
from i18n import tr
from .state import bookmark_end_ms

_BOOKMARK_ROLE = int(QtCore.Qt.ItemDataRole.UserRole)
_NODE_TYPE_ROLE = _BOOKMARK_ROLE + 1
_NODE_PATH_ROLE = _BOOKMARK_ROLE + 3
_NODE_CATEGORY_ROLE = _BOOKMARK_ROLE + 4
_DEFAULT_CATEGORY = "미분류"


def bind_bookmark_context_menu(main):
    widget = getattr(main, "bookmark_widget", None)
    if widget is None:
        return
    widget.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
    widget.customContextMenuRequested.connect(lambda pos, m=main, w=widget: show_bookmark_context_menu(m, w, pos))


def show_bookmark_context_menu(main, widget: QtWidgets.QTreeWidget, pos: QtCore.QPoint):
    item = widget.itemAt(pos)
    _select_context_item(widget, item)
    first_targets = _selected_first_bookmark_targets(main)
    bookmark_targets = _selected_bookmark_targets(main)
    selected_path = _selected_context_path(widget)
    menu = QtWidgets.QMenu(widget)
    has_selection = _add_open_actions(main, menu, first_targets, bookmark_targets, selected_path)
    if has_selection:
        menu.addSeparator()
    if _has_selection(main):
        menu.addAction(tr(main, "카테고리변경"), main._classify_selected_bookmarks)
        menu.addAction(tr(main, "북마크삭제"), main._delete_selected_bookmarks)
    menu.addAction(tr(main, "카테고리추가..."), main._add_bookmark_category)
    menu.exec(widget.viewport().mapToGlobal(pos))


def _add_open_actions(main, menu, first_targets, bookmark_targets, selected_path: str | None) -> bool:
    added = False
    if first_targets:
        menu.addAction(
            tr(main, "선택 영상 열기 (파일별 첫 북마크, {count}개)", count=len(first_targets)),
            lambda m=main, targets=first_targets: load_targets_into_tiles_impl(m, targets, tr(m, "파일 첫 북마크")),
        )
        added = True
    if bookmark_targets:
        menu.addAction(
            tr(main, "선택 북마크 분배 열기 ({count}개)", count=len(bookmark_targets)),
            lambda m=main, targets=bookmark_targets: load_targets_into_tiles_impl(
                m,
                targets,
                tr(m, "북마크 분배"),
                prefer_open_parent_tiles=True,
            ),
        )
        added = True
    if selected_path:
        menu.addAction(
            tr(main, "폴더 열기(경로)"),
            lambda path=selected_path: _open_path_in_explorer(path),
        )
        added = True
    return added


def _has_selection(main) -> bool:
    bookmark_ids, file_paths, categories = _selected_state(main)
    return bool(bookmark_ids or file_paths or categories)


def _select_context_item(widget: QtWidgets.QTreeWidget, item):
    if item is None or item.isSelected():
        return
    widget.blockSignals(True)
    try:
        widget.clearSelection()
        item.setSelected(True)
        widget.setCurrentItem(item)
    finally:
        widget.blockSignals(False)


def _normalize_path(path: str) -> str:
    return os.path.normpath(os.path.abspath(path))


def _normalize_category(name: Any) -> str:
    if not isinstance(name, str):
        return _DEFAULT_CATEGORY
    text = " ".join(name.split()).strip()
    return text or _DEFAULT_CATEGORY


def _selected_context_path(widget: QtWidgets.QTreeWidget) -> str | None:
    current_item = widget.currentItem()
    path = _item_path(current_item)
    if path:
        return path
    for item in widget.selectedItems():
        path = _item_path(item)
        if path:
            return path
    return None


def _item_path(item) -> str | None:
    if item is None:
        return None
    if item.data(0, _NODE_TYPE_ROLE) not in {"file", "bookmark"}:
        return None
    path = str(item.data(0, _NODE_PATH_ROLE) or "").strip()
    return _normalize_path(path) if path else None


def _selected_state(main) -> tuple[set[str], set[str], set[str]]:
    widget = getattr(main, "bookmark_widget", None)
    if widget is None:
        return set(), set(), set()
    bookmark_ids: set[str] = set()
    file_paths: set[str] = set()
    categories: set[str] = set()
    for item in widget.selectedItems():
        node_type = item.data(0, _NODE_TYPE_ROLE)
        if node_type == "bookmark":
            bookmark_id = str(item.data(0, _BOOKMARK_ROLE) or "").strip()
            if bookmark_id:
                bookmark_ids.add(bookmark_id)
        elif node_type == "file":
            path = str(item.data(0, _NODE_PATH_ROLE) or "").strip()
            if path:
                file_paths.add(_normalize_path(path))
        elif node_type == "category":
            categories.add(_normalize_category(item.data(0, _NODE_CATEGORY_ROLE)))
    return bookmark_ids, file_paths, categories


def _entry_sort_key(entry: dict[str, Any]) -> tuple[str, str, int]:
    path = _normalize_path(str(entry.get("path", "")))
    return (os.path.basename(path).lower(), path.lower(), int(entry.get("position_ms", 0)))


def _selected_entries(main, *, direct_only: bool) -> list[dict[str, Any]]:
    bookmark_ids, file_paths, categories = _selected_state(main)
    if not (bookmark_ids or file_paths or categories):
        return []
    out: list[dict[str, Any]] = []
    for entry in getattr(main, "bookmarks", []) or []:
        bookmark_id = str(entry.get("id", "")).strip()
        path = _normalize_path(str(entry.get("path", ""))) if entry.get("path") else ""
        category = _normalize_category(entry.get("category", _DEFAULT_CATEGORY))
        if direct_only:
            if bookmark_id and bookmark_id in bookmark_ids:
                out.append(entry)
            continue
        if bookmark_id and bookmark_id in bookmark_ids:
            out.append(entry)
            continue
        if path and (path in file_paths or category in categories):
            out.append(entry)
    out.sort(key=_entry_sort_key)
    return out


def _selected_bookmark_targets(main) -> list[tuple[str, int, int | None, int, int]]:
    return [
        (
            _normalize_path(str(entry.get("path", ""))),
            int(entry.get("position_ms", 0)),
            bookmark_end_ms(entry),
            int(entry.get("video_mtime_ns", 0) or 0),
            int(entry.get("video_size", 0) or 0),
        )
        for entry in _selected_entries(main, direct_only=False)
        if str(entry.get("path", "")).strip()
    ]


def _selected_first_bookmark_targets(main) -> list[tuple[str, int, int | None, int, int]]:
    bookmark_ids, file_paths, categories = _selected_state(main)
    wanted_paths: set[str] = set(file_paths)
    for entry in getattr(main, "bookmarks", []) or []:
        path = _normalize_path(str(entry.get("path", ""))) if entry.get("path") else ""
        category = _normalize_category(entry.get("category", _DEFAULT_CATEGORY))
        bookmark_id = str(entry.get("id", "")).strip()
        if bookmark_id and bookmark_id in bookmark_ids and path:
            wanted_paths.add(path)
        elif category in categories and path:
            wanted_paths.add(path)
    first_by_path: dict[str, tuple[int, int | None, int, int]] = {}
    for entry in getattr(main, "bookmarks", []) or []:
        path = _normalize_path(str(entry.get("path", ""))) if entry.get("path") else ""
        if not path or path not in wanted_paths:
            continue
        position_ms = int(entry.get("position_ms", 0))
        end_ms = bookmark_end_ms(entry)
        video_mtime_ns = int(entry.get("video_mtime_ns", 0) or 0)
        video_size = int(entry.get("video_size", 0) or 0)
        if path not in first_by_path or position_ms < first_by_path[path][0]:
            first_by_path[path] = (position_ms, end_ms, video_mtime_ns, video_size)
    return sorted(
        ((path, data[0], data[1], data[2], data[3]) for path, data in first_by_path.items()),
        key=lambda item: (os.path.basename(item[0]).lower(), item[0].lower()),
    )


def _open_path_in_explorer(path: str):
    path = _normalize_path(str(path or ""))
    folder = os.path.dirname(path)
    try:
        if sys.platform.startswith("win"):
            if os.path.isfile(path):
                if _run_windows_explorer_select(path):
                    return
                if folder and os.path.isdir(folder):
                    os.startfile(folder)
            elif os.path.isdir(path):
                os.startfile(path)
            elif folder and os.path.isdir(folder):
                os.startfile(folder)
        elif sys.platform == "darwin":
            if os.path.exists(path):
                subprocess.run(["open", "-R", path], check=False)
            elif folder:
                subprocess.run(["open", folder], check=False)
        elif folder:
            subprocess.run(["xdg-open", folder], check=False)
    except Exception:
        pass


def _run_windows_explorer_select(path: str) -> bool:
    try:
        proc = subprocess.run(["explorer.exe", "/select,", path], check=False)
        return int(getattr(proc, "returncode", 1) or 0) == 0
    except Exception:
        return False
