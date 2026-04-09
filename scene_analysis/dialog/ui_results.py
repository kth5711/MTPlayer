from PyQt6 import QtCore, QtWidgets

from .ui_responsive import ResponsiveSplitWidget

RESULT_ICON_SIZE = QtCore.QSize(160, 90)
SCENE_FRAME_PREVIEW_ITEM_SIZE = QtCore.QSize(166, 114)
SCENE_FRAME_PREVIEW_HEIGHT = 147


def build_common_actions_section(dialog, layout) -> None:
    row = QtWidgets.QHBoxLayout()
    row.addWidget(QtWidgets.QLabel("정렬"))
    dialog.cmb_scene_sort.setMinimumWidth(92)
    row.addWidget(dialog.cmb_scene_sort)
    row.addSpacing(8)
    dialog.btn_cache_history = QtWidgets.QPushButton("결과기록")
    dialog.btn_cache_history.setMinimumHeight(30)
    row.addWidget(dialog.btn_cache_history)
    row.addSpacing(8)
    dialog.btn_scan_batch = QtWidgets.QPushButton("순차 작업")
    dialog.btn_scan_batch.setMinimumHeight(30)
    row.addWidget(dialog.btn_scan_batch)
    row.addStretch(1)
    layout.addLayout(row)


def build_results_section(dialog, layout) -> None:
    _init_scene_tooltips(dialog)
    layout.addLayout(_status_row(dialog))
    layout.addWidget(_results_list(dialog), 1)
    layout.addLayout(_scene_clip_row(dialog))
    layout.addWidget(_scene_frames_row(dialog))
    layout.addWidget(_scene_frame_preview(dialog))
    layout.addWidget(_scene_nudge_row(dialog))
    layout.addLayout(_progress_row(dialog))


def _init_scene_tooltips(dialog) -> None:
    dialog._scene_ab_tooltip_manual = "프레임셋/씬 결과에서 서로 다른 2개 시점을 선택해\n현재 타일의 A/B 구간으로 설정"
    dialog._scene_ab_tooltip_group = "선택된 구간묶음 씬 1개의 범위를\n현재 타일의 A/B 구간으로 설정"
    dialog._scene_clip_tooltip_manual = "프레임셋/씬 결과에서 서로 다른 2개 시점을 선택해\n수동 구간 클립으로 저장"
    dialog._scene_clip_tooltip_group = "선택된 구간묶음 씬을 클립으로 저장\n(다중 선택 기본=개별 저장, [다중 묶음 합치기] 체크=1개 병합)"
    dialog._scene_gif_tooltip_manual = "프레임셋/씬 결과에서 서로 다른 2개 시점을 선택해\n수동 구간 GIF로 저장"
    dialog._scene_gif_tooltip_single = "선택된 구간묶음 씬 1개를 GIF로 저장\n또는 씬/프레임셋에서 서로 다른 2개 시점을 선택해 저장"
    dialog._scene_gif_tooltip_multi = "GIF는 현재 1개 구간만 저장합니다.\n구간묶음 씬은 1개만 선택하거나 수동 구간을 선택하세요."


def _status_row(dialog):
    row = QtWidgets.QHBoxLayout()
    dialog.lbl_status = QtWidgets.QLabel("옵션 설정 후 [탐색 실행].  더블클릭/Enter: 이동 · 방향키: 탐색")
    dialog.lbl_status.setStyleSheet("color:#8aa;")
    row.addWidget(dialog.lbl_status)
    row.addStretch(1)
    return row


def _results_list(dialog):
    dialog.listw = QtWidgets.QListWidget(dialog)
    dialog.listw.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
    dialog.listw.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
    dialog.listw.setIconSize(RESULT_ICON_SIZE)
    dialog.listw.setMovement(QtWidgets.QListView.Movement.Static)
    dialog.listw.setSpacing(6)
    dialog.listw.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
    dialog.listw.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
    dialog.listw.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    dialog.listw.installEventFilter(dialog)
    return dialog.listw


def _scene_clip_row(dialog):
    row = QtWidgets.QHBoxLayout()
    dialog.btn_scene_set_ab = QtWidgets.QPushButton("타일 A/B 설정")
    dialog.btn_scene_set_ab.setEnabled(False)
    dialog.btn_scene_set_ab.setToolTip(dialog._scene_ab_tooltip_manual)
    dialog.btn_scene_clip_save = QtWidgets.QPushButton("선택구간 클립")
    dialog.btn_scene_clip_save.setEnabled(False)
    dialog.btn_scene_clip_save.setToolTip(dialog._scene_clip_tooltip_manual)
    dialog.btn_scene_gif_save = QtWidgets.QPushButton("선택구간 GIF")
    dialog.btn_scene_gif_save.setEnabled(False)
    dialog.btn_scene_gif_save.setToolTip(dialog._scene_gif_tooltip_manual)
    dialog.chk_scene_clip_merge = QtWidgets.QCheckBox("다중 묶음 합치기")
    dialog.chk_scene_clip_merge.setChecked(False)
    dialog.chk_scene_clip_merge.setEnabled(False)
    dialog.chk_scene_clip_merge.setToolTip("구간묶음 씬을 2개 이상 선택한 경우\n체크 시 선택 구간들만 이어붙여 1개 클립으로 저장합니다.")
    for widget in (dialog.btn_scene_set_ab, dialog.btn_scene_clip_save, dialog.btn_scene_gif_save, dialog.chk_scene_clip_merge):
        row.addWidget(widget)
    row.addStretch(1)
    return row


