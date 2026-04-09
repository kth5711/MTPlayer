from typing import List
import logging

from .thumbnail_loading import (
    resume_thumbnail_loading as resume_thumbnail_loading_impl,
    schedule_thumbnail_resume as schedule_thumbnail_resume_impl,
)


logger = logging.getLogger(__name__)


def apply_refilter_pairs(
    dialog,
    source: List[tuple[int, float]],
    sim_pairs: List[tuple[int, float]],
    mode: str,
    cache_hit: bool = False,
    allow_auto_clip: bool = True,
) -> None:
    sim_thr = float(dialog.spn_sim_thr.value())
    sim_map = {int(ms): float(sim) for ms, sim in (sim_pairs or [])}
    dialog._last_refilter_sim_by_ms = dict(sim_map)
    filtered_data = _filter_refilter_hits(source, sim_map, sim_thr)
    display_data, auto_clip_data, grouped_note = _apply_direct_grouping(dialog, filtered_data, sim_map)
    dialog._similarity_by_ms = _shown_similarity_map(display_data, sim_map)
    dialog._refilter_active = True
    dialog.btn_refilter_clear.setEnabled(True)
    _refresh_refilter_result_view(dialog, display_data)
    _update_refilter_status(dialog, source, display_data, mode, sim_thr, cache_hit, grouped_note)
    if bool(allow_auto_clip):
        dialog._auto_save_refilter_scene_clips(auto_clip_data)


def schedule_refilter_reapply(dialog, status_text: str, debounce_ms: int = 180) -> None:
    if bool(getattr(dialog, "_cache_hist_loading", False)):
        return
    if dialog.refilter_worker is not None and dialog.refilter_worker.isRunning():
        return
    if not bool(getattr(dialog, "_refilter_active", False)):
        return
    dialog._thumbnail_reload_suppressed = True
    _clear_reapply_thumbnail_jobs(dialog)
    if _arm_reapply_timer(dialog, debounce_ms):
        _set_reapply_status(dialog, status_text)
        return
    dialog._commit_refilter_reapply()


def on_sim_threshold_changed(dialog, *_args) -> None:
    dialog._schedule_refilter_reapply(
        f"유사도 임계값 조정 중… ({float(dialog.spn_sim_thr.value()):.2f})",
        debounce_ms=180,
    )


def on_refilter_direct_group_changed(dialog, *_args) -> None:
    if dialog._current_refilter_source_mode() != "direct":
        return
    group_on = bool(dialog.chk_refilter_direct_group.isChecked())
    if hasattr(dialog, "spn_refilter_direct_group_band"):
        dialog.spn_refilter_direct_group_band.setEnabled(group_on)
    dialog._schedule_refilter_reapply(
        "직행 결과 구간 묶기 적용 중…" if group_on else "직행 결과 구간 묶기 해제 중…",
        debounce_ms=120,
    )


def commit_refilter_reapply(dialog) -> None:
    source = list(getattr(dialog, "_refilter_source_data", []) or [])
    if not source:
        over = list(getattr(dialog, "_refilter_source_override_ms", []) or [])
        if over:
            source = [(int(ms), 0.0) for ms in sorted(set(int(x) for x in over if int(x) >= 0))]
    if not source:
        dialog._thumbnail_reload_suppressed = False
        return
    sim_map = dict(getattr(dialog, "_last_refilter_sim_by_ms", {}) or {})
    sim_pairs = [(int(ms), float(sim_map[int(ms)])) for ms, _score in source if int(ms) in sim_map]
    if not sim_pairs:
        dialog._thumbnail_reload_suppressed = False
        return
    dialog._apply_refilter_pairs(
        source,
        sim_pairs,
        dialog._current_refilter_mode(),
        cache_hit=True,
        allow_auto_clip=False,
    )
    dialog._schedule_thumbnail_resume(280)


def schedule_thumbnail_resume(dialog, debounce_ms: int = 280) -> None:
    schedule_thumbnail_resume_impl(dialog, debounce_ms)


