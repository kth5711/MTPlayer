from PyQt6 import QtCore, QtGui, QtWidgets
from .theme import is_dark_palette


_AUX_DOCK_DARK_STYLESHEET = """
QWidget#AuxDockContainer {
    background: #0d1117;
}
QWidget#AuxDockTitleBar {
    background: #141b25;
    border: 1px solid #243040;
    border-radius: 8px;
}
QLabel#AuxDockTitleLabel {
    color: #edf3fb;
    font-weight: 600;
    padding-left: 4px;
}
QToolButton#AuxDockTitleButton {
    background: transparent;
    color: #d8e0ea;
    border: none;
    border-radius: 5px;
    padding: 2px;
}
QToolButton#AuxDockTitleButton:hover {
    background: #243143;
}
QToolButton#AuxDockTitleButton:pressed {
    background: #2c3d55;
}
QFrame#AuxDockTopBar {
    background: #151b24;
    border: 1px solid #243040;
    border-radius: 8px;
}
QLineEdit#AuxDockFilterEdit,
QComboBox#AuxDockCombo {
    background: #0f141c;
    color: #e7edf7;
    border: 1px solid #2b394d;
    border-radius: 6px;
    padding: 6px 8px;
}
QLineEdit#AuxDockFilterEdit:focus,
QComboBox#AuxDockCombo:focus {
    border: 1px solid #5f8fd7;
    background: #121a24;
}
QPushButton#AuxDockButton {
    background: #192230;
    color: #e3e9f3;
    border: 1px solid #314153;
    border-radius: 6px;
    padding: 6px 10px;
}
QPushButton#AuxDockButton:hover {
    background: #202b3b;
}
QPushButton#AuxDockButton:checked {
    background: #28405f;
    border-color: #5f8fd7;
}
QLabel#AuxDockLabel {
    color: #b4c0d0;
    font-weight: 600;
}
QCheckBox#AuxDockCheck {
    color: #d7e0eb;
    spacing: 6px;
}
QCheckBox#AuxDockCheck::indicator {
    width: 15px;
    height: 15px;
}
QTreeWidget#AuxDockTree {
    background: #0b0f15;
    color: #e7edf7;
    border: 1px solid #243040;
    border-radius: 8px;
    alternate-background-color: #111823;
}
QTreeWidget#AuxDockTree::item {
    border-radius: 5px;
    padding: 3px 4px;
}
QTreeWidget#AuxDockTree::item:hover {
    background: #182331;
}
QTreeWidget#AuxDockTree::item:selected:active {
    background: #28405f;
    color: #f3f8ff;
}
QTreeWidget#AuxDockTree::item:selected:!active {
    background: #1f3148;
    color: #dde6f2;
}
QTabWidget#AuxDockTabs::pane {
    background: #0b0f15;
    border: 1px solid #243040;
    border-radius: 8px;
    margin-top: 8px;
}
QTabBar::tab {
    background: #151c27;
    color: #c9d4e1;
    border: 1px solid #243040;
    border-bottom: none;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    padding: 7px 12px;
    margin-right: 4px;
}
QTabBar::tab:hover {
    background: #1a2432;
}
QTabBar::tab:selected {
    background: #223246;
    color: #eef4ff;
}
QHeaderView::section {
    background: #151c27;
    color: #c9d4e1;
    border: none;
    border-bottom: 1px solid #243040;
    padding: 6px 8px;
}
"""

_AUX_DOCK_LIGHT_STYLESHEET = """
QWidget#AuxDockContainer {
    background: #eef2f6;
}
QWidget#AuxDockTitleBar {
    background: #f6f8fb;
    border: 1px solid #cfd7e3;
    border-radius: 8px;
}
QLabel#AuxDockTitleLabel {
    color: #1f2a36;
    font-weight: 600;
    padding-left: 4px;
}
QToolButton#AuxDockTitleButton {
    background: transparent;
    color: #334255;
    border: none;
    border-radius: 5px;
    padding: 2px;
}
QToolButton#AuxDockTitleButton:hover {
    background: #dde5ef;
}
QToolButton#AuxDockTitleButton:pressed {
    background: #cfd8e4;
}
QFrame#AuxDockTopBar {
    background: #f6f8fb;
    border: 1px solid #cfd7e3;
    border-radius: 8px;
}
QLineEdit#AuxDockFilterEdit,
QComboBox#AuxDockCombo {
    background: #ffffff;
    color: #1d2732;
    border: 1px solid #c6d0dd;
    border-radius: 6px;
    padding: 6px 8px;
}
QLineEdit#AuxDockFilterEdit:focus,
QComboBox#AuxDockCombo:focus {
    border: 1px solid #4a82df;
    background: #ffffff;
}
QPushButton#AuxDockButton {
    background: #edf2f8;
    color: #1e2834;
    border: 1px solid #c7d2df;
    border-radius: 6px;
    padding: 6px 10px;
}
QPushButton#AuxDockButton:hover {
    background: #e4ebf4;
}
QPushButton#AuxDockButton:checked {
    background: #d8e6ff;
    border-color: #4a82df;
}
QLabel#AuxDockLabel {
    color: #4b5b6d;
    font-weight: 600;
}
QCheckBox#AuxDockCheck {
    color: #344658;
    spacing: 6px;
}
QCheckBox#AuxDockCheck::indicator {
    width: 15px;
    height: 15px;
}
QTreeWidget#AuxDockTree {
    background: #ffffff;
    color: #1d2732;
    border: 1px solid #cfd7e3;
    border-radius: 8px;
    alternate-background-color: #f5f7fa;
}
QTreeWidget#AuxDockTree::item {
    border-radius: 5px;
    padding: 3px 4px;
}
QTreeWidget#AuxDockTree::item:hover {
    background: #eef3f8;
}
QTreeWidget#AuxDockTree::item:selected:active {
    background: #d8e6ff;
    color: #0f1c2b;
}
QTreeWidget#AuxDockTree::item:selected:!active {
    background: #e7effa;
    color: #243547;
}
QTabWidget#AuxDockTabs::pane {
    background: #ffffff;
    border: 1px solid #cfd7e3;
    border-radius: 8px;
    margin-top: 8px;
}
QTabBar::tab {
    background: #eef2f6;
    color: #425365;
    border: 1px solid #cfd7e3;
    border-bottom: none;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    padding: 7px 12px;
    margin-right: 4px;
}
QTabBar::tab:hover {
    background: #e6edf5;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #1e2b37;
}
QHeaderView::section {
    background: #eef2f6;
    color: #425365;
    border: none;
    border-bottom: 1px solid #cfd7e3;
    padding: 6px 8px;
}
"""