def _scene_frames_row(dialog):
    row = ResponsiveSplitWidget(
        _scene_frames_option_group(dialog),
        _scene_frames_action_group(dialog),
        breakpoint=920,
        spacing=10,
        first_stretch=1,
        second_stretch=0,
        parent=dialog,
    )
    row.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
    return row


def _scene_frame_preview(dialog):
    dialog.lst_scene_frame_preview = _preview_list(dialog)
    return dialog.lst_scene_frame_preview


def _scene_nudge_row(dialog):
    row = QtWidgets.QHBoxLayout()
    dialog.btn_scene_frame_shift_prev = QtWidgets.QPushButton("-")
    dialog.btn_scene_frame_shift_prev.setFixedWidth(52)
    row.addWidget(dialog.btn_scene_frame_shift_prev)
    row.addWidget(QtWidgets.QLabel("프레임수"))
    dialog.spn_scene_frame_shift_count = _spin(1, 10, 1, 72)
    row.addWidget(dialog.spn_scene_frame_shift_count)
    row.addWidget(QtWidgets.QLabel("스탭수"))
    dialog.spn_scene_frame_shift_step = _spin(1, 10, 1, 72)
    row.addWidget(dialog.spn_scene_frame_shift_step)
    dialog.btn_scene_frame_shift_next = QtWidgets.QPushButton("+")
    dialog.btn_scene_frame_shift_next.setFixedWidth(52)
    row.addWidget(dialog.btn_scene_frame_shift_next)
    row.addStretch(1)
    widget = QtWidgets.QWidget(dialog)
    widget.setLayout(row)
    return widget


def _progress_row(dialog):
    row = QtWidgets.QHBoxLayout()
    dialog.progress = QtWidgets.QProgressBar()
    dialog.progress.setRange(0, 100)
    dialog.progress.setValue(0)
    dialog.progress.setFormat("%p%")
    dialog.btn_cancel = QtWidgets.QPushButton("취소")
    dialog.btn_cancel.setEnabled(False)
    row.addWidget(dialog.progress, 1)
    row.addWidget(dialog.btn_cancel)
    return row


def _preview_list(dialog):
    widget = QtWidgets.QListWidget()
    widget.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
    widget.setMovement(QtWidgets.QListView.Movement.Static)
    widget.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
    widget.setWrapping(False)
    widget.setSpacing(4)
    widget.setIconSize(RESULT_ICON_SIZE)
    widget.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
    widget.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
    widget.setFixedHeight(SCENE_FRAME_PREVIEW_HEIGHT)
    return widget


def _scene_frames_option_group(dialog):
    widget = QtWidgets.QWidget(dialog)
    row = QtWidgets.QHBoxLayout(widget)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    row.addWidget(QtWidgets.QLabel("선택컷 프레임셋"))
    dialog.spn_scene_frame_secs = _spin(1, 10, 3, 72)
    row.addWidget(dialog.spn_scene_frame_secs)
    dialog.chk_scene_frame_preview = QtWidgets.QCheckBox("프레임셋 보기")
    dialog.chk_scene_frame_preview.setChecked(False)
    row.addWidget(dialog.chk_scene_frame_preview)
    dialog.chk_scene_frame_prev = QtWidgets.QCheckBox("이전프레임")
    dialog.chk_scene_frame_prev.setChecked(False)
    row.addWidget(dialog.chk_scene_frame_prev)
    row.addStretch(1)
    return widget


def _scene_frames_action_group(dialog):
    widget = QtWidgets.QWidget(dialog)
    row = QtWidgets.QHBoxLayout(widget)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    dialog.btn_scene_frame_save = QtWidgets.QPushButton("선택프레임 저장")
    row.addWidget(dialog.btn_scene_frame_save)
    dialog.btn_scene_bookmark_add = QtWidgets.QPushButton("북마크 추가")
    dialog.btn_scene_bookmark_add.setEnabled(False)
    row.addWidget(dialog.btn_scene_bookmark_add)
    row.addStretch(1)
    return widget


def _spin(minimum: int, maximum: int, value: int, width: int):
    spin = QtWidgets.QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setValue(value)
    spin.setMinimumWidth(width)
    return spin
