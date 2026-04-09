from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from app_shell.dock_chrome import (
    install_aux_dock_title_bar,
    make_aux_dock_top_bar,
    style_aux_dock_button,
    style_aux_dock_combo,
    style_aux_dock_container,
    style_aux_dock_filter_edit,
    style_aux_dock_label,
    style_aux_dock_tree,
)
from i18n import tr
from .duration_worker import PlaylistDurationWorker


class DockPlaylistTree(QtWidgets.QTreeWidget):
    filesMoved = QtCore.pyqtSignal(int, list)
    openRequested = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["타일 / 미디어 목록", "시간"])
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self._drag_payload = None
        self.itemDoubleClicked.connect(self._on_double_clicked)

    def startDrag(self, actions):
        items = self.selectedItems()
        payload = []
        for item in items:
            meta = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(meta, dict) and meta.get("type") == "file":
                payload.append((meta["tile_idx"], meta["row"], meta["path"]))
        if payload:
            self._drag_payload = payload
        super().startDrag(actions)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        event.acceptProposedAction()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent):
        event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent):
        if not self._drag_payload:
            return super().dropEvent(event)
        target = _drop_target_top_item(self, event.position().toPoint())
        if target is None:
            self._drag_payload = None
            return
        meta = target.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if not isinstance(meta, dict) or meta.get("type") != "tile":
            self._drag_payload = None
            return
        dst_idx = meta["tile_idx"]
        moved = [(src_idx, row, path) for src_idx, row, path in self._drag_payload]
        self._drag_payload = None
        self.filesMoved.emit(dst_idx, moved)
        event.acceptProposedAction()

    def _on_double_clicked(self, item, column):
        meta = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(meta, dict) and meta.get("type") in {"file", "bookmark"}:
            self.openRequested.emit(meta)


def _drop_target_top_item(tree: DockPlaylistTree, pos: QtCore.QPoint):
    item = tree.itemAt(pos)
    while item and item.parent():
        item = item.parent()
    if item is not None:
        return item
    return tree.topLevelItem(0)
def create_playlist_dock(main):
    main.playlist_dock = _build_playlist_dock(main)
    container, layout = _build_playlist_container()
    _build_playlist_filter_row(main, layout)
    _build_playlist_tree(main, layout)
    _ensure_duration_worker(main)
    main.playlist_dock.setWidget(container)
    main.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, main.playlist_dock)
    main.playlist_dock.visibilityChanged.connect(lambda visible: _on_dock_visibility_changed(main, visible))
    main.playlist_dock.topLevelChanged.connect(lambda _floating, m=main: _sync_aux_dock_owner(m, getattr(m, "playlist_dock", None)))
    main.playlist_dock.setVisible(False)
    _sync_aux_dock_owner(main, main.playlist_dock)


def _build_playlist_dock(main):
    dock = QtWidgets.QDockWidget(tr(main, "플레이리스트"), main)
    dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.RightDockWidgetArea | QtCore.Qt.DockWidgetArea.LeftDockWidgetArea)
    install_aux_dock_title_bar(dock)
    return dock


def _build_playlist_container():
    cont = QtWidgets.QWidget()
    style_aux_dock_container(cont)
    layout = QtWidgets.QVBoxLayout(cont)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(6)
    return cont, layout


def _build_playlist_filter_row(main, layout):
    bar = make_aux_dock_top_bar()
    row = QtWidgets.QHBoxLayout(bar)
    row.setContentsMargins(8, 8, 8, 8)
    row.setSpacing(6)
    main.playlist_filter_edit = QtWidgets.QLineEdit()
    main.playlist_filter_edit.setClearButtonEnabled(True)
    main.playlist_filter_edit.setPlaceholderText(tr(main, "플레이리스트 검색 (파일명/경로)"))
    main.playlist_filter_edit.textChanged.connect(lambda _text: main.request_playlist_refresh(force=True, delay_ms=120))
    style_aux_dock_filter_edit(main.playlist_filter_edit)
    row.addWidget(main.playlist_filter_edit, 1)
    main.playlist_sort_label = QtWidgets.QLabel(tr(main, "정렬"))
    style_aux_dock_label(main.playlist_sort_label)
    row.addWidget(main.playlist_sort_label)
    _build_playlist_sort_controls(main, row)
    layout.addWidget(bar)


