# ffscene_cached.py (전체 수정 코드)
from typing import Any, Dict, List, Tuple, Optional
import logging
import os, time

from PyQt6 import QtWidgets, QtGui, QtCore

from scene_analysis.core.media import (
    FFMPEG_BIN,
    SIGLIP_BATCH_DEFAULT,
    ThumbnailWorker as _ThumbnailWorker,
    _normalize_siglip_batch_size,
    resolve_ffmpeg_bin,
)
from scene_analysis.core.cache import (
    _normalize_sample_paths,
    _normalize_sample_texts,
    load_from_disk,
    refilter_cache_clear_all,
    refilter_cache_clear_for_video,
    refilter_cache_get,
    refilter_cache_set,
    scene_cache_clear_all,
    scene_cache_clear_for_path,
    scene_cache_get,
    scene_cache_set,
    store_to_disk,
)
from scene_analysis.core.similarity import (
    POSE_COMP_KEYS,
    POSE_COMP_PROFILES,
    REFILTER_FRAME_PROFILES,
    _gpu_decode_chunk_batch_limits,
    _imread_bgr,
    _normalize_adapter_path,
    _normalize_pose_weights,
    _normalize_refilter_agg_mode,
    _normalize_refilter_sampling_mode as _normalize_refilter_sampling_mode_base,
    _normalize_siglip_decode_scale_w,
    _siglip2_default_model_id,
)
from scene_analysis.core.refilter import (
    SceneSimilarityParallelRunner,
    SceneSimilarityWorker,
    build_scene_similarity_cache_kwargs,
    build_scene_similarity_worker_kwargs,
    build_scene_similarity_worker_plan,
)
from scene_analysis.core.detect import SceneDetectWorker
from scene_analysis.dialog import (
    SCENE_ROLE_GROUP_END_MS as _SCENE_ROLE_GROUP_END_MS,
    apply_refilter_pairs as apply_refilter_pairs_impl,
    auto_save_refilter_scene_clips as auto_save_refilter_scene_clips_impl,
    begin_async_thumbnail_close as begin_async_thumbnail_close_impl,
    build_scene_dialog_ui,
    cache_history_dialog_closed,
    cache_history_selected_entries,
    clear_similarity_refilter as clear_similarity_refilter_impl,
    clear_ref_images as clear_ref_images_impl,
    collapse_direct_hits_first_only as collapse_direct_hits_first_only_impl,
    commit_refilter_reapply as commit_refilter_reapply_impl,
    current_auto_clip_end_mode as current_auto_clip_end_mode_impl,
    current_frame_profile as current_frame_profile_impl,
    current_hybrid_siglip_weight as current_hybrid_siglip_weight_impl,
    current_kofn_k as current_kofn_k_impl,
    current_pose_weights as current_pose_weights_impl,
    current_scene_sort_mode as current_scene_sort_mode_impl,
    current_refilter_agg_mode as current_refilter_agg_mode_impl,
    current_refilter_direct_group_band as current_refilter_direct_group_band_impl,
    current_refilter_direct_group_enabled as current_refilter_direct_group_enabled_impl,
    current_refilter_direct_sec as current_refilter_direct_sec_impl,
    current_refilter_mode as current_refilter_mode_impl,
    current_refilter_sampling_mode as current_refilter_sampling_mode_impl,
    current_refilter_source_mode as current_refilter_source_mode_impl,
    current_sample_texts as current_sample_texts_impl,
    current_siglip_adapter_path as current_siglip_adapter_path_impl,
    current_siglip_batch_size as current_siglip_batch_size_impl,
    current_siglip_decode_scale_w as current_siglip_decode_scale_w_impl,
    current_siglip_model_id as current_siglip_model_id_impl,
    current_siglip_scene_feature_cache_enabled as current_siglip_scene_feature_cache_enabled_impl,
    current_siglip_stage2_ratio as current_siglip_stage2_ratio_impl,
    current_siglip_two_stage as current_siglip_two_stage_impl,
    clear_scene_frame_preview,
    close_event as close_event_impl,
    continue_close_after_thumbnail_workers as continue_close_after_thumbnail_workers_impl,
    delete_selected_ref_images as delete_selected_ref_images_impl,
    delete_selected_cache_history_entries,
    disable_scene_frame_preview_on_keyboard_nav,
    dispatch_cache_history_entry_load,
    find_preview_insert_row,
    find_preview_item_by_base_rel,
    find_preview_item_by_ms,
    go_scene_frame_from_preview,
    is_scene_frame_preview_enabled,
    load_refilter_cache_entry,
    load_scene_cache_entry,
    load_selected_cache_history_entry,
    nudge_selected_preview_frames,
    on_refilter_direct_group_changed as on_refilter_direct_group_changed_impl,
    on_sim_threshold_changed as on_sim_threshold_changed_impl,
    on_hybrid_weight_changed as on_hybrid_weight_changed_impl,
    on_refilter_agg_changed as on_refilter_agg_changed_impl,
    on_refilter_mode_changed as on_refilter_mode_changed_impl,
    on_refilter_sampling_mode_changed as on_refilter_sampling_mode_changed_impl,
    on_refilter_source_mode_changed as on_refilter_source_mode_changed_impl,
    on_scene_result_selection_changed as on_scene_result_selection_changed_impl,
    on_scene_sort_changed as on_scene_sort_changed_impl,
    on_scene_frame_preview_toggled,
    on_siglip_two_stage_changed as on_siglip_two_stage_changed_impl,
    on_weight_profile_changed as on_weight_profile_changed_impl,
    on_weight_slider_changed as on_weight_slider_changed_impl,
    open_scene_dialog_with_options as open_scene_dialog_with_options_impl,
    open_cache_history_dialog,
    open_scene_batch_dialog,
    pick_ref_image as pick_ref_image_impl,
    pick_siglip_adapter as pick_siglip_adapter_impl,
    prepare_thumbnail_workers_for_close as prepare_thumbnail_workers_for_close_impl,
    preview_rel_text,
    populate_from_result as populate_from_result_impl,
    refresh_cache_history_dialog,
    refresh_scene_frame_preview_if_enabled,
    request_cache_history_entry_load,
    refilter_mode_label as refilter_mode_label_impl,
    refresh_scan_progress_text as refresh_scan_progress_text_impl,
    run_scan as run_scan_impl,
    scan_unlock as scan_unlock_impl,
    refilter_cache_clear_all_public as refilter_cache_clear_all_public_impl,
    refilter_cache_clear_for_current as refilter_cache_clear_for_current_impl,
    scene_frame_step_ms,
    scene_frame_times_for_ms,
    scene_frame_times_for_range,
    scene_group_end_ms,
    scene_end_ms,
    scene_end_ms_from_starts,
    scene_item_text as scene_item_text_impl,
    scene_ranges_to_next_prefilter_from_starts,
    scene_ranges_to_similarity_drop,
    scene_sort_label as scene_sort_label_impl,
    scene_sort_score as scene_sort_score_impl,
    schedule_cache_history_refresh,
    scene_cache_clear_all_public as scene_cache_clear_all_public_impl,
    scene_cache_clear_for_current as scene_cache_clear_for_current_impl,
    selected_scene_ms,
    selected_scene_ms_list,
    selected_ref_image_paths as selected_ref_image_paths_impl,
    set_refilter_running as set_refilter_running_impl,
    set_scan_progress_active as set_scan_progress_active_impl,
    set_siglip_decode_scale_w as set_siglip_decode_scale_w_impl,
    set_preview_item_rel_text,
    sample_last_dir as sample_last_dir_impl,
    sample_preview_pixmap as sample_preview_pixmap_impl,
    show_selected_scene_frame_set,
    siglip_runtime_device as siglip_runtime_device_impl,
    sort_scene_rows as sort_scene_rows_impl,
    store_sample_last_dir as store_sample_last_dir_impl,
    shutdown_for_app_close as shutdown_for_app_close_impl,
    timeline_scene_starts_prefilter_sorted,
    timeline_scene_starts_sorted,
    thumbnail_workers_running as thumbnail_workers_running_impl,
    wait_for_worker_stopped as wait_for_worker_stopped_impl,
    current_video_length_ms,
    build_direct_refilter_source,
    check_and_load_more as check_and_load_more_impl,
    go_current as go_current_impl,
    item_has_thumbnail as item_has_thumbnail_impl,
    load_next_batch as load_next_batch_impl,
    on_preview_thumbnail_ready as on_preview_thumbnail_ready_impl,
    on_scene_item_clicked as on_scene_item_clicked_impl,
    on_thumbnail_ready as on_thumbnail_ready_impl,
    reprioritize_thumbnails_from_ms as reprioritize_thumbnails_from_ms_impl,
    resume_thumbnail_loading as resume_thumbnail_loading_impl,
    run_similarity_refilter as run_similarity_refilter_impl,
    schedule_refilter_reapply as schedule_refilter_reapply_impl,
    schedule_thumbnail_resume as schedule_thumbnail_resume_impl,
    update_hybrid_weight_label as update_hybrid_weight_label_impl,
    update_ref_image_actions as update_ref_image_actions_impl,
    update_ref_image_text as update_ref_image_text_impl,
    update_weight_value_labels as update_weight_value_labels_impl,
    apply_weight_profile as apply_weight_profile_impl,
)
from i18n import tr


