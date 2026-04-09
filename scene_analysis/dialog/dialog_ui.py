from PyQt6 import QtWidgets

from .ui_refilter_controls import build_refilter_control_sections
from .ui_refilter_samples import build_refilter_sample_section
from .ui_results import build_common_actions_section, build_results_section
from .ui_runtime import connect_scene_dialog_signals, init_scene_dialog_runtime_state, start_scene_dialog_workers
from .ui_scan import build_scan_options_section


def build_scene_dialog_ui(dialog, host) -> None:
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.addWidget(_scene_tabs(dialog, host))
    build_common_actions_section(dialog, layout)
    build_results_section(dialog, layout)
    connect_scene_dialog_signals(dialog)
    start_scene_dialog_workers(dialog)
    init_scene_dialog_runtime_state(dialog)
    _initialize_scene_dialog_state(dialog)


def _scene_tabs(dialog, host):
    tabs = QtWidgets.QTabWidget(dialog)
    tabs.setDocumentMode(True)
    tabs.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
    dialog.tabs_scene_controls = tabs
    tabs.addTab(_scan_tab(dialog, host), "씬변화")
    tabs.addTab(_refilter_tab(dialog), "유사씬")
    return tabs


def _scan_tab(dialog, host):
    tab = QtWidgets.QWidget()
    layout = _tab_layout(tab)
    build_scan_options_section(dialog, host, layout)
    layout.addStretch(1)
    return tab


def _refilter_tab(dialog):
    tab = QtWidgets.QWidget()
    layout = _tab_layout(tab)
    build_refilter_control_sections(dialog, layout)
    build_refilter_sample_section(dialog, layout)
    layout.addStretch(1)
    return tab


def _tab_layout(tab):
    layout = QtWidgets.QVBoxLayout(tab)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)
    return layout


def _initialize_scene_dialog_state(dialog):
    dialog._apply_weight_profile("balanced")
    dialog._update_hybrid_weight_label()
    dialog._on_refilter_agg_changed()
    dialog._on_refilter_mode_changed()
    dialog._on_refilter_source_mode_changed()
    dialog._on_refilter_sampling_mode_changed()
    dialog._on_siglip_two_stage_changed()
    dialog._update_ref_image_text()
    dialog.resize(980, 720)
