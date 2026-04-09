from importlib import import_module


_EXPORT_GROUPS = {
    ".batch_dialog": ("open_scene_batch_dialog",),
    ".dialog_lifecycle": (
        "begin_async_thumbnail_close",
        "close_event",
        "continue_close_after_thumbnail_workers",
        "prepare_thumbnail_workers_for_close",
        "shutdown_for_app_close",
        "thumbnail_workers_running",
        "wait_for_worker_stopped",
    ),
    ".dialog_entry": (
        "open_scene_dialog_with_options",
        "refilter_cache_clear_all_public",
        "refilter_cache_clear_for_current",
        "scene_cache_clear_all_public",
        "scene_cache_clear_for_current",
    ),
    ".dialog_ui": ("build_scene_dialog_ui",),
    ".export": (
        "add_selected_scene_results_to_bookmarks",
        "enqueue_clip_export_job",
        "on_clip_job_failed",
        "on_clip_job_finished",
        "on_clip_worker_busy_changed",
        "save_selected_scene_range_clip",
        "save_selected_scene_range_gif",
        "save_selected_scene_result_shots",
        "selected_clip_range_ms",
        "selected_clip_ranges_for_save",
        "selected_grouped_scene_clip_ranges",
        "selected_ms_from_items",
        "selected_scene_ms_list_for_save",
        "set_selected_scene_range_ab",
        "update_scene_clip_button_enabled",
    ),
    ".history_actions": (
        "delete_selected_cache_history_entries",
        "dispatch_cache_history_entry_load",
        "load_selected_cache_history_entry",
        "request_cache_history_entry_load",
        "schedule_cache_history_refresh",
    ),
    ".history_apply_refilter": ("load_refilter_cache_entry", "load_siglip_feature_cache_entry"),
    ".history_apply_scene": ("load_scene_cache_entry",),
    ".history_dialog": ("cache_history_dialog_closed", "open_cache_history_dialog"),
    ".history_refresh": ("refresh_cache_history_dialog",),
    ".history_shared": ("cache_history_selected_entries",),
    ".lazy_loading": ("check_and_load_more", "load_next_batch"),
    ".preview_display": ("show_selected_scene_frame_set",),
    ".preview_items": (
        "SCENE_ROLE_GROUP_END_MS",
        "find_preview_insert_row",
        "find_preview_item_by_base_rel",
        "find_preview_item_by_ms",
        "preview_rel_text",
        "set_preview_item_rel_text",
    ),
    ".preview_nudge": ("nudge_selected_preview_frames",),
    ".preview_ranges": ("scene_frame_times_for_ms", "scene_frame_times_for_range"),
    ".preview_runtime": (
        "clear_scene_frame_preview",
        "disable_scene_frame_preview_on_keyboard_nav",
        "go_scene_frame_from_preview",
        "on_scene_frame_preview_toggled",
        "refresh_scene_frame_preview_if_enabled",
    ),
    ".preview_selection": (
        "is_scene_frame_preview_enabled",
        "scene_frame_step_ms",
        "scene_group_end_ms",
        "selected_scene_ms",
        "selected_scene_ms_list",
    ),
    ".refilter_samples": (
        "clear_ref_images",
        "current_sample_texts",
        "delete_selected_ref_images",
        "pick_ref_image",
        "pick_siglip_adapter",
        "sample_last_dir",
        "sample_preview_pixmap",
        "selected_ref_image_paths",
        "store_sample_last_dir",
        "update_ref_image_actions",
        "update_ref_image_text",
    ),
    ".refilter_apply": (
        "apply_refilter_pairs",
        "commit_refilter_reapply",
        "on_refilter_direct_group_changed",
        "on_sim_threshold_changed",
        "resume_thumbnail_loading",
        "schedule_refilter_reapply",
        "schedule_thumbnail_resume",
    ),
    ".refilter_auto_clip": ("auto_save_refilter_scene_clips",),
    ".refilter_state": ("set_refilter_running",),
    ".refilter_ui_state": (
        "apply_weight_profile",
        "current_auto_clip_end_mode",
        "current_frame_profile",
        "current_hybrid_siglip_weight",
        "current_kofn_k",
        "current_pose_weights",
        "current_refilter_agg_mode",
        "current_refilter_direct_group_band",
        "current_refilter_direct_group_enabled",
        "current_refilter_direct_sec",
        "current_refilter_mode",
        "current_refilter_sampling_mode",
        "current_refilter_source_mode",
        "current_siglip_adapter_path",
        "current_siglip_batch_size",
        "current_siglip_decode_scale_w",
        "current_siglip_model_id",
        "current_siglip_scene_feature_cache_enabled",
        "current_siglip_stage2_ratio",
        "current_siglip_two_stage",
        "on_hybrid_weight_changed",
        "on_refilter_agg_changed",
        "on_refilter_mode_changed",
        "on_refilter_sampling_mode_changed",
        "on_refilter_source_mode_changed",
        "on_siglip_two_stage_changed",
        "on_weight_profile_changed",
        "on_weight_slider_changed",
        "refilter_mode_label",
        "set_siglip_decode_scale_w",
        "siglip_runtime_device",
        "update_hybrid_weight_label",
        "update_weight_value_labels",
    ),
    ".refilter_runtime": ("clear_similarity_refilter", "run_similarity_refilter"),
    ".result_sorting": (
        "current_scene_sort_mode",
        "on_scene_sort_changed",
        "scene_item_text",
        "scene_sort_label",
        "scene_sort_score",
        "sort_scene_rows",
    ),
    ".result_view": (
        "collapse_direct_hits_first_only",
        "on_scene_result_selection_changed",
        "populate_from_result",
    ),
    ".scan_progress": ("refresh_scan_progress_text", "set_scan_progress_active"),
    ".scan_runtime": ("run_scan", "scan_unlock"),
    ".scene_navigation": ("go_current",),
    ".scene_ranges": (
        "build_direct_refilter_source",
        "scene_ranges_to_next_prefilter_from_starts",
        "scene_ranges_to_similarity_drop",
    ),
    ".scene_timeline": (
        "current_video_length_ms",
        "scene_end_ms",
        "scene_end_ms_from_starts",
        "timeline_scene_starts_prefilter_sorted",
        "timeline_scene_starts_sorted",
    ),
    ".thumbnail_loading": (
        "item_has_thumbnail",
        "on_preview_thumbnail_ready",
        "on_scene_item_clicked",
        "on_thumbnail_ready",
        "reprioritize_thumbnails_from_ms",
        "resume_thumbnail_loading",
        "schedule_thumbnail_resume",
    ),
}

_EXPORTS = {
    name: module_name
    for module_name, names in _EXPORT_GROUPS.items()
    for name in names
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
