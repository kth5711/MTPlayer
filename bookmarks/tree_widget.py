from typing import Any, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from .selection import selected_direct_bookmark_ids, selected_file_nodes
from .shared import NODE_CATEGORY_ROLE, NODE_TYPE_ROLE, normalize_category


class BookmarkTreeWidget(QtWidgets.QTreeWidget):
    MIME_TYPE = "application/x-multi-play-bookmark-tree"

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._drag_payload: Optional[dict[str, Any]] = None
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)

    def _collect_drag_payload(self) -> Optional[dict[str, Any]]:
        bookmark_ids = selected_direct_bookmark_ids(self._main)
        file_nodes = selected_file_nodes(self._main)
        if not bookmark_ids and not file_nodes:
            return None
        return {"bookmark_ids": list(bookmark_ids), "file_nodes": list(file_nodes)}

    def _drop_target_category(self, pos: QtCore.QPoint) -> Optional[str]:
        item = self.itemAt(pos)
        if item is None:
            return None
        if item.data(0, NODE_TYPE_ROLE) not in {"category", "file", "bookmark"}:
            return None
        return normalize_category(item.data(0, NODE_CATEGORY_ROLE))

    def _can_accept_drag(self, event: QtGui.QDragMoveEvent) -> bool:
        return bool(
            event.source() is self
            and self._drag_payload
            and event.mimeData().hasFormat(self.MIME_TYPE)
            and self._drop_target_category(event.position().toPoint()) is not None
        )

    def startDrag(self, supportedActions: QtCore.Qt.DropAction) -> None:
        payload = self._collect_drag_payload()
        if payload is None:
            return
        self._drag_payload = payload
        mime = QtCore.QMimeData()
        mime.setData(self.MIME_TYPE, QtCore.QByteArray(b"bookmark-tree"))
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        try:
            drag.exec(QtCore.Qt.DropAction.MoveAction)
        finally:
            self._drag_payload = None

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        event.acceptProposedAction() if self._can_accept_drag(event) else event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        event.acceptProposedAction() if self._can_accept_drag(event) else event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        if event.source() is not self or self._drag_payload is None:
            event.ignore()
            return
        target_category = self._drop_target_category(event.position().toPoint())
        if not target_category:
            event.ignore()
            return
        from .categories import move_bookmark_items_to_category

        moved = move_bookmark_items_to_category(
            self._main,
            self._drag_payload.get("bookmark_ids", []),
            self._drag_payload.get("file_nodes", []),
            target_category,
        )
        if moved <= 0:
            event.ignore()
            return
        event.acceptProposedAction()
