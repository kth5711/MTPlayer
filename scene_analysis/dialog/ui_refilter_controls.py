from PyQt6 import QtCore, QtWidgets

from i18n import tr
from scene_analysis.core.similarity import DEFAULT_SIGLIP2_MODEL_ID, POSE_COMP_KEYS, POSE_COMP_LABELS, POSE_COMP_PROFILES, _siglip2_default_adapter_path
from .ui_responsive import CollapsibleSectionBox, ResponsiveSplitWidget, bind_equal_section_heights


def build_refilter_control_sections(dialog, layout) -> None:
    dialog.cmb_refilter_mode = QtWidgets.QComboBox(dialog)
    dialog.cmb_refilter_mode.addItem("SigLIP2", "siglip2")
    dialog.cmb_refilter_mode.setEnabled(False)
    dialog.cmb_refilter_mode.setVisible(False)
    layout.addWidget(_refilter_primary_row(dialog))
    layout.addWidget(_hidden_weight_panel(dialog))


def _refilter_primary_row(dialog):
    settings_box = _refilter_section_box(dialog, tr(dialog, "탐색 설정"), _refilter_settings_group(dialog))
    filter_box = _refilter_section_box(dialog, tr(dialog, "필터 옵션"), _refilter_filter_group(dialog))
    row = ResponsiveSplitWidget(
        settings_box,
        filter_box,
        breakpoint=920,
        spacing=12,
        first_stretch=1,
        second_stretch=1,
        parent=dialog,
    )
    row.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
    row._equal_height_binder = bind_equal_section_heights(row, settings_box, filter_box)
    return row


def _refilter_settings_group(dialog):
    widget = QtWidgets.QWidget(dialog)
    col = _refilter_group_layout(widget)
    dialog.lbl_siglip_model = QtWidgets.QLabel(DEFAULT_SIGLIP2_MODEL_ID)
    dialog.lbl_siglip_model.setToolTip(DEFAULT_SIGLIP2_MODEL_ID)
    col.addWidget(_field_row(dialog, "모델", dialog.lbl_siglip_model))
    dialog.cmb_refilter_sampling = _sampling_combo(dialog)
    dialog.cmb_refilter_sampling.setMinimumWidth(168)
    col.addWidget(_field_row(dialog, "방식", dialog.cmb_refilter_sampling))
    dialog.cmb_refilter_source = _source_combo(dialog)
    dialog.cmb_refilter_source.setMinimumWidth(132)
    col.addWidget(_field_row(dialog, "대상", dialog.cmb_refilter_source))
    dialog.spn_refilter_direct_sec = _spin(1, 120, 2)
    dialog.spn_refilter_direct_sec.setToolTip("직행 샘플 모드에서 샘플 간격(초)")
    dialog.spn_refilter_direct_sec.setMinimumWidth(84)
    col.addWidget(_field_row(dialog, "간격(s)", dialog.spn_refilter_direct_sec))
    dialog.cmb_frame_profile = _frame_profile_combo()
    dialog.cmb_frame_profile.setMinimumWidth(132)
    col.addWidget(_field_row(dialog, "샷", dialog.cmb_frame_profile))
    dialog.cmb_siglip_decode_scale = QtWidgets.QComboBox()
    dialog.cmb_siglip_decode_scale.addItem("원본", -1)
    dialog.cmb_siglip_decode_scale.addItem("품질(420)", 420)
    dialog.cmb_siglip_decode_scale.addItem("속도(224)", 224)
    dialog.cmb_siglip_decode_scale.setMinimumWidth(180)
    col.addWidget(_field_row(dialog, "프레임 처리 크기", dialog.cmb_siglip_decode_scale))
    col.addWidget(_field_row(dialog, "LoRA 어댑터", _adapter_widget(dialog)))
    return widget


def _sampling_combo(dialog):
    combo = QtWidgets.QComboBox()
    combo.addItem("패스트(씬시작 1샷)", "start_frame")
    combo.addItem("구간 샘플링", "scene_window")
    combo.setCurrentIndex(1)
    combo.setToolTip("재필터 프레임 추출 방식\n- 패스트(씬시작 1샷): 씬 시작점 1프레임만 빠르게 비교\n- 구간 샘플링: 씬 시작~다음 씬 전 구간 균등 샘플")
    return combo


