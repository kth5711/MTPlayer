import logging
from typing import List, Tuple

from .scene_timeline import (
    current_video_length_ms,
    scene_end_ms_from_starts,
    timeline_scene_starts_prefilter_sorted,
)


logger = logging.getLogger(__name__)


def _scene_range_fallback_sec(dialog) -> int:
    try:
        return int(dialog.spn_scene_frame_secs.value() if hasattr(dialog, "spn_scene_frame_secs") else 3)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        logger.debug("scene range fallback_sec read failed", exc_info=True)
        return 3


def build_direct_refilter_source(dialog, interval_sec: int) -> List[tuple[int, float]]:
    step_ms = max(1000, int(max(1, interval_sec) * 1000))
    length_ms = current_video_length_ms(dialog)
    if length_ms <= 0:
        return [(0, 0.0)]
    starts = list(range(0, max(1, int(length_ms)), step_ms))
    if not starts:
        starts = [0]
    tail = max(0, int(length_ms) - 1)
    if tail - starts[-1] >= (step_ms // 2):
        starts.append(tail)
    starts = sorted(set(max(0, int(x)) for x in starts))
    return [(ms, 0.0) for ms in starts]


def scene_ranges_to_next_prefilter_from_starts(dialog, scene_starts_ms: List[int]) -> List[Tuple[int, int]]:
    starts = timeline_scene_starts_prefilter_sorted(dialog)
    fallback_sec = _scene_range_fallback_sec(dialog)
    out: List[Tuple[int, int]] = []
    seen = set()
    for value in sorted(set(int(x) for x in (scene_starts_ms or []))):
        start_ms = max(0, int(value))
        end_ms = scene_end_ms_from_starts(dialog, start_ms, starts, fallback_sec=fallback_sec)
        if end_ms <= start_ms:
            continue
        pair = (start_ms, end_ms)
        if pair in seen:
            continue
        seen.add(pair)
        out.append(pair)
    return out


def _similarity_run_ranges(starts: List[int], sim_map: dict, threshold: float) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    run_start = None
    run_last = None
    for ms in starts:
        point = int(ms)
        sim = sim_map.get(point)
        is_hit = (sim is not None) and (float(sim) >= threshold)
        if is_hit:
            if run_start is None:
                run_start = point
            run_last = point
            continue
        if run_start is not None:
            end_ms = max(run_start, point - 1)
            if end_ms > run_start:
                out.append((run_start, end_ms))
            run_start = None
            run_last = None
    if run_start is not None:
        out.append((run_start, int(run_last if run_last is not None else run_start)))
    return out


def _dedup_ranges(ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    seen = set()
    for start_ms, end_ms in ranges:
        pair = (int(start_ms), int(end_ms))
        if pair in seen:
            continue
        seen.add(pair)
        out.append(pair)
    return out


def scene_ranges_to_similarity_drop(dialog, sim_thr: float) -> List[Tuple[int, int]]:
    starts = timeline_scene_starts_prefilter_sorted(dialog)
    sim_map = dict(getattr(dialog, "_last_refilter_sim_by_ms", {}) or {})
    if not starts or not sim_map:
        return []
    fallback_sec = _scene_range_fallback_sec(dialog)
    ranges = _similarity_run_ranges(starts, sim_map, float(sim_thr))
    out: List[Tuple[int, int]] = []
    for start_ms, end_ms in ranges:
        if end_ms == start_ms:
            end_ms = scene_end_ms_from_starts(dialog, start_ms, starts, fallback_sec=fallback_sec)
        if end_ms > start_ms:
            out.append((start_ms, end_ms))
    return _dedup_ranges(out)
