from typing import Optional, Sequence

from PyQt6 import QtCore, QtWidgets
from i18n import tr

PRESET_TOP_PERCENTS = (
    ("평균", 20),
    ("연하게", 12),
    ("강하게", 30),
)


def overlay_preset_opacity_values(layer_count: int, top_percent: int) -> list[int]:
    total = max(1, int(layer_count))
    capped_top = max(1, min(100, int(top_percent)))
    top_fraction = max(0.01, min(1.0, float(capped_top) / 100.0))
    values: list[int] = []
    for order in range(total):
        if order <= 0 or total <= 1:
            values.append(100)
            continue
        progress = float(order) / float(max(1, total - 1))
        values.append(max(10, min(100, int(round((top_fraction ** progress) * 100.0)))))
    return values


class OverlayLayerOpacityDialog(QtWidgets.QDialog):
    def __init__(
        self,
        *,
        title: str,
        layer_items: Sequence[tuple[str, int]],
        current_top_percent: int,
        on_layer_change,
        on_preset_change,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._on_layer_change = on_layer_change
        self._on_preset_change = on_preset_change
        self._value_labels: list[QtWidgets.QLabel] = []
        self._sliders: list[QtWidgets.QSlider] = []
        self._syncing_sliders = False
        self._preset_info = QtWidgets.QLabel("")
        self._current_top_percent = max(1, min(100, int(current_top_percent)))
        self._init_ui(title, list(layer_items))

    def _init_ui(self, title: str, layer_items: list[tuple[str, int]]):
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(480)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(
            QtWidgets.QLabel(
                tr(
                    self,
                    "위쪽 슬라이더부터 맨 아래 레이어입니다. 프리셋은 현재 스택 전체에 함께 적용됩니다.",
                )
            )
        )
        layout.addWidget(self._preset_info)
        self._preset_info.setText(tr(self, "현재 프리셋 기준값: {percent}%", percent=self._current_top_percent))
        self._add_preset_buttons(layout, len(layer_items))
        for index, (label, current_percent) in enumerate(layer_items):
            self._add_layer_row(layout, index, label, current_percent)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if self._sliders:
            self._sliders[0].setFocus()

    def _add_preset_buttons(self, layout: QtWidgets.QVBoxLayout, layer_count: int):
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(QtWidgets.QLabel(tr(self, "프리셋")))
        for label, top_percent in PRESET_TOP_PERCENTS:
            button = QtWidgets.QPushButton(f"{tr(self, label)} ({top_percent}%)", self)
            button.clicked.connect(
                lambda _checked=False, name=label, top=top_percent, count=layer_count: self._apply_preset(name, top, count)
            )
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)

    def _add_layer_row(
        self,
        layout: QtWidgets.QVBoxLayout,
        index: int,
        label: str,
        current_percent: int,
    ):
        layout.addWidget(QtWidgets.QLabel(label))
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, self)
        slider.setRange(10, 100)
        slider.setSingleStep(1)
        slider.setPageStep(5)
        slider.setValue(max(10, min(100, int(current_percent))))
        value_label = QtWidgets.QLabel(f"{slider.value()}%")
        value_label.setMinimumWidth(48)
        value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        slider.valueChanged.connect(lambda value, row_index=index: self._handle_slider_changed(row_index, value))
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        layout.addLayout(row)
        self._sliders.append(slider)
        self._value_labels.append(value_label)

    def _apply_preset(self, preset_name: str, top_percent: int, layer_count: int):
        values = overlay_preset_opacity_values(layer_count, top_percent)
        self._syncing_sliders = True
        try:
            for slider, value_label, value in zip(self._sliders, self._value_labels, values):
                slider.setValue(int(value))
                value_label.setText(f"{int(value)}%")
        finally:
            self._syncing_sliders = False
        self._current_top_percent = max(1, min(100, int(top_percent)))
        self._preset_info.setText(
            tr(self, "현재 프리셋 기준값: {percent}% ({name})", percent=self._current_top_percent, name=tr(self, preset_name))
        )
        try:
            self._on_preset_change(tr(self, preset_name), self._current_top_percent)
        except Exception:
            pass

    def _handle_slider_changed(self, index: int, value: int):
        percent = max(10, min(100, int(value)))
        self._value_labels[index].setText(f"{percent}%")
        if self._syncing_sliders:
            return
        try:
            self._on_layer_change(index, percent / 100.0)
        except Exception:
            pass
