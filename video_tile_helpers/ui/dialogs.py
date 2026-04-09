from typing import Callable, Optional

from PyQt6 import QtCore, QtGui, QtWidgets


def _build_slider_row(
    parent: QtWidgets.QWidget,
    *,
    min_value: int,
    max_value: int,
    current_value: int,
    label_width: int,
) -> tuple[QtWidgets.QHBoxLayout, QtWidgets.QSlider, QtWidgets.QLabel]:
    row = QtWidgets.QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, parent)
    slider.setRange(int(min_value), int(max_value))
    slider.setSingleStep(1)
    slider.setPageStep(5)
    slider.setValue(max(int(min_value), min(int(max_value), int(current_value))))
    value_label = QtWidgets.QLabel(f"{slider.value()}%")
    value_label.setMinimumWidth(int(label_width))
    value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
    row.addWidget(slider, 1)
    row.addWidget(value_label)
    return row, slider, value_label


def _init_slider_dialog(
    dialog: QtWidgets.QDialog,
    *,
    title: str,
    minimum_width: int,
    info_text: str,
    min_value: int,
    max_value: int,
    current_value: int,
    label_width: int,
) -> tuple[QtWidgets.QSlider, QtWidgets.QLabel]:
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setMinimumWidth(int(minimum_width))
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(10)
    layout.addWidget(QtWidgets.QLabel(info_text))
    row, slider, value_label = _build_slider_row(
        dialog,
        min_value=min_value,
        max_value=max_value,
        current_value=current_value,
        label_width=label_width,
    )
    layout.addLayout(row)
    _add_close_buttons(dialog, layout)
    slider.setFocus()
    return slider, value_label


def _add_close_buttons(dialog: QtWidgets.QDialog, layout: QtWidgets.QVBoxLayout) -> None:
    buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close, dialog)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)


class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()

    def mousePressEvent(self, e: QtGui.QMouseEvent) -> None:
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


class OpacitySliderDialog(QtWidgets.QDialog):
    def __init__(
        self,
        *,
        title: str,
        current_percent: int,
        on_change,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._on_change = on_change
        self.slider, self.value_label = _init_slider_dialog(
            self,
            title=title,
            minimum_width=340,
            info_text="10~100%",
            min_value=10,
            max_value=100,
            current_value=current_percent,
            label_width=48,
        )
        self.slider.valueChanged.connect(self._handle_value_changed)

    def _handle_value_changed(self, value: int):
        percent = max(10, min(100, int(value)))
        self.value_label.setText(f"{percent}%")
        try:
            self._on_change(percent / 100.0)
        except Exception:
            pass


class OverlayGlobalApplyDialog(QtWidgets.QDialog):
    def __init__(
        self,
        *,
        title: str,
        current_value: int,
        on_change,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._on_change = on_change
        self.slider, self.value_label = _init_slider_dialog(
            self,
            title=title,
            minimum_width=360,
            info_text="1~100%  |  맨 위 기준값, 나머지는 배수형으로 자동 배치",
            min_value=1,
            max_value=100,
            current_value=current_value,
            label_width=56,
        )
        self.slider.valueChanged.connect(self._handle_value_changed)

    def _handle_value_changed(self, value: int):
        applied = max(1, min(100, int(value)))
        self.value_label.setText(f"{applied}%")
        try:
            self._on_change(applied)
        except Exception:
            pass


class DetachedTilesOpacityGroupDialog(QtWidgets.QDialog):
    def __init__(
        self,
        *,
        title: str,
        current_percent: int,
        get_tiles: Callable[[], list],
        on_change,
        on_redock,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._get_tiles = get_tiles
        self._on_change = on_change
        self._on_redock = on_redock
        self.setWindowTitle(title)
        self.setModal(False)
        self.setMinimumWidth(360)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.info_label = QtWidgets.QLabel("", self)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        row, self.slider, self.value_label = _build_slider_row(
            self,
            min_value=10,
            max_value=100,
            current_value=current_percent,
            label_width=48,
        )
        layout.addLayout(row)

        buttons = QtWidgets.QDialogButtonBox(self)
        self.btn_redock = buttons.addButton("전체 타일로 복귀", QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        self.btn_close = buttons.addButton(QtWidgets.QDialogButtonBox.StandardButton.Close)
        layout.addWidget(buttons)

        self.slider.valueChanged.connect(self._handle_value_changed)
        self.btn_redock.clicked.connect(self._handle_redock_clicked)
        buttons.rejected.connect(self.reject)

        self._refresh_info()
        self._apply_dialog_opacity(max(10, min(100, int(current_percent))))
        self.slider.setFocus()

    def _tracked_tiles(self) -> list:
        try:
            return list(self._get_tiles() or [])
        except Exception:
            return []

    def _refresh_info(self) -> None:
        count = len(self._tracked_tiles())
        self.info_label.setText(f"공유 투명도 10~100%  |  현재 묶음 {count}개")
        self.btn_redock.setEnabled(count > 0)

    def _apply_dialog_opacity(self, percent: int) -> None:
        try:
            self.setWindowOpacity(max(0.35, min(1.0, float(percent) / 100.0)))
        except Exception:
            pass

    def _handle_value_changed(self, value: int):
        percent = max(10, min(100, int(value)))
        self.value_label.setText(f"{percent}%")
        self._apply_dialog_opacity(percent)
        self._refresh_info()
        try:
            self._on_change(percent / 100.0)
        except Exception:
            pass

    def _handle_redock_clicked(self):
        tiles = self._tracked_tiles()
        if not tiles:
            self.reject()
            return
        try:
            self._on_redock(tiles)
        finally:
            self.accept()
