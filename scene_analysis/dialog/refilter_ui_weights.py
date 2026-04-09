import logging

from scene_analysis.core.similarity import (
    POSE_COMP_KEYS,
    POSE_COMP_PROFILES,
    _normalize_pose_weights,
)


logger = logging.getLogger(__name__)


def current_hybrid_siglip_weight(dialog) -> float:
    return max(0.0, min(1.0, float(dialog.sld_hybrid_siglip.value()) / 100.0))


def update_hybrid_weight_label(dialog) -> None:
    dialog.lbl_hybrid_siglip.setText(f"{dialog._current_hybrid_siglip_weight():.2f}")


def on_hybrid_weight_changed(dialog, *_args) -> None:
    dialog._update_hybrid_weight_label()


def on_refilter_mode_changed(dialog, *_args) -> None:
    dialog.cmb_refilter_mode.setEnabled(False)
    dialog.edt_siglip_adapter.setEnabled(True)
    dialog.btn_pick_siglip_adapter.setEnabled(True)
    dialog.sld_hybrid_siglip.setEnabled(False)
    for slider in dialog.weight_sliders.values():
        slider.setEnabled(False)
    dialog.lbl_hybrid_title.setVisible(False)
    dialog.sld_hybrid_siglip.setVisible(False)
    dialog.lbl_hybrid_siglip.setVisible(False)
    _hide_pose_controls(dialog)
    dialog._update_hybrid_weight_label()
    dialog._on_refilter_source_mode_changed()
    dialog._on_refilter_sampling_mode_changed()
    dialog._on_refilter_agg_changed()


def current_pose_weights(dialog) -> dict[str, float]:
    raw = {}
    for key in POSE_COMP_KEYS:
        slider = dialog.weight_sliders.get(key)
        raw[key] = float(slider.value()) if slider is not None else 0.0
    return _normalize_pose_weights(raw)


def update_weight_value_labels(dialog) -> None:
    weights = dialog._current_pose_weights()
    for key in POSE_COMP_KEYS:
        label = dialog.weight_value_labels.get(key)
        if label is not None:
            label.setText(f"{weights.get(key, 0.0):.2f}")


def apply_weight_profile(dialog, profile_name: str) -> None:
    preset = POSE_COMP_PROFILES.get(profile_name)
    if not preset:
        return
    dialog._updating_weight_ui = True
    try:
        for key in POSE_COMP_KEYS:
            slider = dialog.weight_sliders.get(key)
            if slider is not None:
                slider.setValue(int(round(float(preset.get(key, 0.0)) * 100)))
        dialog._update_weight_value_labels()
        index = dialog.cmb_weight_profile.findData(profile_name)
        if index >= 0 and dialog.cmb_weight_profile.currentIndex() != index:
            dialog.cmb_weight_profile.setCurrentIndex(index)
    finally:
        dialog._updating_weight_ui = False


def on_weight_profile_changed(dialog, *_args) -> None:
    if dialog._updating_weight_ui:
        return
    profile_name = dialog.cmb_weight_profile.currentData()
    if profile_name == "custom":
        dialog._update_weight_value_labels()
        return
    if isinstance(profile_name, str):
        dialog._apply_weight_profile(profile_name)
    dialog._update_weight_value_labels()


def on_weight_slider_changed(dialog, _key: str) -> None:
    dialog._update_weight_value_labels()
    if dialog._updating_weight_ui:
        return
    index = dialog.cmb_weight_profile.findData("custom")
    if index >= 0 and dialog.cmb_weight_profile.currentIndex() != index:
        dialog._updating_weight_ui = True
        try:
            dialog.cmb_weight_profile.setCurrentIndex(index)
        finally:
            dialog._updating_weight_ui = False


def _hide_pose_controls(dialog) -> None:
    for key in POSE_COMP_KEYS:
        title = dialog.weight_title_labels.get(key)
        slider = dialog.weight_sliders.get(key)
        value = dialog.weight_value_labels.get(key)
        if title is not None:
            title.setVisible(False)
        if slider is not None:
            slider.setVisible(False)
        if value is not None:
            value.setVisible(False)