def _normalize_refilter_sampling_mode(mode: str) -> str:
    m = str(mode or "").strip().lower()
    if m == "adaptive_window":
        return "scene_window"
    return _normalize_refilter_sampling_mode_base(m)


def _refilter_sampling_uses_frame_profile(mode: str) -> bool:
    return _normalize_refilter_sampling_mode(mode) == "scene_window"
from scene_analysis.dialog import (
    add_selected_scene_results_to_bookmarks,
    enqueue_clip_export_job,
    on_clip_job_failed,
    on_clip_job_finished,
    on_clip_worker_busy_changed,
    save_selected_scene_range_clip,
    save_selected_scene_range_gif,
    save_selected_scene_result_shots,
    selected_clip_range_ms,
    selected_clip_ranges_for_save,
    selected_grouped_scene_clip_ranges,
    selected_ms_from_items,
    selected_scene_ms_list_for_save,
    set_selected_scene_range_ab,
    update_scene_clip_button_enabled,
)


ThumbnailWorker = _ThumbnailWorker
logger = logging.getLogger(__name__)


def _dialog_ffmpeg_bin(dialog) -> str:
    preferred = str(getattr(getattr(dialog, "ed_ff", None), "text", lambda: "")() or "").strip()
    if not preferred:
        host = getattr(dialog, "host", None)
        preferred = str(getattr(host, "ffmpeg_path", "") or "").strip()
    ffbin = resolve_ffmpeg_bin(preferred or FFMPEG_BIN)
    try:
        if hasattr(dialog, "ed_ff"):
            dialog.ed_ff.setText(ffbin)
    except (AttributeError, RuntimeError, TypeError):
        logger.debug("scene dialog ffmpeg line edit sync skipped", exc_info=True)
    try:
        host = getattr(dialog, "host", None)
        if host is not None:
            setattr(host, "ffmpeg_path", ffbin)
    except (AttributeError, RuntimeError, TypeError):
        logger.debug("scene dialog host ffmpeg path sync skipped", exc_info=True)
    return ffbin


