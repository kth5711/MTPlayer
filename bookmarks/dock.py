from typing import Optional

from PyQt6 import QtCore, QtWidgets

from app_shell.dock_chrome import (
    install_aux_dock_title_bar,
    make_aux_dock_top_bar,
    style_aux_dock_container,
    style_aux_dock_filter_edit,
    style_aux_dock_tree,
)
from i18n import tr

from .render import refresh_bookmark_dock
from .state import refresh_bookmark_marks
from .tree_widget import BookmarkTreeWidget


def create_bookmark_dock(main):
    main.bookmarks = list(getattr(main, "bookmarks", []) or [])
    main.bookmark_categories = list(getattr(main, "bookmark_categories", []) or [])
    main.bookmark_dock = _bookmark_dock(main)
    main.bookmark_widget = _bookmark_widget(main)
    main.bookmark_dock.setWidget(_dock_container(main, main.bookmark_widget))
    main.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, main.bookmark_dock)
    main.bookmark_dock.visibilityChanged.connect(lambda visible, m=main: _on_visibility_changed(m, visible))
    main.bookmark_dock.topLevelChanged.connect(lambda _floating, m=main: _sync_aux_dock_owner(m, getattr(m, "bookmark_dock", None)))
    main.bookmark_dock.setVisible(False)
    _sync_aux_dock_owner(main, main.bookmark_dock)
    refresh_bookmark_dock(main, keep_selection=False)


def _bookmark_dock(main):
    dock = QtWidgets.QDockWidget(tr(main, "북마크"), main)
    dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.RightDockWidgetArea | QtCore.Qt.DockWidgetArea.LeftDockWidgetArea)
    install_aux_dock_title_bar(dock)
    return dock


def _bookmark_widget(main):
    widget = BookmarkTreeWidget(main)
    widget.setRootIsDecorated(True)
    widget.setUniformRowHeights(True)
    widget.setAlternatingRowColors(True)
    widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
    widget.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setExpandsOnDoubleClick(False)
    widget.setHeaderLabels([tr(main, "이름"), tr(main, "경로")])
    widget.itemDoubleClicked.connect(lambda item, _col, m=main: _on_item_double_clicked(m, item))
    widget.itemSelectionChanged.connect(lambda m=main: refresh_bookmark_marks(m))
    style_aux_dock_tree(widget)
    return widget


def _dock_container(main, widget):
    cont = QtWidgets.QWidget()
    style_aux_dock_container(cont)
    layout = QtWidgets.QVBoxLayout(cont)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(6)
    layout.addWidget(_bookmark_top_bar(main))
    layout.addWidget(widget)
    return cont


def _bookmark_top_bar(main):
    bar = make_aux_dock_top_bar()
    layout = QtWidgets.QHBoxLayout(bar)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)
    layout.addWidget(_bookmark_filter_edit(main))
    return bar


def _bookmark_filter_edit(main):
    edit = QtWidgets.QLineEdit()
    edit.setClearButtonEnabled(True)
    edit.setPlaceholderText(tr(main, "북마크 검색 (이름/경로/카테고리)"))
    edit.textChanged.connect(lambda _text, m=main: refresh_bookmark_dock(m, keep_selection=True))
    style_aux_dock_filter_edit(edit)
    main.bookmark_filter_edit = edit
    return edit


def _on_visibility_changed(main, visible: bool):
    if hasattr(main, "act_toggle_bookmark_dock"):
        main.act_toggle_bookmark_dock.setChecked(bool(visible))
    main.config["bookmark_dock_visible"] = bool(visible)
    if bool(visible):
        _sync_aux_dock_owner(main, getattr(main, "bookmark_dock", None))


def _sync_aux_dock_owner(main, dock):
    callback = getattr(main, "_sync_aux_dock_owner", None)
    if not callable(callback) or dock is None:
        return
    QtCore.QTimer.singleShot(0, lambda d=dock, cb=callback: cb(d))


def refresh_bookmark_ui_texts(main):
    widget = getattr(main, "bookmark_widget", None)
    if widget is not None:
        widget.setHeaderLabels([tr(main, "이름"), tr(main, "경로")])
    edit = getattr(main, "bookmark_filter_edit", None)
    if edit is not None:
        edit.setPlaceholderText(tr(main, "북마크 검색 (이름/경로/카테고리)"))
    refresh_bookmark_dock(main, keep_selection=True)


def _on_item_double_clicked(main, item):
    if item is None:
        return
    if item.data(0, int(QtCore.Qt.ItemDataRole.UserRole) + 1) == "bookmark":
        main._jump_to_selected_bookmark()
        return
    item.setExpanded(not item.isExpanded())


def toggle_bookmark_visibility(main, checked: Optional[bool] = None):
    if not hasattr(main, "bookmark_dock"):
        main._create_bookmark_dock()
    visible = bool(checked) if isinstance(checked, bool) else not bool(main.bookmark_dock.isVisible())
    main.bookmark_dock.setVisible(visible)
    if not visible:
        return
    refresh_bookmark_dock(main, keep_selection=True)
    try:
        main.bookmark_dock.raise_()
        main.bookmark_dock.activateWindow()
    except Exception:
        pass
