from typing import Any, Dict, List, Optional

from PyQt6 import QtCore, QtWidgets

from scene_analysis.core.clip import ClipExportQueueWorker
from scene_analysis.core.media import ThumbnailWorker


def connect_scene_dialog_signals(dialog) -> None:
    dialog.btn_scan.clicked.connect(dialog._run_scan)
    dialog.tabs_scene_controls.currentChanged.connect(lambda _idx: _schedule_scene_dialog_layout_sync(dialog, 0))
    dialog.listw.itemClicked.connect(dialog._on_scene_item_clicked)
    dialog.listw.itemDoubleClicked.connect(lambda _it: dialog._go_current())
    dialog.listw.itemSelectionChanged.connect(dialog._on_scene_result_selection_changed)
    dialog.lst_scene_frame_preview.itemSelectionChanged.connect(dialog._update_scene_clip_button_enabled)
    dialog.chk_scene_frame_preview.stateChanged.connect(dialog._on_scene_frame_preview_toggled)
    dialog.spn_scene_frame_secs.valueChanged.connect(lambda _v: dialog._schedule_scene_frame_preview_refresh(70))
    dialog.chk_scene_frame_prev.stateChanged.connect(lambda _v: dialog._schedule_scene_frame_preview_refresh(70))
    _connect_preview_nudge(dialog)
    _connect_scene_actions(dialog)
    _connect_refilter_actions(dialog)
    _connect_refilter_state(dialog)


def _connect_preview_nudge(dialog):
    dialog.btn_scene_frame_shift_prev.clicked.connect(lambda: _nudge_preview(dialog, -1))
    dialog.btn_scene_frame_shift_next.clicked.connect(lambda: _nudge_preview(dialog, +1))


def _nudge_preview(dialog, direction: int):
    dialog._nudge_selected_preview_frames(direction, int(dialog.spn_scene_frame_shift_count.value()), int(dialog.spn_scene_frame_shift_step.value()))


def _connect_scene_actions(dialog):
    dialog.btn_scene_clip_save.clicked.connect(dialog._save_selected_scene_range_clip)
    dialog.btn_scene_set_ab.clicked.connect(dialog._set_selected_scene_range_ab)
    dialog.btn_scene_gif_save.clicked.connect(dialog._save_selected_scene_range_gif)
    dialog.btn_scene_frame_save.clicked.connect(dialog._save_selected_scene_result_shots)
    dialog.btn_scene_bookmark_add.clicked.connect(dialog._add_selected_scene_results_to_bookmarks)
    dialog.lst_scene_frame_preview.itemClicked.connect(lambda _it: dialog._go_scene_frame_from_preview(_it))
    dialog.lst_scene_frame_preview.itemActivated.connect(lambda _it: dialog._go_scene_frame_from_preview(_it))


def _connect_refilter_actions(dialog):
    dialog.btn_pick_ref.clicked.connect(dialog._pick_ref_image)
    dialog.btn_remove_ref.clicked.connect(dialog._delete_selected_ref_images)
    dialog.btn_clear_ref.clicked.connect(dialog._clear_ref_images)
    dialog.lst_ref_img.itemSelectionChanged.connect(dialog._update_ref_image_actions)
    dialog.btn_pick_siglip_adapter.clicked.connect(dialog._pick_siglip_adapter)
    dialog.btn_refilter.clicked.connect(dialog._run_similarity_refilter)
    dialog.btn_refilter_clear.clicked.connect(dialog._clear_similarity_refilter)
    dialog.spn_sim_thr.valueChanged.connect(dialog._on_sim_threshold_changed)
    dialog.chk_refilter_direct_group.stateChanged.connect(dialog._on_refilter_direct_group_changed)
    dialog.spn_refilter_direct_group_band.valueChanged.connect(dialog._on_refilter_direct_group_changed)
    dialog.btn_cache_history.clicked.connect(dialog._open_cache_history_dialog)
    dialog.btn_scan_batch.clicked.connect(dialog._open_scene_batch_dialog)


