from PyQt6 import QtCore, QtWidgets


class ResponsiveSplitWidget(QtWidgets.QWidget):
    def __init__(
        self,
        first: QtWidgets.QWidget,
        second: QtWidgets.QWidget,
        *,
        breakpoint: int = 760,
        spacing: int = 8,
        first_stretch: int = 1,
        second_stretch: int = 1,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent)
        self._breakpoint = max(240, int(breakpoint))
        self._box = QtWidgets.QBoxLayout(QtWidgets.QBoxLayout.Direction.LeftToRight, self)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(max(0, int(spacing)))
        self._box.addWidget(first, max(0, int(first_stretch)))
        self._box.addWidget(second, max(0, int(second_stretch)))
        self._apply_direction()

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_direction()

    def showEvent(self, event):  # type: ignore[override]
        super().showEvent(event)
        self._apply_direction()

    def _apply_direction(self) -> None:
        width = max(0, int(self.width()))
        direction = (
            QtWidgets.QBoxLayout.Direction.TopToBottom
            if width and width < self._breakpoint
            else QtWidgets.QBoxLayout.Direction.LeftToRight
        )
        if self._box.direction() != direction:
            self._box.setDirection(direction)
            self.updateGeometry()

    def isStacked(self) -> bool:
        return self._box.direction() == QtWidgets.QBoxLayout.Direction.TopToBottom


class CollapsibleSectionBox(QtWidgets.QFrame):
    expandedChanged = QtCore.pyqtSignal(bool)

    def __init__(
        self,
        title: str,
        content: QtWidgets.QWidget,
        *,
        parent: QtWidgets.QWidget | None = None,
        expanded: bool = True,
    ):
        super().__init__(parent)
        self._content = content
        self.setObjectName("CollapsibleSectionBox")
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            """
            QFrame#CollapsibleSectionBox {
                border: 1px solid palette(mid);
                border-radius: 6px;
                background: palette(window);
            }
            QFrame#CollapsibleSectionBox > QToolButton {
                border: none;
                font-weight: 600;
                padding: 0px;
                text-align: left;
                background: transparent;
            }
            """
        )
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(8)
        self._toggle = QtWidgets.QToolButton(self)
        self._toggle.setText(str(title))
        self._toggle.setCheckable(True)
        self._toggle.setChecked(bool(expanded))
        self._toggle.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self._toggle.toggled.connect(self._set_expanded)
        self._layout.addWidget(self._toggle)
        self._layout.addWidget(self._content)
        self._set_expanded(bool(expanded))

    def isExpanded(self) -> bool:
        return bool(self._toggle.isChecked())

    def setExpanded(self, expanded: bool) -> None:
        self._toggle.setChecked(bool(expanded))

    def _set_expanded(self, expanded: bool) -> None:
        self._toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if bool(expanded) else QtCore.Qt.ArrowType.RightArrow
        )
        self._content.setVisible(bool(expanded))
        self.expandedChanged.emit(bool(expanded))
        self.updateGeometry()


class _EqualSectionHeightBinder(QtCore.QObject):
    def __init__(self, split: ResponsiveSplitWidget, boxes: list[CollapsibleSectionBox]):
        super().__init__(split)
        self._split = split
        self._boxes = list(boxes)
        self._pending = False
        self._split.installEventFilter(self)
        for box in self._boxes:
            box.installEventFilter(self)
            box.expandedChanged.connect(self._schedule_sync)
        self._schedule_sync()

    def eventFilter(self, watched, event):  # type: ignore[override]
        if event.type() in (
            QtCore.QEvent.Type.Resize,
            QtCore.QEvent.Type.LayoutRequest,
            QtCore.QEvent.Type.Show,
            QtCore.QEvent.Type.Hide,
        ):
            self._schedule_sync()
        return super().eventFilter(watched, event)

    def _schedule_sync(self) -> None:
        if self._pending:
            return
        self._pending = True
        QtCore.QTimer.singleShot(0, self._sync)

    def _sync(self) -> None:
        self._pending = False
        for box in self._boxes:
            box.setMinimumHeight(0)
        if self._split.isStacked():
            return
        if not self._boxes or not all(box.isExpanded() for box in self._boxes):
            return
        target = max(int(box.sizeHint().height()) for box in self._boxes)
        for box in self._boxes:
            box.setMinimumHeight(target)
            box.updateGeometry()


def bind_equal_section_heights(
    split: ResponsiveSplitWidget, *boxes: CollapsibleSectionBox
) -> QtCore.QObject:
    return _EqualSectionHeightBinder(split, list(boxes))
