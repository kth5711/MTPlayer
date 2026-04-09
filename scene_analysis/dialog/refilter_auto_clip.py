from typing import List
import logging
import os


logger = logging.getLogger(__name__)


def auto_save_refilter_scene_clips(dialog, filtered_data: List[tuple[int, float]]) -> None:
    if not bool(dialog.chk_auto_clip_after_refilter.isChecked() if hasattr(dialog, "chk_auto_clip_after_refilter") else False):
        return
    if not filtered_data:
        dialog.lbl_status.setText("자동클립저장: 필터 결과가 없어 건너뜀")
        return
    if not dialog.current_path or not os.path.exists(dialog.current_path):
        dialog.lbl_status.setText("자동클립저장: 영상 경로 없음")
        return

    clip_ranges, mode_label = _auto_clip_ranges(dialog, filtered_data)
    if not clip_ranges:
        dialog.lbl_status.setText("자동클립저장: 유효 구간 없음")
        return
    try:
        dialog._enqueue_clip_export_job(
            "ranges",
            clip_ranges,
            mode_label=f"자동클립/{mode_label}",
            source="auto",
        )
    except Exception as exc:
        logger.warning("auto clip export enqueue failed", exc_info=True)
        dialog.lbl_status.setText(f"자동클립저장 실패: {exc}")


def _auto_clip_ranges(dialog, filtered_data: List[tuple[int, float]]) -> tuple[List[tuple[int, int]], str]:
    starts = [int(ms) for ms, _ in (filtered_data or [])]
    if dialog._current_auto_clip_end_mode() != "sim_drop":
        return dialog._scene_ranges_to_next_prefilter_from_starts(starts), "다음씬"
    sim_thr = float(dialog.spn_sim_thr.value())
    clip_ranges = dialog._scene_ranges_to_similarity_drop(sim_thr)
    if clip_ranges:
        return clip_ranges, "유사도하강"
    return dialog._scene_ranges_to_next_prefilter_from_starts(starts), "다음씬(대체)"