def _connect_refilter_state(dialog):
    dialog.cmb_refilter_mode.currentIndexChanged.connect(dialog._on_refilter_mode_changed)
    dialog.cmb_refilter_source.currentIndexChanged.connect(dialog._on_refilter_source_mode_changed)
    dialog.cmb_refilter_sampling.currentIndexChanged.connect(dialog._on_refilter_sampling_mode_changed)
    dialog.cmb_refilter_agg.currentIndexChanged.connect(dialog._on_refilter_agg_changed)
    dialog.chk_siglip_two_stage.stateChanged.connect(dialog._on_siglip_two_stage_changed)
    dialog.cmb_weight_profile.currentIndexChanged.connect(dialog._on_weight_profile_changed)
    dialog.cmb_scene_sort.currentIndexChanged.connect(dialog._on_scene_sort_changed)
    dialog.sld_hybrid_siglip.valueChanged.connect(dialog._on_hybrid_weight_changed)
    for key, slider in dialog.weight_sliders.items():
        slider.valueChanged.connect(lambda _v, kk=key: dialog._on_weight_slider_changed(kk))


def start_scene_dialog_workers(dialog) -> None:
    dialog.thumb_worker = ThumbnailWorker(parent=dialog)
    dialog.thumb_worker.thumbnailReady.connect(dialog._on_thumbnail_ready)
    dialog.thumb_worker.start()
    dialog.preview_thumb_worker = ThumbnailWorker(parent=dialog)
    dialog.preview_thumb_worker.thumbnailReady.connect(dialog._on_preview_thumbnail_ready)
    dialog.preview_thumb_worker.start()
    dialog.clip_worker = ClipExportQueueWorker(dialog)
    dialog.clip_worker.message.connect(dialog.lbl_status.setText)
    dialog.clip_worker.busy_changed.connect(dialog._on_clip_worker_busy_changed)
    dialog.clip_worker.job_finished.connect(dialog._on_clip_job_finished)
    dialog.clip_worker.job_failed.connect(dialog._on_clip_job_failed)
    dialog.clip_worker.start()


def init_scene_dialog_runtime_state(dialog) -> None:
    _init_runtime_fields(dialog)
    _init_timers(dialog)
    _bind_load_check_scroll(dialog)
    dialog._schedule_scene_layout_sync = lambda delay_ms=0: _schedule_scene_dialog_layout_sync(dialog, delay_ms)
    _schedule_scene_dialog_layout_sync(dialog, 0)
    _schedule_scene_dialog_layout_sync(dialog, 140)


def _init_runtime_fields(dialog):
    dialog.all_scenes_data: List[tuple[int, float]] = []
    dialog._display_source_data: List[tuple[int, float]] = []
    dialog._item_by_ms: dict[int, QtWidgets.QListWidgetItem] = {}
    dialog._similarity_by_ms: dict[int, float] = {}
    dialog._last_refilter_sim_by_ms: dict[int, float] = {}
    dialog._refilter_source_data: List[tuple[int, float]] = []
    dialog._refilter_source_override_ms: List[int] = []
    dialog._direct_group_clip_ranges: dict[int, tuple[int, int]] = {}
    dialog._refilter_active = False
    dialog.sample_image_paths: List[str] = []
    dialog.refilter_worker: Optional[Any] = None
    dialog._scan_progress_active = False
    dialog._scan_started_at = 0.0
    dialog._updating_weight_ui = False
    dialog._clip_worker_busy = False
    dialog._clip_job_meta: Dict[int, Dict[str, Any]] = {}
    dialog._cache_hist_dialog: Optional[QtWidgets.QDialog] = None
    dialog._cache_hist_tree: Optional[QtWidgets.QTreeWidget] = None
    dialog._cache_hist_lbl: Optional[QtWidgets.QLabel] = None
    dialog._cache_hist_chk_current: Optional[QtWidgets.QCheckBox] = None
    dialog._cache_hist_chk_close_after_load: Optional[QtWidgets.QCheckBox] = None
    dialog._cache_hist_loading = False
    dialog._cache_hist_pending_entry: Optional[dict] = None
    dialog._cache_hist_refresh_scheduled = False
    dialog._thumbnail_reload_suppressed = False
    dialog._scene_thumb_cache_path = ""
    dialog._scene_thumb_cache: dict[int, object] = {}
    dialog._preview_thumb_expected_ms: set[int] = set()
    dialog.current_path = ""
    dialog.loaded_count = 0
    dialog.currently_loading = False
    dialog.batch_size = 30


