from typing import Optional

from PyQt6 import QtCore, QtWidgets

from i18n import tr

from .dock import refresh_bookmark_dock
from .selection import selected_category_names, selected_direct_bookmark_ids, selected_file_nodes
from .shared import DEFAULT_CATEGORY, display_category, normalize_category, status
from .state import bookmark_category_names, category_sort_key, refresh_bookmark_marks
from .tree_nodes import focus_category_item


def _ask_bookmark_category(main, title: str, label: str, current: str = "") -> Optional[str]:
    dlg = QtWidgets.QDialog(main)
    dlg.setWindowTitle(title)
    dlg.setModal(True)
    dlg.resize(320, dlg.sizeHint().height())
    _category_dialog_layout(main, dlg, label, current)
    if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None
    return normalize_category(dlg.findChild(QtWidgets.QComboBox, "bookmarkCategoryCombo").currentText())


def _category_dialog_layout(main, dlg, label: str, current: str):
    layout = QtWidgets.QVBoxLayout(dlg)
    form = QtWidgets.QFormLayout()
    combo = QtWidgets.QComboBox(dlg)
    combo.setObjectName("bookmarkCategoryCombo")
    combo.setEditable(True)
    combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
    combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
    for category in sorted(bookmark_category_names(main), key=category_sort_key):
        combo.addItem(category)
    combo.setCurrentText(normalize_category(current) if current else "")
    form.addRow(label, combo)
    layout.addLayout(form)
    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
        parent=dlg,
    )
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)
    (combo.lineEdit() or combo).setFocus()
    if combo.lineEdit() is not None:
        combo.lineEdit().selectAll()


def ensure_bookmark_category(main, category: str) -> bool:
    normalized = normalize_category(category)
    current = list(getattr(main, "bookmark_categories", []) or [])
    if normalized in {normalize_category(name) for name in current}:
        return False
    current.append(normalized)
    main.bookmark_categories = current
    return True


def _selected_entries_for_category_change(main) -> list[dict]:
    direct_ids = set(selected_direct_bookmark_ids(main))
    file_nodes = set(selected_file_nodes(main))
    category_names = set(selected_category_names(main))
    out: list[dict] = []
    seen: set[str] = set()
    for entry in getattr(main, "bookmarks", []) or []:
        bookmark_id = str(entry.get("id", ""))
        path = str(entry.get("path", ""))
        category = normalize_category(entry.get("category", DEFAULT_CATEGORY))
        if not bookmark_id or bookmark_id in seen:
            continue
        if bookmark_id in direct_ids or (path, category) in file_nodes or category in category_names:
            seen.add(bookmark_id)
            out.append(entry)
    return out


def _selected_category_change_state(main) -> tuple[list[dict], set[str], str]:
    entries = _selected_entries_for_category_change(main)
    selected_categories = set(selected_category_names(main))
    categories = {normalize_category(entry.get("category", DEFAULT_CATEGORY)) for entry in entries}
    categories.update(selected_categories)
    current = categories.pop() if len(categories) == 1 else DEFAULT_CATEGORY
    return entries, selected_categories, current


def _apply_category_change(main, category: str) -> bool:
    entries, selected_categories, _current = _selected_category_change_state(main)
    if not entries and not selected_categories:
        return False
    category = normalize_category(category)
    changed = _set_entry_categories(entries, category)
    category_added = ensure_bookmark_category(main, category)
    renamed = _rename_empty_category(main, selected_categories, category, entries)
    _refresh_category_change(main)
    if changed <= 0 and not category_added and not renamed:
        return False
    _save_bookmark_state(main)
    status(main, tr(main, "카테고리 변경: {category} ({count}개)", category=display_category(main, category), count=changed))
    return True


def _set_entry_categories(entries, category: str) -> int:
    changed = 0
    for entry in entries:
        if normalize_category(entry.get("category", DEFAULT_CATEGORY)) == category:
            continue
        entry["category"] = category
        changed += 1
    return changed


def _rename_empty_category(main, selected_categories: set[str], category: str, entries) -> bool:
    if entries or len(selected_categories) != 1:
        return False
    old_category = next(iter(selected_categories))
    if old_category in {DEFAULT_CATEGORY, category}:
        return False
    names = [normalize_category(name) for name in getattr(main, "bookmark_categories", []) or []]
    main.bookmark_categories = [name for name in names if name != old_category]
    ensure_bookmark_category(main, category)
    return True


