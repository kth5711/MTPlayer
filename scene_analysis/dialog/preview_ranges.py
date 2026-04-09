from typing import List, Optional


def _build_seed_points(start_ms: int, end_ms: int, center_hint_ms: Optional[int]) -> tuple[list[int], set[int]]:
    mid = start_ms + ((end_ms - start_ms) // 2)
    center = int(center_hint_ms) if center_hint_ms is not None else mid
    if center < start_ms or center > end_ms:
        center = mid
    points = sorted(set([start_ms, center, end_ms]))
    return points, set(points)


def _fill_midpoint_gaps(points: list[int], point_set: set[int], count: int) -> list[int]:
    while len(points) < count:
        best_gap = -1
        best_mid = None
        for index in range(len(points) - 1):
            left = int(points[index])
            right = int(points[index + 1])
            gap = right - left
            midpoint = left + (gap // 2)
            if gap <= 1 or midpoint in point_set:
                continue
            if gap > best_gap:
                best_gap = gap
                best_mid = midpoint
        if best_mid is None:
            return points
        point_set.add(int(best_mid))
        points = sorted(point_set)
    return points


def _fill_linear_points(start_ms: int, end_ms: int, count: int, point_set: set[int], points: list[int]) -> list[int]:
    for index in range(count):
        point = start_ms + int(round((end_ms - start_ms) * index / float(max(1, count - 1))))
        if point in point_set:
            continue
        point_set.add(point)
        points.append(point)
        if len(point_set) >= count:
            break
    return sorted(point_set)


def _build_seeded_times(start_ms: int, end_ms: int, count: int, center_hint_ms: Optional[int] = None) -> List[int]:
    start_ms = max(0, int(start_ms))
    end_ms = max(start_ms, int(end_ms))
    count = max(1, int(count))
    if end_ms <= start_ms or count <= 1:
        return [start_ms]
    points, point_set = _build_seed_points(start_ms, end_ms, center_hint_ms)
    points = _fill_midpoint_gaps(points, point_set, count)
    if len(points) < count:
        points = _fill_linear_points(start_ms, end_ms, count, point_set, points)
    return points[:count]


def _clamped_duration_sec(duration_sec: int) -> int:
    return max(1, min(10, int(duration_sec)))


def scene_frame_times_for_ms(center_ms: int, duration_sec: int, include_prev: bool = False) -> List[int]:
    duration = _clamped_duration_sec(duration_sec)
    center_ms = max(0, int(center_ms))
    future_span_ms = int(duration * 1000)
    if not include_prev:
        count = max(6, min(24, int(round(duration * 3.0))))
        end_ms = center_ms + future_span_ms
        center_hint_ms = center_ms + ((end_ms - center_ms) // 2)
        return _build_seeded_times(center_ms, end_ms, count, center_hint_ms=center_hint_ms)
    count = max(8, min(28, int(round(duration * 4.5)) + 1))
    prev_span_ms = max(500, int(round(future_span_ms / 2.0)))
    start_ms = max(0, center_ms - prev_span_ms)
    end_ms = max(start_ms, center_ms + future_span_ms)
    return _build_seeded_times(start_ms, end_ms, count, center_hint_ms=center_ms)


def scene_frame_times_for_range(start_ms: int, end_ms: int, duration_sec: int, include_prev: bool = False) -> List[int]:
    duration = _clamped_duration_sec(duration_sec)
    if include_prev:
        count = max(7, min(25, int(round(duration * 4.0)) + 1))
        half_span_ms = max(500, int(round((duration * 1000) / 2.0)))
        start_ms = max(0, int(start_ms) - half_span_ms)
        end_ms = max(start_ms, int(end_ms) + half_span_ms)
    else:
        count = max(6, min(24, int(round(duration * 3.0))))
        start_ms = max(0, int(start_ms))
        end_ms = max(start_ms, int(end_ms))
    return _build_seeded_times(start_ms, end_ms, count)