def _init_timers(dialog):
    dialog._scan_elapsed_timer = _timer(dialog, 250, dialog._refresh_scan_progress_text)
    dialog._refilter_reapply_timer = _single_shot_timer(dialog, 180, dialog._commit_refilter_reapply)
    dialog._thumbnail_resume_timer = _single_shot_timer(dialog, 280, dialog._resume_thumbnail_loading)
    dialog._scene_frame_preview_timer = _single_shot_timer(dialog, 90, dialog._commit_scene_frame_preview_refresh)
    dialog._load_check_timer = _single_shot_timer(dialog, 25, dialog._check_and_load_more)


def _bind_load_check_scroll(dialog):
    scrollbar = dialog.listw.verticalScrollBar()
    scrollbar.valueChanged.connect(dialog._schedule_load_check)
    scrollbar.rangeChanged.connect(lambda _min, _max: dialog._schedule_load_check())


def _timer(parent, interval: int, slot):
    timer = QtCore.QTimer(parent)
    timer.setInterval(interval)
    timer.timeout.connect(slot)
    return timer


def _single_shot_timer(parent, interval: int, slot):
    timer = QtCore.QTimer(parent)
    timer.setSingleShot(True)
    timer.setInterval(interval)
    timer.timeout.connect(slot)
    return timer


def _schedule_scene_dialog_layout_sync(dialog, delay_ms: int = 0) -> None:
    QtCore.QTimer.singleShot(max(0, int(delay_ms)), lambda d=dialog: _sync_scene_dialog_layout(d))


def _sync_scene_dialog_layout(dialog) -> None:
    if dialog is None:
        return
    try:
        tabs = getattr(dialog, "tabs_scene_controls", None)
        current_tab = tabs.currentWidget() if tabs is not None else None
        if current_tab is not None and current_tab.layout() is not None:
            current_tab.layout().activate()
            current_tab.updateGeometry()
        if tabs is not None:
            _sync_scene_tab_height(tabs, current_tab)
            tabs.updateGeometry()
        for name in ("listw", "lst_scene_frame_preview"):
            widget = getattr(dialog, name, None)
            if widget is None:
                continue
            try:
                widget.doItemsLayout()
            except Exception:
                pass
            try:
                widget.updateGeometries()
            except Exception:
                pass
            widget.updateGeometry()
            viewport = getattr(widget, "viewport", lambda: None)()
            if viewport is not None:
                viewport.update()
        if dialog.layout() is not None:
            dialog.layout().activate()
        dialog.updateGeometry()
        dialog.update()
    except RuntimeError:
        pass


def _sync_scene_tab_height(tabs, current_tab) -> None:
    if tabs is None or current_tab is None:
        return
    try:
        page_hint = current_tab.sizeHint()
        page_min = current_tab.minimumSizeHint()
        content_h = max(int(page_hint.height()), int(page_min.height()))
        tab_bar = tabs.tabBar()
        tab_bar_h = int(tab_bar.sizeHint().height()) if tab_bar is not None else 0
        margins = tabs.contentsMargins()
        frame_w = tabs.style().pixelMetric(QtWidgets.QStyle.PixelMetric.PM_DefaultFrameWidth, None, tabs)
        frame_h = int(frame_w) * 2
        target_h = max(0, content_h + tab_bar_h + int(margins.top()) + int(margins.bottom()) + frame_h)
        if target_h <= 0:
            return
        tabs.setMinimumHeight(target_h)
        tabs.setMaximumHeight(target_h)
    except Exception:
        pass