def _source_combo(dialog):
    combo = QtWidgets.QComboBox()
    combo.addItem("씬변화 결과", "scene")
    combo.addItem("직행 샘플", "direct")
    combo.setCurrentIndex(1)
    combo.setToolTip("재필터 입력 시점 선택\n- 씬변화 결과: 현재 결과를 대상으로 실행\n- 직행 샘플: 씬변화 없이 영상 전체를 간격 샘플링")
    return combo


def _frame_profile_combo():
    combo = QtWidgets.QComboBox()
    combo.addItem("기본(3)", "normal")
    combo.addItem("확장(5)", "wide")
    combo.addItem("고성능(9)", "high")
    combo.setCurrentIndex(0)
    combo.setToolTip("구간 샘플링 최소 샷 수")
    return combo


def _refilter_filter_group(dialog):
    widget = QtWidgets.QWidget(dialog)
    col = _refilter_group_layout(widget)
    dialog.spn_sim_thr = QtWidgets.QDoubleSpinBox()
    dialog.spn_sim_thr.setRange(0.0, 1.0)
    dialog.spn_sim_thr.setDecimals(2)
    dialog.spn_sim_thr.setSingleStep(0.05)
    dialog.spn_sim_thr.setValue(0.85)
    dialog.spn_sim_thr.setKeyboardTracking(False)
    dialog.spn_sim_thr.setMinimumWidth(84)
    col.addWidget(_field_row(dialog, "유사도 임계값", dialog.spn_sim_thr))
    col.addWidget(_two_stage_row(dialog))
    col.addWidget(_aggregate_row(dialog))
    col.addWidget(_direct_group_row(dialog))
    return widget


def _two_stage_row(dialog):
    widget = QtWidgets.QWidget(dialog)
    row = QtWidgets.QHBoxLayout(widget)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    dialog.chk_siglip_two_stage = QtWidgets.QCheckBox("SigLIP2 2단계")
    row.addWidget(dialog.chk_siglip_two_stage)
    row.addWidget(QtWidgets.QLabel("2차 비율%"))
    dialog.spn_siglip_stage2_ratio = _spin(10, 100, 35, width=60)
    row.addWidget(dialog.spn_siglip_stage2_ratio)
    row.addStretch(1)
    return widget


def _aggregate_row(dialog):
    widget = QtWidgets.QWidget(dialog)
    row = QtWidgets.QHBoxLayout(widget)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    row.addWidget(QtWidgets.QLabel("집계"))
    dialog.cmb_refilter_agg = QtWidgets.QComboBox()
    dialog.cmb_refilter_agg.addItem("최고값", "max")
    dialog.cmb_refilter_agg.addItem("K-of-N", "kofn")
    row.addWidget(dialog.cmb_refilter_agg)
    row.addWidget(QtWidgets.QLabel("K"))
    dialog.spn_kofn_k = _spin(1, 32, 2)
    row.addWidget(dialog.spn_kofn_k)
    row.addStretch(1)
    return widget


def _direct_group_row(dialog):
    widget = QtWidgets.QWidget(dialog)
    row = QtWidgets.QHBoxLayout(widget)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    dialog.chk_refilter_direct_group = QtWidgets.QCheckBox("직행 결과 구간 묶기(씬클립)")
    dialog.chk_refilter_direct_group.setChecked(True)
    row.addWidget(dialog.chk_refilter_direct_group)
    row.addWidget(QtWidgets.QLabel("폭"))
    dialog.spn_refilter_direct_group_band = QtWidgets.QDoubleSpinBox()
    dialog.spn_refilter_direct_group_band.setRange(0.01, 0.20)
    dialog.spn_refilter_direct_group_band.setDecimals(2)
    dialog.spn_refilter_direct_group_band.setSingleStep(0.01)
    dialog.spn_refilter_direct_group_band.setValue(0.05)
    dialog.spn_refilter_direct_group_band.setKeyboardTracking(False)
    dialog.spn_refilter_direct_group_band.setMinimumWidth(68)
    dialog.spn_refilter_direct_group_band.setToolTip("직행 결과 구간 묶기 점수폭\n같은 연속 run 안에서 이 값 이하 차이면 같은 그룹으로 묶음")
    row.addWidget(dialog.spn_refilter_direct_group_band)
    row.addStretch(1)
    return widget

