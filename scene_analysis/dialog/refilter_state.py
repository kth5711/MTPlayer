def set_refilter_running(dialog, running: bool, *, source_mode: str, uses_frame_profile: bool, agg_mode: str) -> None:
    _set_common_controls(dialog, running)
    _set_refilter_controls(dialog, running, source_mode, uses_frame_profile, agg_mode)
    if not running:
        dialog._update_ref_image_actions()
        dialog._update_scene_clip_button_enabled()


def _set_common_controls(dialog, running: bool):
    dialog.btn_cancel.setEnabled(bool(running))
    _set_primary_group(dialog, running)
    _set_secondary_group(dialog, running)
    _set_optional_controls(dialog, running)
    _set_ref_image_buttons(dialog, running)


def _set_primary_group(dialog, running: bool):
    _set_toggle_group(dialog, running, (
        "btn_refilter",
        "btn_pick_ref",
        "lst_ref_img",
        "edt_ref_text",
        "spn_scene_frame_secs",
        "chk_scene_frame_prev",
        "spn_scene_frame_shift_count",
        "spn_scene_frame_shift_step",
        "chk_scene_frame_preview",
        "btn_scene_frame_shift_prev",
        "btn_scene_frame_shift_next",
        "btn_scene_clip_save",
        "btn_scene_set_ab",
        "btn_scene_gif_save",
        "chk_scene_clip_merge",
        "btn_scene_frame_save",
        "lst_scene_frame_preview",
    ))


def _set_secondary_group(dialog, running: bool):
    _set_toggle_group(dialog, running, (
        "cmb_refilter_source",
        "edt_siglip_adapter",
        "btn_pick_siglip_adapter",
        "cmb_refilter_sampling",
        "chk_siglip_two_stage",
        "cmb_siglip_decode_scale",
        "cmb_refilter_agg",
        "btn_cache_history",
        "cmb_scene_sort",
    ))


def _set_toggle_group(dialog, running: bool, widget_names):
    for widget_name in widget_names:
        getattr(dialog, widget_name).setEnabled(not running)


def _set_optional_controls(dialog, running: bool):
    if hasattr(dialog, "btn_scene_bookmark_add"):
        dialog.btn_scene_bookmark_add.setEnabled(not running)
    if hasattr(dialog, "btn_scan_batch"):
        dialog.btn_scan_batch.setEnabled(not running)
    dialog.cmb_refilter_mode.setEnabled(False)
    dialog.sld_hybrid_siglip.setEnabled(False)
    for slider in dialog.weight_sliders.values():
        slider.setEnabled(False)


def _set_ref_image_buttons(dialog, running: bool):
    if hasattr(dialog, "btn_remove_ref"):
        dialog.btn_remove_ref.setEnabled(False if running else bool(dialog._selected_ref_image_paths()))
    if hasattr(dialog, "btn_clear_ref"):
        dialog.btn_clear_ref.setEnabled(False if running else bool(getattr(dialog, "sample_image_paths", [])))


def _set_refilter_controls(dialog, running: bool, source_mode: str, uses_frame_profile: bool, agg_mode: str):
    dialog.spn_siglip_stage2_ratio.setEnabled((not running) and bool(dialog.chk_siglip_two_stage.isChecked()))
    dialog.spn_refilter_direct_sec.setEnabled((not running) and source_mode == "direct")
    dialog.chk_refilter_direct_group.setEnabled((not running) and source_mode == "direct")
    dialog.spn_refilter_direct_group_band.setEnabled(
        (not running) and source_mode == "direct" and bool(dialog.chk_refilter_direct_group.isChecked())
    )
    dialog.cmb_frame_profile.setEnabled((not running) and uses_frame_profile)
    dialog.spn_kofn_k.setEnabled((not running) and agg_mode == "kofn")
    dialog.btn_refilter_clear.setEnabled((not running) and dialog._refilter_active)