# ---------- 클립 내보내기 큐 워커 ----------
# ---------- 옵션 다이얼로그 ----------
class SceneDialog(QtWidgets.QDialog):
    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.host = host
        self._thumb_close_pending = False
        self._force_close_after_thumb = False
        self._thumb_close_retry_timer: Optional[QtCore.QTimer] = None
        # 첫 실행 기본값은 GPU 우선이고, CPU 디코드 체크는 해제 상태로 둔다.
        if not hasattr(host, "ffmpeg_hwaccel"):
            setattr(host, "ffmpeg_hwaccel", True)
        self.setWindowTitle(tr(self, "씬분석 (씬변화 / 유사씬)"))
        self.setModal(False)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        build_scene_dialog_ui(self, host)

    def _thumbnail_workers_running(self) -> bool:
        return thumbnail_workers_running_impl(self)

    def _prepare_thumbnail_workers_for_close(self) -> None:
        prepare_thumbnail_workers_for_close_impl(self)

    def _continue_close_after_thumbnail_workers(self) -> None:
        continue_close_after_thumbnail_workers_impl(self)

    def _begin_async_thumbnail_close(self) -> None:
        begin_async_thumbnail_close_impl(self)

    def _wait_for_worker_stopped(self, worker: Any, timeout_ms: int = 5000) -> bool:
        return wait_for_worker_stopped_impl(worker, timeout_ms=timeout_ms)

    def shutdown_for_app_close(self, timeout_ms: int = 5000) -> bool:
        return shutdown_for_app_close_impl(self, timeout_ms=timeout_ms)

    def closeEvent(self, e: QtGui.QCloseEvent):
        close_event_impl(self, e)

    def showEvent(self, event):  # type: ignore[override]
        super().showEvent(event)
        self._request_scene_layout_sync(0)
        self._request_scene_layout_sync(180)
        self._request_scene_layout_sync(360)

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        self._request_scene_layout_sync(0)

    def _format_elapsed_tag(self, sec: int) -> str:
        s = max(0, int(sec))
        hh = s // 3600
        mm = (s % 3600) // 60
        ss = s % 60
        if hh > 0:
            return f"{hh:02d}:{mm:02d}:{ss:02d}"
        return f"{mm:02d}:{ss:02d}"

    def _refresh_scan_progress_text(self):
        refresh_scan_progress_text_impl(self)

    def _set_scan_progress_active(self, active: bool):
        set_scan_progress_active_impl(self, active)

    def _scene_item_text(self, ms: int, score: float) -> str:
        return scene_item_text_impl(self, ms, score)

    def _current_scene_sort_mode(self) -> str:
        return current_scene_sort_mode_impl(self)

    def _scene_sort_label(self) -> str:
        return scene_sort_label_impl(self)

    def _scene_sort_score(self, ms: int, score: float) -> float:
        return scene_sort_score_impl(self, ms, score)

    def _sort_scene_rows(self, rows: List[tuple[int, float]]) -> List[tuple[int, float]]:
        return sort_scene_rows_impl(self, rows)

    def _on_scene_sort_changed(self, *_):
        on_scene_sort_changed_impl(self)

    def _sample_preview_pixmap(self, path: str, w: int = 96, h: int = 60) -> Optional[QtGui.QPixmap]:
        return sample_preview_pixmap_impl(self, path, w=w, h=h)

    def _update_ref_image_text(self):
        update_ref_image_text_impl(self)

    def _selected_ref_image_paths(self) -> List[str]:
        return selected_ref_image_paths_impl(self)

    def _update_ref_image_actions(self):
        update_ref_image_actions_impl(self)

    def _sample_last_dir(self) -> str:
        return sample_last_dir_impl(self)

    def _store_sample_last_dir(self, folder: str):
        store_sample_last_dir_impl(self, folder)

    def _pick_ref_image(self):
        pick_ref_image_impl(self)

    def _clear_ref_images(self):
        clear_ref_images_impl(self)

    def _delete_selected_ref_images(self):
        delete_selected_ref_images_impl(self)

    def _current_sample_texts(self) -> List[str]:
        return current_sample_texts_impl(self)

    def _pick_siglip_adapter(self):
        pick_siglip_adapter_impl(self)

    def _set_refilter_running(self, running: bool):
        set_refilter_running_impl(
            self,
            running,
            source_mode=self._current_refilter_source_mode(),
            uses_frame_profile=_refilter_sampling_uses_frame_profile(self._current_refilter_sampling_mode()),
            agg_mode=self._current_refilter_agg_mode(),
        )

    def _current_refilter_mode(self) -> str:
        return current_refilter_mode_impl(self)

    def _current_refilter_agg_mode(self) -> str:
        return current_refilter_agg_mode_impl(self)

    def _current_auto_clip_end_mode(self) -> str:
        return current_auto_clip_end_mode_impl(self)

    def _current_refilter_source_mode(self) -> str:
        return current_refilter_source_mode_impl(self)

    def _current_refilter_direct_sec(self) -> int:
        return current_refilter_direct_sec_impl(self)

    def _current_siglip_batch_size(self) -> int:
        return current_siglip_batch_size_impl(self)

    def _current_siglip_decode_scale_w(self) -> int:
        return current_siglip_decode_scale_w_impl(self)

    def _current_siglip_scene_feature_cache_enabled(self) -> bool:
        return current_siglip_scene_feature_cache_enabled_impl(self)

    def _set_siglip_decode_scale_w(self, value: Any):
        set_siglip_decode_scale_w_impl(self, value)

    def _current_siglip_two_stage(self) -> bool:
        return current_siglip_two_stage_impl(self)

    def _current_siglip_stage2_ratio(self) -> float:
        return current_siglip_stage2_ratio_impl(self)

    def _on_siglip_two_stage_changed(self, *_):
        on_siglip_two_stage_changed_impl(self)

    def _current_refilter_direct_group_enabled(self) -> bool:
        return current_refilter_direct_group_enabled_impl(self)

    def _current_refilter_direct_group_band(self) -> float:
        return current_refilter_direct_group_band_impl(self)

    def _current_kofn_k(self) -> int:
        return current_kofn_k_impl(self)

    def _current_frame_profile(self) -> str:
        return current_frame_profile_impl(self)

    def _current_refilter_sampling_mode(self) -> str:
        return current_refilter_sampling_mode_impl(self)

    def _current_hybrid_siglip_weight(self) -> float:
        return current_hybrid_siglip_weight_impl(self)

    def _update_hybrid_weight_label(self):
        update_hybrid_weight_label_impl(self)

    def _on_hybrid_weight_changed(self, *_):
        on_hybrid_weight_changed_impl(self)

    def _on_refilter_agg_changed(self, *_):
        on_refilter_agg_changed_impl(self)

    def _on_refilter_source_mode_changed(self, *_):
        on_refilter_source_mode_changed_impl(self)

    def _on_refilter_sampling_mode_changed(self, *_):
        on_refilter_sampling_mode_changed_impl(self)

    def _refilter_mode_label(self, mode: str) -> str:
        return refilter_mode_label_impl(self, mode)

    def _current_siglip_model_id(self) -> str:
        return current_siglip_model_id_impl(self)

    def _current_siglip_adapter_path(self) -> str:
        return current_siglip_adapter_path_impl(self)

    def _siglip_runtime_device(self) -> str:
        return siglip_runtime_device_impl(self)

    def _on_refilter_mode_changed(self, *_):
        on_refilter_mode_changed_impl(self)

    def _current_pose_weights(self) -> dict[str, float]:
        return current_pose_weights_impl(self)

    def _update_weight_value_labels(self):
        update_weight_value_labels_impl(self)

    def _apply_weight_profile(self, profile_name: str):
        apply_weight_profile_impl(self, profile_name)

    def _on_weight_profile_changed(self, *_):
        on_weight_profile_changed_impl(self)

    def _on_weight_slider_changed(self, _key: str):
        on_weight_slider_changed_impl(self, _key)

    def _collapse_direct_hits_first_only(
        self,
        filtered_data: List[tuple[int, float]],
        sim_map: dict[int, float],
    ) -> Tuple[List[tuple[int, float]], dict[int, tuple[int, int]]]:
        if not filtered_data:
            return [], {}
        return collapse_direct_hits_first_only_impl(
            max(1000, int(self._current_refilter_direct_sec() * 1000)),
            self._current_video_length_ms(),
            filtered_data,
            sim_map,
            self._current_refilter_direct_group_band(),
        )

    def _apply_refilter_pairs(
        self,
        source: List[tuple[int, float]],
        sim_pairs: List[tuple[int, float]],
        mode: str,
        cache_hit: bool = False,
        allow_auto_clip: bool = True,
    ):
        apply_refilter_pairs_impl(
            self,
            source,
            sim_pairs,
            mode,
            cache_hit=cache_hit,
            allow_auto_clip=allow_auto_clip,
        )

    def _schedule_refilter_reapply(self, status_text: str, debounce_ms: int = 180):
        schedule_refilter_reapply_impl(self, status_text, debounce_ms=debounce_ms)

    def _on_sim_threshold_changed(self, *_):
        on_sim_threshold_changed_impl(self)

    def _on_refilter_direct_group_changed(self, *_):
        on_refilter_direct_group_changed_impl(self)

    def _commit_refilter_reapply(self):
        commit_refilter_reapply_impl(self)

    def _schedule_thumbnail_resume(self, debounce_ms: int = 280):
        schedule_thumbnail_resume_impl(self, debounce_ms)

    def _resume_thumbnail_loading(self):
        resume_thumbnail_loading_impl(self)

    def _auto_save_refilter_scene_clips(self, filtered_data: List[tuple[int, float]]):
        auto_save_refilter_scene_clips_impl(self, filtered_data)

    def _run_similarity_refilter(self):
        run_similarity_refilter_impl(self)

    def _clear_similarity_refilter(self):
        clear_similarity_refilter_impl(self)

    def _history_current_video_path(self) -> str:
        p = ""
        try:
            p = str(self.host._current_media_path() or "")
        except (AttributeError, RuntimeError):
            logger.debug("history current media path lookup failed", exc_info=True)
            p = str(self.current_path or "")
        return os.path.abspath(p) if p else ""

    def _history_norm_path(self, path: str) -> str:
        p = str(path or "").strip()
        if not p:
            return ""
        try:
            return os.path.normcase(os.path.normpath(os.path.abspath(p)))
        except (OSError, TypeError, ValueError):
            logger.debug("history path normalization failed for %r", path, exc_info=True)
            return p

    def _history_active_media_path(self) -> str:
        try:
            mp = getattr(self.host, "mediaplayer", None)
            if mp is None or not hasattr(mp, "get_media"):
                return ""
            media = mp.get_media()
            if media is None:
                return ""
            mrl = str(media.get_mrl() or "")
            if not mrl:
                return ""
            if mrl.startswith("file:///"):
                import urllib.parse
                path = urllib.parse.unquote(mrl[8:])
            elif mrl.startswith("file://"):
                import urllib.parse
                path = urllib.parse.unquote(mrl[7:])
            else:
                path = mrl
            if os.name == "nt":
                path = path.replace("/", "\\")
            return os.path.abspath(path) if path else ""
        except (AttributeError, RuntimeError, OSError, TypeError, ValueError):
            logger.debug("history active media path extraction failed", exc_info=True)
            return ""

    def _ensure_history_video_loaded(self, target_path: str) -> bool:
        path = os.path.abspath(str(target_path or ""))
        if not path or not os.path.exists(path):
            QtWidgets.QMessageBox.warning(self, "오류", "기록의 영상 경로를 찾을 수 없습니다.")
            return False
        norm_target = self._history_norm_path(path)
        cur = self._history_current_video_path()
        norm_cur = self._history_norm_path(cur)
        norm_active = self._history_norm_path(self._history_active_media_path())
        same_video = bool(norm_cur) and (norm_cur == norm_target)
        active_ready = bool(norm_active) and (norm_active == norm_target)
        # 같은 파일이면 결과만 다시 로드하고, VLC 미디어를 불필요하게 재오픈하지 않는다.
        # 결과기록 재로드마다 stop/set_media를 반복하면 FFmpeg/VLC 디코더 경고가 늘어난다.
        if same_video:
            self.current_path = path
            return True

        yes_btn = getattr(QtWidgets.QMessageBox, "Yes", QtWidgets.QMessageBox.StandardButton.Yes)
        no_btn = getattr(QtWidgets.QMessageBox, "No", QtWidgets.QMessageBox.StandardButton.No)
        if not same_video:
            ret = QtWidgets.QMessageBox.question(
                self,
                "영상 전환",
                "선택한 기록은 현재 영상과 다릅니다.\n현재 타일에서 해당 영상을 열고 결과를 로드할까요?",
                yes_btn | no_btn,
                yes_btn,
            )
            if ret != yes_btn:
                return False
        try:
            if hasattr(self.host, "stop"):
                try:
                    self.host.stop()
                except RuntimeError:
                    logger.debug("history video switch stop skipped", exc_info=True)
            opened = False
            if hasattr(self.host, "add_to_playlist"):
                opened = bool(self.host.add_to_playlist(path, play_now=True))
            elif hasattr(self.host, "set_media"):
                opened = bool(self.host.set_media(path))
            if not opened:
                return False
            if hasattr(self.host, "play"):
                try:
                    self.host.play()
                except RuntimeError:
                    logger.debug("history video switch play skipped", exc_info=True)
            # 같은 경로로 인식되어도 실제 VLC media 객체가 비어 있던 경우를 보정.
            if self._history_norm_path(self._history_active_media_path()) != norm_target and hasattr(self.host, "set_media"):
                if self.host.set_media(path) and hasattr(self.host, "play"):
                    try:
                        self.host.play()
                    except RuntimeError:
                        logger.debug("history video switch play retry skipped", exc_info=True)
            self.current_path = path
            return True
        except Exception:
            logger.warning("history video switch failed for %s", path, exc_info=True)
            QtWidgets.QMessageBox.warning(self, "오류", "영상 전환에 실패했습니다.")
            return False

    def _cache_history_selected_entries(self) -> List[dict]:
        return cache_history_selected_entries(self)

    def _refresh_cache_history_dialog(self):
        refresh_cache_history_dialog(self)

    def _load_scene_cache_entry(self, ent: dict):
        load_scene_cache_entry(self, ent)

    def _load_refilter_cache_entry(self, ent: dict):
        load_refilter_cache_entry(self, ent)

    def _schedule_cache_history_refresh(self):
        schedule_cache_history_refresh(self)

    def _dispatch_cache_history_entry_load(self, ent: dict):
        dispatch_cache_history_entry_load(self, ent)

    def _request_cache_history_entry_load(self, ent: dict):
        request_cache_history_entry_load(self, ent)

    def _load_selected_cache_history_entry(self):
        load_selected_cache_history_entry(self)

    def _delete_selected_cache_history_entries(self):
        delete_selected_cache_history_entries(self)

    def _open_cache_history_dialog(self):
        open_cache_history_dialog(self)

    def _open_scene_batch_dialog(self):
        open_scene_batch_dialog(self)

    def _cache_history_dialog_closed(self):
        cache_history_dialog_closed(self)

    def _clear_scene_frame_preview(self):
        clear_scene_frame_preview(self)

    def _is_scene_frame_preview_enabled(self) -> bool:
        return is_scene_frame_preview_enabled(self)

    def _scene_frame_step_ms(self) -> int:
        return scene_frame_step_ms(self)

    def _preview_rel_text(self, rel_step: int) -> str:
        return preview_rel_text(rel_step)

    def _set_preview_item_rel_text(self, it: QtWidgets.QListWidgetItem, ms: int, rel_step: int):
        set_preview_item_rel_text(self, it, ms, rel_step)

    def _find_preview_item_by_base_rel(self, base_ms: int, rel_step: int) -> Optional[QtWidgets.QListWidgetItem]:
        return find_preview_item_by_base_rel(self, base_ms, rel_step)

    def _find_preview_item_by_ms(self, ms: int) -> Optional[QtWidgets.QListWidgetItem]:
        return find_preview_item_by_ms(self, ms)

    def _find_preview_insert_row(self, base_ms: int, rel_step: int) -> int:
        return find_preview_insert_row(self, base_ms, rel_step)

    def _nudge_selected_preview_frames(
        self,
        step_frames: int,
        repeat_count: int = 1,
        jump_step_frames: int = 1,
    ):
        nudge_selected_preview_frames(self, step_frames, repeat_count=repeat_count, jump_step_frames=jump_step_frames)

    def _refresh_scene_frame_preview_if_enabled(self):
        refresh_scene_frame_preview_if_enabled(self)

    def _schedule_scene_frame_preview_refresh(self, debounce_ms: int = 90):
        timer = getattr(self, "_scene_frame_preview_timer", None)
        if timer is None:
            self._commit_scene_frame_preview_refresh()
            return
        try:
            worker = getattr(self, "preview_thumb_worker", None)
            if worker is not None:
                worker.clear_jobs()
        except RuntimeError:
            logger.debug("scene frame preview worker clear_jobs skipped", exc_info=True)
        timer.setInterval(max(1, int(debounce_ms)))
        timer.start()

    def _commit_scene_frame_preview_refresh(self):
        refresh_scene_frame_preview_if_enabled(self)

    def _on_scene_frame_preview_toggled(self, _state: int):
        timer = getattr(self, "_scene_frame_preview_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
        on_scene_frame_preview_toggled(self, _state)

    def _disable_scene_frame_preview_on_keyboard_nav(self):
        disable_scene_frame_preview_on_keyboard_nav(self)

    def eventFilter(self, obj, event):
        if obj is getattr(self, "listw", None) and event is not None:
            et = event.type()
            if et == QtCore.QEvent.Type.KeyPress:
                key = int(getattr(event, "key", lambda: 0)())
                nav_keys = {
                    int(QtCore.Qt.Key.Key_Left), int(QtCore.Qt.Key.Key_Right),
                    int(QtCore.Qt.Key.Key_Up), int(QtCore.Qt.Key.Key_Down),
                    int(QtCore.Qt.Key.Key_PageUp), int(QtCore.Qt.Key.Key_PageDown),
                    int(QtCore.Qt.Key.Key_Home), int(QtCore.Qt.Key.Key_End),
                }
                if key in nav_keys:
                    self._disable_scene_frame_preview_on_keyboard_nav()
        return super().eventFilter(obj, event)

    def _selected_scene_ms(self) -> Optional[int]:
        return selected_scene_ms(self)

    def _selected_scene_ms_list(self) -> List[int]:
        return selected_scene_ms_list(self)

    def _scene_group_end_ms(self, scene_start_ms: int) -> Optional[int]:
        return scene_group_end_ms(self, scene_start_ms)

    def _timeline_scene_starts_sorted(self) -> List[int]:
        return timeline_scene_starts_sorted(self)

    def _request_scene_layout_sync(self, delay_ms: int = 0) -> None:
        try:
            scheduler = getattr(self, "_schedule_scene_layout_sync", None)
            if callable(scheduler):
                scheduler(int(delay_ms))
        except Exception:
            pass

    def _timeline_scene_starts_prefilter_sorted(self) -> List[int]:
        return timeline_scene_starts_prefilter_sorted(self)

    def _scene_end_ms_from_starts(self, scene_start_ms: int, starts: List[int], fallback_sec: int = 3) -> int:
        return scene_end_ms_from_starts(self, scene_start_ms, starts, fallback_sec=fallback_sec)

    def _scene_end_ms(self, scene_start_ms: int, fallback_sec: int = 3) -> int:
        return scene_end_ms(self, scene_start_ms, fallback_sec=fallback_sec)

    def _current_video_length_ms(self) -> int:
        return current_video_length_ms(self)

    def _build_direct_refilter_source(self, interval_sec: int) -> List[tuple[int, float]]:
        return build_direct_refilter_source(self, interval_sec)

    def _scene_frame_times_for_ms(self, center_ms: int, duration_sec: int, include_prev: bool = False) -> List[int]:
        return scene_frame_times_for_ms(center_ms, duration_sec, include_prev=include_prev)

    def _scene_frame_times_for_range(
        self,
        start_ms: int,
        end_ms: int,
        duration_sec: int,
        include_prev: bool = False,
    ) -> List[int]:
        return scene_frame_times_for_range(start_ms, end_ms, duration_sec, include_prev=include_prev)

    def _format_ms_mmss(self, ms: int) -> str:
        sec = max(0, int(ms) // 1000)
        mm, ss = divmod(sec, 60)
        return f"{mm:02d}:{ss:02d}"

    def _show_selected_scene_frame_set(self):
        show_selected_scene_frame_set(self)

    def _on_scene_result_selection_changed(self):
        on_scene_result_selection_changed_impl(self)

    def _item_has_thumbnail(self, it: Optional[QtWidgets.QListWidgetItem]) -> bool:
        return item_has_thumbnail_impl(self, it)

    def _reprioritize_thumbnails_from_ms(self, start_ms: int):
        reprioritize_thumbnails_from_ms_impl(self, start_ms)

    def _on_scene_item_clicked(self, it: Optional[QtWidgets.QListWidgetItem]):
        on_scene_item_clicked_impl(self, it)

    def _go_scene_frame_from_preview(self, item: Optional[QtWidgets.QListWidgetItem] = None):
        go_scene_frame_from_preview(self, item=item)

    def _selected_ms_from_items(self, items: List[QtWidgets.QListWidgetItem]) -> List[int]:
        return selected_ms_from_items(self, items)

    def _selected_clip_range_ms(self) -> Optional[Tuple[int, int]]:
        return selected_clip_range_ms(self)

    def _selected_grouped_scene_clip_ranges(self) -> List[Tuple[int, int]]:
        return selected_grouped_scene_clip_ranges(self)

    def _selected_clip_ranges_for_save(self) -> List[Tuple[int, int]]:
        return selected_clip_ranges_for_save(self)

    def _update_scene_clip_button_enabled(self):
        update_scene_clip_button_enabled(self)

    def _on_clip_worker_busy_changed(self, busy: bool):
        on_clip_worker_busy_changed(self, busy)

    def _enqueue_clip_export_job(
        self,
        kind: str,
        clip_ranges: List[Tuple[int, int]],
        mode_label: str,
        source: str = "manual",
    ) -> int:
        return enqueue_clip_export_job(self, kind, clip_ranges, mode_label, source=source)

    def _on_clip_job_finished(self, result: dict):
        on_clip_job_finished(self, result)

    def _on_clip_job_failed(self, payload: dict):
        on_clip_job_failed(self, payload)

    def _scene_ranges_to_next_prefilter_from_starts(self, scene_starts_ms: List[int]) -> List[Tuple[int, int]]:
        return scene_ranges_to_next_prefilter_from_starts(self, scene_starts_ms)

    def _scene_ranges_to_similarity_drop(self, sim_thr: float) -> List[Tuple[int, int]]:
        return scene_ranges_to_similarity_drop(self, sim_thr)

    def _save_selected_scene_range_clip(self):
        save_selected_scene_range_clip(self)

    def _set_selected_scene_range_ab(self):
        set_selected_scene_range_ab(self)

    def _save_selected_scene_range_gif(self):
        save_selected_scene_range_gif(self)

    def _selected_scene_ms_list_for_save(self) -> List[int]:
        return selected_scene_ms_list_for_save(self)

    def _save_selected_scene_result_shots(self):
        save_selected_scene_result_shots(self)

    def _add_selected_scene_results_to_bookmarks(self):
        add_selected_scene_results_to_bookmarks(self)

    def _go_current(self):
        go_current_impl(self)

    def _filter_pts(self, pts: List[int], top: List[tuple[int, float]]) -> List[int]:
        topk = int(self.spn_topk.value() if hasattr(self, "spn_topk") else 0)
        mingap = int(self.spn_mingap.value() if hasattr(self, "spn_mingap") else 0)

        # 1. 'pts'를 (ms, score) 튜플 리스트로 변환 (기본은 시간순)
        top_map = dict(top or [])
        scored_pts = []
        for ms in sorted(set(pts or [])):
            scored_pts.append((ms, top_map.get(ms, 0.0)))

        # 2. 'Top-K' 필터링 (변동성 기준)
        #    Top-K가 0이면 이 단계는 건너뛰고 'working_list'는 전체 씬이 됨
        if topk > 0:
            # 점수순으로 정렬해서 상위 K개만 '선택'
            scored_pts.sort(key=lambda x: x[1], reverse=True)
            working_list = scored_pts[:topk]
            # ◀ Top-K로 고른 씬들을 다시 시간순으로 정렬
            working_list.sort(key=lambda x: x[0])
        else:
            # 0이면 '전체' (이미 시간순)
            working_list = scored_pts

        # 3. '최소 간격(mingap)' 필터링
        #    (Top-K 리스트든, 전체 리스트든, 항상 mingap 적용)
        final_pts_ms = []
        if mingap > 0:
            last_ms = -mingap  # 0도 포함시키기 위해
            for ms, score in working_list:  # working_list는 항상 시간순
                if (ms - last_ms) >= mingap:
                    final_pts_ms.append(ms)
                    last_ms = ms
        else:
            final_pts_ms = [ms for ms, score in working_list]

        # 4. 0(시작점)이 없으면 추가하고 최종 시간순 정렬
        if 0 not in final_pts_ms:
            final_pts_ms.append(0)

        return sorted(list(set(final_pts_ms)))

    def _apply_user_threshold(self, pts: List[int], top: List[tuple[int, float]]) -> List[int]:
        base = sorted(set(int(ms) for ms in (pts or [])))
        if 0 not in base:
            base = [0] + base
        if not top:
            return base

        user_thr = float(self.spn_thr.value() if hasattr(self, "spn_thr") else 0.0)
        filtered = sorted(set(int(ms) for ms, score in top if float(score) >= user_thr))
        if 0 not in filtered:
            filtered = [0] + filtered

        # 점수 스케일/샘플링 특성으로 컷이 모두 탈락하는 경우, 0초만 보이는 현상 방지
        if len(filtered) <= 1 and len(base) > 1:
            return base
        return filtered

    def _schedule_load_check(self, *_):
        if getattr(self, "_load_check_timer", None) is None:
            return
        if not self._load_check_timer.isActive():
            self._load_check_timer.start()

    @QtCore.pyqtSlot(str, QtGui.QImage, int)
    def _on_thumbnail_ready(self, path: str, image: QtGui.QImage, ms: int):
        on_thumbnail_ready_impl(self, path, image, ms)

    def _on_preview_thumbnail_ready(self, path: str, image: QtGui.QImage, ms: int):
        on_preview_thumbnail_ready_impl(self, path, image, ms)

    @QtCore.pyqtSlot()
    def _check_and_load_more(self):
        check_and_load_more_impl(self)

    # ◀◀◀ [신규] 다음 N개 씬을 리스트에 추가
    def _load_next_batch(self):
        load_next_batch_impl(self)

    def _populate_from_result(self, path: str, pts: List[int], top: List[tuple[int, float]],
                              reset_similarity: bool = True):
        populate_from_result_impl(
            self,
            path,
            pts,
            top,
            reset_similarity=reset_similarity,
            scene_role_group_end_ms=_SCENE_ROLE_GROUP_END_MS,
        )

    def _scan_unlock(self):
        scan_unlock_impl(self)

    def _run_scan(self, force_rescan: bool = False):
        _unused_force_rescan = force_rescan
        try:
            run_scan_impl(self)
        except Exception as exc:
            logger.warning("scene scan launch failed", exc_info=True)
            QtWidgets.QMessageBox.warning(self, "오류", f"씬변화 실행 실패: {exc}")


# ---------- 공개 엔트리 ----------
def open_scene_dialog_with_options(host) -> None:
    open_scene_dialog_with_options_impl(host, SceneDialog, logger)


def scene_cache_clear_for_current(host):
    scene_cache_clear_for_current_impl(host, scene_cache_clear_for_path, logger)


def scene_cache_clear_all_public():
    scene_cache_clear_all_public_impl(scene_cache_clear_all)


def refilter_cache_clear_for_current(host):
    refilter_cache_clear_for_current_impl(host, refilter_cache_clear_for_video, logger)


def refilter_cache_clear_all_public():
    refilter_cache_clear_all_public_impl(refilter_cache_clear_all)
