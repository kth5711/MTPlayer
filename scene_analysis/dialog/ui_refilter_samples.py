from PyQt6 import QtCore, QtWidgets

from i18n import tr
from .ui_responsive import CollapsibleSectionBox, ResponsiveSplitWidget


def build_refilter_sample_section(dialog, layout) -> None:
    layout.addWidget(_sample_box(dialog))
    layout.addLayout(_refilter_action_row(dialog))


def _sample_box(dialog):
    split = ResponsiveSplitWidget(
        _sample_image_column(dialog),
        _sample_text_column(dialog),
        breakpoint=920,
        spacing=8,
        first_stretch=5,
        second_stretch=4,
        parent=dialog,
    )
    split.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
    return CollapsibleSectionBox(tr(dialog, "샘플"), split, parent=dialog, expanded=True)


def _sample_image_column(dialog):
    widget = QtWidgets.QWidget(dialog)
    col = QtWidgets.QVBoxLayout(widget)
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(6)
    col.addLayout(_sample_image_buttons(dialog))
    col.addWidget(_sample_image_list(dialog), 1)
    return widget


def _sample_image_buttons(dialog):
    row = QtWidgets.QHBoxLayout()
    dialog.btn_pick_ref = QtWidgets.QPushButton(tr(dialog, "추가"))
    dialog.btn_pick_ref.setToolTip(tr(dialog, "샘플 이미지를 현재 목록에 추가"))
    dialog.btn_remove_ref = QtWidgets.QPushButton(tr(dialog, "삭제"))
    dialog.btn_remove_ref.setToolTip(tr(dialog, "선택한 샘플 이미지만 목록에서 제거"))
    dialog.btn_remove_ref.setEnabled(False)
    dialog.btn_clear_ref = QtWidgets.QPushButton(tr(dialog, "비우기"))
    dialog.btn_clear_ref.setToolTip(tr(dialog, "현재 샘플 이미지 목록 비우기"))
    dialog.btn_clear_ref.setEnabled(False)
    for button in (dialog.btn_pick_ref, dialog.btn_remove_ref, dialog.btn_clear_ref):
        button.setMinimumHeight(30)
        row.addWidget(button)
    row.addStretch(1)
    return row


def _sample_image_list(dialog):
    dialog.lst_ref_img = QtWidgets.QListWidget()
    dialog.lst_ref_img.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
    dialog.lst_ref_img.setMovement(QtWidgets.QListView.Movement.Static)
    dialog.lst_ref_img.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
    dialog.lst_ref_img.setWrapping(False)
    dialog.lst_ref_img.setSpacing(4)
    dialog.lst_ref_img.setIconSize(QtCore.QSize(96, 60))
    dialog.lst_ref_img.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    dialog.lst_ref_img.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
    dialog.lst_ref_img.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
    dialog.lst_ref_img.setFixedHeight(86)
    return dialog.lst_ref_img


def _sample_text_column(dialog):
    widget = QtWidgets.QWidget(dialog)
    col = QtWidgets.QVBoxLayout(widget)
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(6)
    col.addWidget(_sample_text_top_spacer(dialog))
    dialog.edt_ref_text = QtWidgets.QPlainTextEdit()
    dialog.edt_ref_text.setPlaceholderText(tr(dialog, "텍스트 샘플 1줄 1개\n예: person kneeling, side view"))
    dialog.edt_ref_text.setToolTip(
        tr(dialog, "텍스트 샘플을 한 줄에 하나씩 입력합니다.\nSigLIP2에서 텍스트 샘플로 함께 사용됩니다.")
    )
    dialog.edt_ref_text.setFixedHeight(86)
    col.addWidget(dialog.edt_ref_text, 1)
    return widget


def _sample_text_top_spacer(dialog):
    spacer = QtWidgets.QWidget(dialog)
    spacer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
    spacer.setFixedHeight(30)
    return spacer


def _refilter_action_row(dialog):
    row = QtWidgets.QHBoxLayout()
    dialog.btn_refilter = QtWidgets.QPushButton(tr(dialog, "유사씬 탐색"))
    dialog.btn_refilter.setMinimumHeight(34)
    dialog.btn_refilter.setMinimumWidth(140)
    dialog.btn_refilter_clear = QtWidgets.QPushButton(tr(dialog, "유사씬 해제"))
    dialog.btn_refilter_clear.setMinimumHeight(34)
    dialog.btn_refilter_clear.setEnabled(False)
    row.addWidget(dialog.btn_refilter)
    row.addWidget(dialog.btn_refilter_clear)
    row.addWidget(_refilter_action_hint(dialog))
    row.addStretch(1)
    return row


def _refilter_action_hint(dialog):
    label = QtWidgets.QLabel(tr(dialog, "현재 결과 또는 직행 샘플을 기준으로 다시 점수화합니다."))
    label.setWordWrap(True)
    label.setStyleSheet("color:#8aa;")
    return label