def resume_thumbnail_loading(dialog) -> None:
    resume_thumbnail_loading_impl(dialog)


def _filter_refilter_hits(
    source: List[tuple[int, float]],
    sim_map: dict[int, float],
    sim_thr: float,
) -> List[tuple[int, float]]:
    hit_data: List[tuple[int, float]] = []
    for ms, scene_score in source:
        sim = sim_map.get(int(ms))
        if sim is None:
            continue
        if sim >= sim_thr:
            hit_data.append((int(ms), float(scene_score)))
    return hit_data


def _apply_direct_grouping(
    dialog,
    filtered_data: List[tuple[int, float]],
    sim_map: dict[int, float],
) -> tuple[List[tuple[int, float]], List[tuple[int, float]], str]:
    dialog._direct_group_clip_ranges = {}
    if dialog._current_refilter_source_mode() != "direct":
        return filtered_data, filtered_data, ""
    if not dialog._current_refilter_direct_group_enabled():
        return filtered_data, filtered_data, ""
    grouped, clip_map = dialog._collapse_direct_hits_first_only(filtered_data, sim_map)
    if not grouped:
        return filtered_data, filtered_data, ""
    dialog._direct_group_clip_ranges = dict(clip_map)
    note = ""
    if len(grouped) != len(filtered_data):
        note = f" | 구간묶음 {len(filtered_data)}→{len(grouped)}"
    return grouped, grouped, note


def _shown_similarity_map(
    filtered_data: List[tuple[int, float]],
    sim_map: dict[int, float],
) -> dict[int, float]:
    shown_sim = {}
    for ms, _scene_score in filtered_data:
        sim = sim_map.get(int(ms))
        if sim is not None:
            shown_sim[int(ms)] = float(sim)
    return shown_sim


def _refresh_refilter_result_view(dialog, filtered_data: List[tuple[int, float]]) -> None:
    pts = [ms for ms, _ in filtered_data]
    dialog._populate_from_result(dialog.current_path, pts, filtered_data, reset_similarity=False)
    dialog._update_scene_clip_button_enabled()


def _update_refilter_status(
    dialog,
    source: List[tuple[int, float]],
    filtered_data: List[tuple[int, float]],
    mode: str,
    sim_thr: float,
    cache_hit: bool,
    grouped_note: str,
) -> None:
    mode_label = dialog._refilter_mode_label(mode)
    src_label = "캐시" if cache_hit else "분석"
    hint = " (결과 동일: 임계값 상향 권장)" if len(filtered_data) == len(source) and len(source) > 0 else ""
    dialog.lbl_status.setText(
        f"{mode_label} 재필터 완료({src_label}): {len(filtered_data)} / {len(source)}개 (임계값>={sim_thr:.2f}){hint}{grouped_note}"
    )


def _clear_reapply_thumbnail_jobs(dialog) -> None:
    try:
        dialog.thumb_worker.clear_jobs()
    except RuntimeError:
        logger.debug("refilter reapply thumbnail clear_jobs skipped", exc_info=True)
    try:
        thumb_timer = getattr(dialog, "_thumbnail_resume_timer", None)
        if thumb_timer is not None and thumb_timer.isActive():
            thumb_timer.stop()
    except RuntimeError:
        logger.debug("refilter reapply thumbnail resume timer stop skipped", exc_info=True)


def _arm_reapply_timer(dialog, debounce_ms: int) -> bool:
    timer = getattr(dialog, "_refilter_reapply_timer", None)
    if timer is None:
        return False
    if int(debounce_ms) <= 0:
        if timer.isActive():
            timer.stop()
        return False
    timer.setInterval(max(1, int(debounce_ms)))
    timer.start()
    return True


def _set_reapply_status(dialog, status_text: str) -> None:
    try:
        dialog.lbl_status.setText(str(status_text))
    except RuntimeError:
        logger.debug("refilter reapply status update skipped", exc_info=True)