class AuxDockTitleBar(QtWidgets.QWidget):
    def __init__(self, dock: QtWidgets.QDockWidget):
        super().__init__(dock)
        self._dock = dock
        self.setObjectName("AuxDockTitleBar")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 6, 6)
        layout.setSpacing(4)
        self._title_label = QtWidgets.QLabel(dock.windowTitle(), self)
        self._title_label.setObjectName("AuxDockTitleLabel")
        self._title_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(self._title_label, 1)
        self._float_button = self._title_button(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_TitleBarNormalButton),
            self._toggle_floating,
        )
        self._close_button = self._title_button(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_TitleBarCloseButton),
            self._close_dock,
        )
        layout.addWidget(self._float_button)
        layout.addWidget(self._close_button)
        dock.windowTitleChanged.connect(self._title_label.setText)
        dock.topLevelChanged.connect(lambda _floating: self._sync_state())
        dock.featuresChanged.connect(lambda _features: self._sync_state())
        self._sync_state()

    def _title_button(self, icon: QtGui.QIcon, slot):
        button = QtWidgets.QToolButton(self)
        button.setObjectName("AuxDockTitleButton")
        button.setAutoRaise(True)
        button.setIcon(icon)
        button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        button.setFixedSize(22, 22)
        button.clicked.connect(slot)
        return button

    def _toggle_floating(self):
        if not self._dock.isFloating():
            self._dock.setFloating(True)
        else:
            self._dock.setFloating(False)

    def _close_dock(self):
        self._dock.setVisible(False)

    def _sync_state(self):
        self._refresh_icons()
        features = self._dock.features()
        self._float_button.setVisible(
            bool(features & QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        )
        self._close_button.setVisible(
            bool(features & QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable)
        )
        if self._dock.isFloating():
            self._float_button.setToolTip("도킹")
        else:
            self._float_button.setToolTip("분리")

    def _refresh_icons(self):
        self._float_button.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_TitleBarNormalButton)
        )
        self._close_button.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_TitleBarCloseButton)
        )

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        event.ignore()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        event.ignore()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        event.ignore()


def install_aux_dock_title_bar(dock: QtWidgets.QDockWidget):
    dock.setTitleBarWidget(AuxDockTitleBar(dock))
    refresh_aux_dock_chrome(dock)


def style_aux_dock_container(container: QtWidgets.QWidget):
    container.setObjectName("AuxDockContainer")
    container.setStyleSheet(_aux_dock_stylesheet())


def make_aux_dock_top_bar() -> QtWidgets.QFrame:
    frame = QtWidgets.QFrame()
    frame.setObjectName("AuxDockTopBar")
    return frame


def style_aux_dock_filter_edit(edit: QtWidgets.QLineEdit):
    edit.setObjectName("AuxDockFilterEdit")


def style_aux_dock_combo(combo: QtWidgets.QComboBox):
    combo.setObjectName("AuxDockCombo")


def style_aux_dock_button(button: QtWidgets.QPushButton):
    button.setObjectName("AuxDockButton")


def style_aux_dock_label(label: QtWidgets.QLabel):
    label.setObjectName("AuxDockLabel")


def style_aux_dock_check(checkbox: QtWidgets.QCheckBox):
    checkbox.setObjectName("AuxDockCheck")


def style_aux_dock_tree(tree: QtWidgets.QTreeWidget):
    tree.setObjectName("AuxDockTree")


def style_aux_dock_tabs(tabs: QtWidgets.QTabWidget):
    tabs.setObjectName("AuxDockTabs")


def refresh_aux_dock_chrome(dock: QtWidgets.QDockWidget):
    stylesheet = _aux_dock_stylesheet()
    title_bar = dock.titleBarWidget()
    if title_bar is not None:
        title_bar.setStyleSheet(stylesheet)
        refresh_icons = getattr(title_bar, "_refresh_icons", None)
        if callable(refresh_icons):
            refresh_icons()
    container = dock.widget()
    if container is not None:
        container.setStyleSheet(stylesheet)


def _aux_dock_stylesheet() -> str:
    app = QtWidgets.QApplication.instance()
    if app is not None and not is_dark_palette(app.palette()):
        return _AUX_DOCK_LIGHT_STYLESHEET
    return _AUX_DOCK_DARK_STYLESHEET