def _build_playlist_sort_controls(main, row):
    main.playlist_sort_mode_combo = QtWidgets.QComboBox()
    style_aux_dock_combo(main.playlist_sort_mode_combo)
    for text, value in (
        ("정렬 안 함", "none"),
        ("시간순", "time"),
        ("숫자순", "number"),
        ("알파벳~한글", "alpha_hangul"),
    ):
        main.playlist_sort_mode_combo.addItem(tr(main, text), value)
    main.playlist_sort_mode_combo.currentIndexChanged.connect(main._on_playlist_sort_changed)
    row.addWidget(main.playlist_sort_mode_combo)
    main.playlist_sort_order_button = QtWidgets.QPushButton(tr(main, "오름차순"))
    main.playlist_sort_order_button.setCheckable(True)
    main.playlist_sort_order_button.setChecked(False)
    main.playlist_sort_order_button.clicked.connect(main._on_playlist_sort_order_toggled)
    style_aux_dock_button(main.playlist_sort_order_button)
    row.addWidget(main.playlist_sort_order_button)


def _build_playlist_tree(main, layout):
    main.playlist_widget = DockPlaylistTree()
    style_aux_dock_tree(main.playlist_widget)
    main.playlist_widget.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
    main.playlist_widget.customContextMenuRequested.connect(main._on_playlist_context_menu)
    main.playlist_widget.filesMoved.connect(main._on_files_moved_between_tiles)
    main.playlist_widget.openRequested.connect(main._play_from_tile_row)
    layout.addWidget(main.playlist_widget)


def _ensure_duration_worker(main):
    worker = getattr(main, "_playlist_duration_worker", None)
    try:
        if worker is not None and worker.isRunning():
            return
    except Exception:
        pass
    from .duration import on_playlist_duration_ready

    worker = PlaylistDurationWorker(main)
    worker.durationReady.connect(lambda path, sig, duration_ms, m=main: on_playlist_duration_ready(m, path, sig, duration_ms))
    worker.start()
    main._playlist_duration_worker = worker


def _on_dock_visibility_changed(main, visible: bool):
    if hasattr(main, "act_toggle_playlist_dock"):
        main.act_toggle_playlist_dock.setChecked(bool(visible))
    main.config["playlist_dock_visible"] = bool(visible)
    if bool(visible):
        _sync_aux_dock_owner(main, getattr(main, "playlist_dock", None))
    if bool(visible):
        main.request_playlist_refresh(force=True)


def _sync_aux_dock_owner(main, dock):
    callback = getattr(main, "_sync_aux_dock_owner", None)
    if not callable(callback) or dock is None:
        return
    QtCore.QTimer.singleShot(0, lambda d=dock, cb=callback: cb(d))


def refresh_playlist_ui_texts(main):
    dock = getattr(main, "playlist_dock", None)
    if dock is not None:
        dock.setWindowTitle(tr(main, "플레이리스트"))
    tree = getattr(main, "playlist_widget", None)
    if tree is not None:
        tree.setHeaderLabels([tr(main, "타일 / 미디어 목록"), tr(main, "시간")])
    edit = getattr(main, "playlist_filter_edit", None)
    if edit is not None:
        edit.setPlaceholderText(tr(main, "플레이리스트 검색 (파일명/경로)"))
    label = getattr(main, "playlist_sort_label", None)
    if label is not None:
        label.setText(tr(main, "정렬"))
    _refresh_playlist_sort_mode_texts(main)
    main._sync_playlist_sort_order_button_text()


def _refresh_playlist_sort_mode_texts(main):
    combo = getattr(main, "playlist_sort_mode_combo", None)
    if combo is None:
        return
    for index, (data, text) in enumerate((("none", "정렬 안 함"), ("time", "시간순"), ("number", "숫자순"), ("alpha_hangul", "알파벳~한글"))):
        if index < combo.count() and str(combo.itemData(index) or "") == data:
            combo.setItemText(index, tr(main, text))


def request_playlist_refresh(main, *, force: bool = False, delay_ms: int = 0):
    if not hasattr(main, "playlist_widget"):
        return
    main._playlist_refresh_pending = True
    main._playlist_refresh_force = bool(getattr(main, "_playlist_refresh_force", False) or force)
    timer = getattr(main, "_playlist_refresh_timer", None)
    if timer is None:
        main.update_playlist(force=force)
        return
    timer.start(max(0, int(delay_ms)))


def flush_playlist_refresh(main):
    if not getattr(main, "_playlist_refresh_pending", False):
        return
    main.update_playlist(force=bool(getattr(main, "_playlist_refresh_force", False)))


def toggle_playlist_visibility(main, checked: Optional[bool] = None):
    if not hasattr(main, "playlist_dock"):
        main._create_playlist_dock()
    visible = bool(checked) if isinstance(checked, bool) else not main.playlist_dock.isVisible()
    main.playlist_dock.setVisible(visible)
    if visible:
        main.request_playlist_refresh(force=True)