def _adapter_widget(dialog):
    widget = QtWidgets.QWidget(dialog)
    row = QtWidgets.QHBoxLayout(widget)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    dialog.edt_siglip_adapter = QtWidgets.QLineEdit()
    env_adapter = _siglip2_default_adapter_path()
    if env_adapter:
        dialog.edt_siglip_adapter.setText(env_adapter)
    dialog.edt_siglip_adapter.setPlaceholderText("선택 사항: SigLIP2 LoRA 어댑터 폴더")
    row.addWidget(dialog.edt_siglip_adapter, 1)
    dialog.btn_pick_siglip_adapter = QtWidgets.QPushButton("어댑터 선택")
    row.addWidget(dialog.btn_pick_siglip_adapter)
    return widget


def _refilter_section_box(dialog, title: str, content: QtWidgets.QWidget):
    return CollapsibleSectionBox(title, content, parent=dialog, expanded=True)


def _refilter_group_layout(widget):
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


def _hidden_weight_panel(dialog):
    widget = QtWidgets.QWidget(dialog)
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addLayout(_hybrid_weight_row(dialog))
    layout.addLayout(_pose_weight_row(dialog))
    widget.setVisible(False)
    return widget


def _hybrid_weight_row(dialog):
    row = QtWidgets.QHBoxLayout()
    dialog.cmb_weight_profile = _weight_profile_combo(dialog)
    dialog.lbl_hybrid_title = QtWidgets.QLabel("하이브리드 SigLIP 비중")
    row.addWidget(dialog.lbl_hybrid_title)
    dialog.sld_hybrid_siglip = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    dialog.sld_hybrid_siglip.setRange(0, 100)
    dialog.sld_hybrid_siglip.setValue(55)
    dialog.lbl_hybrid_siglip = QtWidgets.QLabel("0.55")
    dialog.lbl_hybrid_siglip.setMinimumWidth(42)
    row.addWidget(dialog.sld_hybrid_siglip)
    row.addWidget(dialog.lbl_hybrid_siglip)
    row.addStretch(1)
    return row


def _weight_profile_combo(dialog):
    combo = QtWidgets.QComboBox(dialog)
    combo.addItem("행동 우선", "action")
    combo.addItem("균형", "balanced")
    combo.addItem("구도 우선", "composition")
    combo.addItem("커스텀", "custom")
    combo.setCurrentIndex(1)
    combo.setVisible(False)
    return combo


def _pose_weight_row(dialog):
    row = QtWidgets.QHBoxLayout()
    dialog.weight_title_labels = {}
    dialog.weight_sliders = {}
    dialog.weight_value_labels = {}
    for key in POSE_COMP_KEYS:
        row.addWidget(_weight_label(dialog, key))
        row.addWidget(_weight_slider(dialog, key))
        row.addWidget(dialog.weight_value_labels[key])
        row.addSpacing(6)
    row.addStretch(1)
    return row


def _weight_label(dialog, key: str):
    label = QtWidgets.QLabel(POSE_COMP_LABELS.get(key, key))
    dialog.weight_title_labels[key] = label
    return label


def _weight_slider(dialog, key: str):
    slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(int(round(POSE_COMP_PROFILES["balanced"][key] * 100)))
    dialog.weight_sliders[key] = slider
    value_label = QtWidgets.QLabel("0.00")
    value_label.setMinimumWidth(42)
    dialog.weight_value_labels[key] = value_label
    return slider


def _spin(minimum: int, maximum: int, value: int, width: int | None = None):
    spin = QtWidgets.QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setValue(value)
    if width is not None:
        spin.setFixedWidth(width)
    return spin
