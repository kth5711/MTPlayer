from PyQt6 import QtWidgets

from scene_analysis.core.media import FFMPEG_BIN, resolve_ffmpeg_bin
from i18n import tr
from .ui_responsive import CollapsibleSectionBox, ResponsiveSplitWidget


def build_scan_options_section(dialog, host, layout) -> None:
    dialog.ed_ff = _ffmpeg_path_line_edit(dialog, host)
    dialog.btn_scan = QtWidgets.QPushButton(tr(dialog, "탐색 실행"))
    dialog.btn_scan.setMinimumHeight(34)
    dialog.btn_scan.setMinimumWidth(140)
    layout.addWidget(_scan_primary_row(dialog))
    layout.addWidget(_scan_secondary_row(dialog))
    layout.addLayout(_scan_action_row(dialog))


def _ffmpeg_path_line_edit(dialog, host):
    line_edit = QtWidgets.QLineEdit(dialog)
    default_bin = resolve_ffmpeg_bin(str(getattr(host, "ffmpeg_path", "") or FFMPEG_BIN))
    line_edit.setText(default_bin)
    line_edit.hide()
    setattr(host, "ffmpeg_path", default_bin)
    return line_edit


def _scan_primary_row(dialog):
    box = _scan_section_box(dialog, tr(dialog, "탐색 설정"), _scan_decode_group(dialog))
    box.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
    return box


def _scan_secondary_row(dialog):
    box = _scan_section_box(dialog, tr(dialog, "결과 정리"), _scan_result_group(dialog))
    box.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
    return box


def _scan_action_row(dialog):
    row = QtWidgets.QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    row.addWidget(dialog.btn_scan)
    row.addWidget(_scan_action_hint(dialog))
    row.addStretch(1)
    return row


def _scan_decode_group(dialog):
    widget = QtWidgets.QWidget(dialog)
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    left = QtWidgets.QWidget(widget)
    left_col = _scan_group_layout(left)
    dialog.spn_thr = _double_spin(0.05, 0.90, 0.01, 0.35, width=88)
    left_col.addWidget(_field_row(dialog, "Threshold", dialog.spn_thr))
    dialog.spn_fps = _spin(0, 60, 5, width=88)
    left_col.addWidget(_field_row(dialog, "Sample FPS", dialog.spn_fps))
    right = QtWidgets.QWidget(widget)
    right_col = _scan_group_layout(right)
    dialog.spn_dw = _spin(0, 1920, 320, width=88)
    right_col.addWidget(_field_row(dialog, "Downscale(px)", dialog.spn_dw))
    row = ResponsiveSplitWidget(
        left,
        right,
        breakpoint=860,
        spacing=12,
        first_stretch=1,
        second_stretch=1,
        parent=widget,
    )
    row.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
    layout.addWidget(row)
    return widget


def _scan_result_group(dialog):
    widget = QtWidgets.QWidget(dialog)
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    left = QtWidgets.QWidget(widget)
    left_col = _scan_group_layout(left)
    dialog.spn_mingap = _spin(0, 10000, 800, width=88)
    left_col.addWidget(_field_row(dialog, tr(dialog, "간격(ms)"), dialog.spn_mingap))
    dialog.spn_topk = _spin(0, 5000, 0, width=88)
    left_col.addWidget(_field_row(dialog, tr(dialog, "Top-K 표시"), dialog.spn_topk))
    right = QtWidgets.QWidget(widget)
    right_col = _scan_group_layout(right)
    dialog.spn_batch = _spin(10, 200, 30, width=88)
    right_col.addWidget(_field_row(dialog, tr(dialog, "표시 개수(Batch)"), dialog.spn_batch))
    dialog.cmb_scene_sort = _scene_sort_combo()
    dialog.spn_back = _spin(0, 3000, 500, width=88)
    right_col.addWidget(_field_row(dialog, tr(dialog, "백시크(ms)"), dialog.spn_back))
    dialog.chk_use_cache = QtWidgets.QCheckBox(tr(dialog, "이 옵션으로 이전 결과 재사용"))
    dialog.chk_use_cache.setChecked(True)
    right_col.addWidget(dialog.chk_use_cache)
    row = ResponsiveSplitWidget(
        left,
        right,
        breakpoint=860,
        spacing=12,
        first_stretch=1,
        second_stretch=1,
        parent=widget,
    )
    row.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
    layout.addWidget(row)
    return widget


def _scene_sort_combo():
    combo = QtWidgets.QComboBox()
    combo.addItem("시간순", "time")
    combo.addItem("점수순", "score")
    return combo


def _scan_section_box(dialog, title: str, content: QtWidgets.QWidget):
    return CollapsibleSectionBox(title, content, parent=dialog, expanded=True)


def _scan_action_hint(dialog):
    label = QtWidgets.QLabel(
        tr(dialog, "캐시가 있으면 즉시 표시하고, 없으면 새로 계산합니다.")
    )
    label.setWordWrap(True)
    label.setStyleSheet("color:#8aa;")
    return label


def _scan_group_layout(widget):
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    return layout


def _field_row(dialog, label_text: str, field):
    widget = QtWidgets.QWidget(dialog)
    row = QtWidgets.QHBoxLayout(widget)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    label = QtWidgets.QLabel(label_text)
    label.setMinimumWidth(108)
    row.addWidget(label)
    row.addWidget(field)
    row.addStretch(1)
    return widget


def _spin(minimum: int, maximum: int, value: int, width: int | None = None):
    spin = QtWidgets.QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setValue(value)
    if width is not None:
        spin.setFixedWidth(width)
    return spin


def _double_spin(minimum: float, maximum: float, step: float, value: float, width: int | None = None):
    spin = QtWidgets.QDoubleSpinBox()
    spin.setDecimals(2)
    spin.setRange(minimum, maximum)
    spin.setSingleStep(step)
    spin.setValue(value)
    if width is not None:
        spin.setFixedWidth(width)
    return spin
