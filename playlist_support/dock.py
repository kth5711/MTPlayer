from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from i18n import tr

from .duration import PlaylistDurationWorker, on_playlist_duration_ready


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
        payload = []
        for item in self.selectedItems():
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
        target = _drop_target_item(self, event)
        meta = target.data(0, QtCore.Qt.ItemDataRole.UserRole) if target is not None else None
        if not isinstance(meta, dict) or meta.get("type") != "tile":
            self._drag_payload = None
            return
        dst_idx = meta["tile_idx"]
        entries = [(src_idx, row, path) for src_idx, row, path in self._drag_payload]
        self._drag_payload = None
        self.filesMoved.emit(dst_idx, entries)
        event.acceptProposedAction()

    def _on_double_clicked(self, item, _column):
        meta = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(meta, dict) and meta.get("type") in {"file", "bookmark"}:
            self.openRequested.emit(meta)


def _drop_target_item(tree, event):
    item = tree.itemAt(event.position().toPoint())
    while item and item.parent():
        item = item.parent()
    if item is not None:
        return item
    return tree.topLevelItem(0)


def create_playlist_dock(main):
    main.playlist_dock = QtWidgets.QDockWidget(tr(main, "플레이리스트"), main)
    main.playlist_dock.setAllowedAreas(_playlist_dock_areas())
    container = QtWidgets.QWidget()
    layout = _playlist_container_layout(container)
    layout.addLayout(_build_playlist_filter_row(main))
    layout.addWidget(_build_playlist_tree(main))
    _ensure_playlist_duration_worker(main)
    main.playlist_dock.setWidget(container)
    main.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, main.playlist_dock)
    main.playlist_dock.visibilityChanged.connect(lambda visible: _on_dock_visibility_changed(main, visible))
    main.playlist_dock.setVisible(False)


def _playlist_dock_areas():
    return QtCore.Qt.DockWidgetArea.RightDockWidgetArea | QtCore.Qt.DockWidgetArea.LeftDockWidgetArea


def _playlist_container_layout(container):
    layout = QtWidgets.QVBoxLayout(container)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(6)
    return layout


def _build_playlist_filter_row(main):
    row = QtWidgets.QHBoxLayout()
    row.setSpacing(6)
    main.playlist_filter_edit = QtWidgets.QLineEdit()
    main.playlist_filter_edit.setClearButtonEnabled(True)
    main.playlist_filter_edit.setPlaceholderText(tr(main, "플레이리스트 검색 (파일명/경로)"))
    main.playlist_filter_edit.textChanged.connect(
        lambda _text: main.request_playlist_refresh(force=True, delay_ms=120)
    )
    row.addWidget(main.playlist_filter_edit, 1)
    main.playlist_sort_label = QtWidgets.QLabel(tr(main, "정렬"))
    row.addWidget(main.playlist_sort_label)
    row.addWidget(_build_playlist_sort_combo(main))
    row.addWidget(_build_playlist_sort_order_button(main))
    return row


def _build_playlist_sort_combo(main):
    combo = QtWidgets.QComboBox()
    combo.addItem(tr(main, "정렬 안 함"), "none")
    combo.addItem(tr(main, "시간순"), "time")
    combo.addItem(tr(main, "숫자순"), "number")
    combo.addItem(tr(main, "알파벳~한글"), "alpha_hangul")
    combo.currentIndexChanged.connect(main._on_playlist_sort_changed)
    main.playlist_sort_mode_combo = combo
    return combo


def _build_playlist_sort_order_button(main):
    button = QtWidgets.QPushButton(tr(main, "오름차순"))
    button.setCheckable(True)
    button.setChecked(False)
    button.clicked.connect(main._on_playlist_sort_order_toggled)
    main.playlist_sort_order_button = button
    return button


def _build_playlist_tree(main):
    tree = DockPlaylistTree()
    tree.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
    tree.customContextMenuRequested.connect(main._on_playlist_context_menu)
    tree.filesMoved.connect(main._on_files_moved_between_tiles)
    tree.openRequested.connect(main._play_from_tile_row)
    main.playlist_widget = tree
    return tree


def _ensure_playlist_duration_worker(main):
    worker = getattr(main, "_playlist_duration_worker", None)
    try:
        worker_running = bool(worker is not None and worker.isRunning())
    except Exception:
        worker_running = False
    if worker_running:
        return
    worker = PlaylistDurationWorker(main)
    worker.durationReady.connect(
        lambda path, sig, duration_ms, m=main: on_playlist_duration_ready(m, path, sig, duration_ms)
    )
    worker.start()
    main._playlist_duration_worker = worker


def _on_dock_visibility_changed(main, visible: bool):
    if hasattr(main, "act_toggle_playlist_dock"):
        main.act_toggle_playlist_dock.setChecked(bool(visible))
    main.config["playlist_dock_visible"] = bool(visible)
    if bool(visible):
        main.request_playlist_refresh(force=True)


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
    _refresh_sort_combo_texts(main)
    main._sync_playlist_sort_order_button_text()


def _refresh_sort_combo_texts(main):
    combo = getattr(main, "playlist_sort_mode_combo", None)
    if combo is None:
        return
    entries = (("none", "정렬 안 함"), ("time", "시간순"), ("number", "숫자순"), ("alpha_hangul", "알파벳~한글"))
    for index, (data, text) in enumerate(entries):
        if index < combo.count() and str(combo.itemData(index) or "") == data:
            combo.setItemText(index, tr(main, text))


def request_playlist_refresh(main, *, force: bool = False, delay_ms: int = 0):
    if not hasattr(main, "playlist_widget"):
        return
    main._playlist_refresh_pending = True
    main._playlist_refresh_force = bool(main._playlist_refresh_force or force)
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