def _refresh_category_change(main):
    refresh_bookmark_dock(main, keep_selection=True)
    refresh_bookmark_marks(main)


def _save_bookmark_state(main):
    try:
        main.save_config()
    except Exception:
        pass


def show_category_change_menu(main, anchor: Optional[QtWidgets.QWidget] = None) -> bool:
    entries, selected_categories, current = _selected_category_change_state(main)
    if not entries and not selected_categories:
        return False
    menu, action_add = _category_menu(main, current)
    chosen = menu.exec(_category_menu_position(main, anchor))
    if chosen is None:
        return False
    if chosen is action_add:
        add_bookmark_category(main)
        return True
    category = chosen.data()
    return _apply_category_change(main, category) if isinstance(category, str) else False


def _category_menu(main, current: str):
    menu = QtWidgets.QMenu(main)
    for category in sorted(bookmark_category_names(main), key=category_sort_key):
        action = menu.addAction(display_category(main, category))
        action.setCheckable(True)
        action.setChecked(category == current)
        action.setData(category)
    menu.addSeparator()
    return menu, menu.addAction(tr(main, "카테고리추가..."))


def _category_menu_position(main, anchor):
    if isinstance(anchor, QtWidgets.QWidget):
        return anchor.mapToGlobal(QtCore.QPoint(0, anchor.height()))
    widget = getattr(main, "bookmark_widget", None)
    current_item = widget.currentItem() if widget is not None else None
    rect = widget.visualItemRect(current_item) if current_item is not None else widget.rect()
    return widget.viewport().mapToGlobal(rect.bottomLeft())


def classify_selected_bookmarks(main):
    show_category_change_menu(main, anchor=None)


def add_bookmark_category(main):
    current = _current_category(main)
    category = _ask_bookmark_category(main, tr(main, "카테고리 추가"), tr(main, "카테고리 이름"), current=current)
    if category is None:
        return
    added = ensure_bookmark_category(main, category)
    refresh_bookmark_dock(main, keep_selection=True)
    focus_category_item(main, category)
    if not added:
        status(main, tr(main, "이미 있는 카테고리: {category}", category=display_category(main, category)))
        return
    _save_bookmark_state(main)
    status(main, tr(main, "카테고리 추가: {category}", category=display_category(main, category)))


def _current_category(main) -> str:
    widget = getattr(main, "bookmark_widget", None)
    item = widget.currentItem() if widget is not None else None
    return normalize_category(item.data(0,  int(QtCore.Qt.ItemDataRole.UserRole) + 4)) if item is not None else ""


def move_bookmark_items_to_category(main, bookmark_ids, file_nodes, target_category: str) -> int:
    target_ids = _target_bookmark_ids(main, bookmark_ids, file_nodes)
    if not target_ids:
        return 0
    target_category = normalize_category(target_category)
    changed = 0
    for entry in getattr(main, "bookmarks", []) or []:
        if str(entry.get("id", "")) not in target_ids:
            continue
        if normalize_category(entry.get("category", DEFAULT_CATEGORY)) == target_category:
            continue
        entry["category"] = target_category
        changed += 1
    ensure_bookmark_category(main, target_category)
    _refresh_category_change(main)
    if changed > 0:
        _save_bookmark_state(main)
        status(main, tr(main, "카테고리 변경: {category} ({count}개)", category=display_category(main, target_category), count=changed))
    return changed


def _target_bookmark_ids(main, bookmark_ids, file_nodes) -> set[str]:
    ids = {str(bookmark_id) for bookmark_id in (bookmark_ids or []) if str(bookmark_id).strip()}
    file_keys = {(str(path), normalize_category(category)) for path, category in (file_nodes or []) if str(path).strip()}
    for entry in getattr(main, "bookmarks", []) or []:
        key = (str(entry.get("path", "")), normalize_category(entry.get("category", DEFAULT_CATEGORY)))
        if key in file_keys:
            ids.add(str(entry.get("id", "")))
    return {bookmark_id for bookmark_id in ids if bookmark_id}
