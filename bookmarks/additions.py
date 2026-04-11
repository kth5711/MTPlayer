import os
import time
import uuid
from typing import Callable, Iterable

from PyQt6 import QtWidgets

from i18n import tr

from .dock import refresh_bookmark_dock
from .shared import bookmark_matches_path, format_ms, format_range_ms, normalize_path, path_signature_fields, status
from .state import bookmark_end_ms, default_category_for_path, refresh_bookmark_marks


def add_bookmark_from_current(main):
    tile = _candidate_tile(main)
    if tile is None:
        QtWidgets.QMessageBox.information(main, tr(main, "북마크"), tr(main, "북마크를 추가할 재생 중 영상이 없습니다."))
        return
    main.add_bookmark_from_tile(tile)


def _candidate_tile(main):
    for tile in _tile_candidates(main):
        try:
            if tile._current_media_path():
                return tile
        except Exception:
            continue
    return None


def _tile_candidates(main):
    try:
        yield from list(main._selected_tiles())
    except Exception:
        pass
    yield from list(getattr(main.canvas, "tiles", []))


def add_bookmarks_for_path_positions(main, path: str, positions_ms) -> tuple[int, int]:
    normalized_path = normalize_path(path)
    wanted_positions = sorted({max(0, int(ms)) for ms in (positions_ms or [])})
    if not normalized_path or not wanted_positions:
        return 0, 0
    category = default_category_for_path(main, normalized_path)
    added = skipped = 0
    for position_ms in wanted_positions:
        if _is_duplicate_bookmark(main, normalized_path, position_ms, None):
            skipped += 1
            continue
        main.bookmarks.append(_bookmark_entry(normalized_path, position_ms, category, end_ms=None))
        added += 1
    if added > 0:
        _persist_bookmark_add(main)
    return added, skipped


def add_bookmarks_for_path_ranges(main, path: str, ranges_ms) -> tuple[int, int]:
    normalized_path = normalize_path(path)
    normalized_ranges = _normalize_ranges(ranges_ms)
    if not normalized_path or not normalized_ranges:
        return 0, 0
    category = default_category_for_path(main, normalized_path)
    added = skipped = 0
    for start_ms, end_ms in normalized_ranges:
        if _is_duplicate_bookmark(main, normalized_path, start_ms, end_ms):
            skipped += 1
            continue
        main.bookmarks.append(_bookmark_entry(normalized_path, start_ms, category, end_ms=end_ms))
        added += 1
    if added > 0:
        _persist_bookmark_add(main)
    return added, skipped


def _normalize_ranges(ranges_ms) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for value in list(ranges_ms or []):
        try:
            start_ms = max(0, int(value[0]))
            end_ms = max(0, int(value[1]))
        except Exception:
            continue
        if end_ms <= start_ms:
            continue
        key = (start_ms, end_ms)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    out.sort()
    return out


def _is_duplicate_bookmark(main, path: str, position_ms: int, end_ms: int | None) -> bool:
    for entry in getattr(main, "bookmarks", []) or []:
        if not bookmark_matches_path(entry, path):
            continue
        entry_position = int(entry.get("position_ms", 0))
        entry_end = bookmark_end_ms(entry, position_ms=entry_position)
        if abs(entry_position - int(position_ms)) > 500:
            continue
        if end_ms is None and entry_end is None:
            return True
        if end_ms is not None and entry_end is not None and abs(int(entry_end) - int(end_ms)) <= 500:
            return True
    return False


def _bookmark_entry(path: str, position_ms: int, category: str, *, end_ms: int | None) -> dict:
    entry = {
        "id": uuid.uuid4().hex,
        "path": path,
        "position_ms": int(position_ms),
        "created_at": int(time.time()),
        "category": category,
    }
    entry.update(path_signature_fields(path))
    if end_ms is not None and int(end_ms) > int(position_ms):
        entry["end_ms"] = int(end_ms)
    return entry


def _persist_bookmark_add(main):
    refresh_bookmark_dock(main, keep_selection=False)
    refresh_bookmark_marks(main)
    try:
        main.save_config()
    except Exception:
        pass


def add_bookmark_from_tile(main, tile):
    if tile is None:
        return
    path = _tile_media_path(tile)
    if not path:
        QtWidgets.QMessageBox.information(main, tr(main, "북마크"), tr(main, "현재 타일에 열린 영상이 없습니다."))
        return
    loop_range = _tile_loop_range_ms(tile)
    if loop_range is not None:
        start_ms, end_ms = loop_range
        added, skipped = add_bookmarks_for_path_ranges(main, path, [(start_ms, end_ms)])
        if added <= 0:
            refresh_bookmark_dock(main, keep_selection=False)
            refresh_bookmark_marks(main)
            status(main, tr(main, "이미 북마크가 있습니다: {time}", time=format_range_ms(start_ms, end_ms)))
            return
        status(main, _bookmark_added_text(main, path, start_ms, skipped, end_ms=end_ms))
        return
    position_ms = _tile_position_ms(tile)
    added, skipped = add_bookmarks_for_path_positions(main, path, [position_ms])
    if added <= 0:
        refresh_bookmark_dock(main, keep_selection=False)
        refresh_bookmark_marks(main)
        status(main, tr(main, "이미 북마크가 있습니다: {time}", time=format_ms(position_ms)))
        return
    status(main, _bookmark_added_text(main, path, position_ms, skipped))


def set_bookmark_end_from_open_tiles(main, entries: Iterable[dict]) -> tuple[int, int]:
    bookmark_entries = _editable_bookmark_entries(entries)
    if not bookmark_entries:
        QtWidgets.QMessageBox.information(main, tr(main, "북마크"), tr(main, "끝 시점을 추가/수정할 북마크가 없습니다."))
        return 0, 0
    return _apply_bookmark_end_update(
        main,
        bookmark_entries,
        resolver=lambda entry: _resolve_bookmark_end_from_open_tile(main, entry),
        empty_message=tr(main, "현재 위치를 끝 시점으로 쓸 수 있는 열린 타일이 없습니다."),
    )


def set_bookmark_end_fixed_duration(main, entries: Iterable[dict], seconds: int) -> tuple[int, int]:
    bookmark_entries = _editable_bookmark_entries(entries)
    if not bookmark_entries:
        QtWidgets.QMessageBox.information(main, tr(main, "북마크"), tr(main, "끝 시점을 추가/수정할 북마크가 없습니다."))
        return 0, 0
    duration_ms = max(1, int(seconds)) * 1000
    return _apply_bookmark_end_update(
        main,
        bookmark_entries,
        resolver=lambda entry, duration_ms=duration_ms: _resolve_bookmark_end_from_duration(entry, duration_ms),
        empty_message=tr(main, "끝 시점을 바꿀 수 있는 북마크가 없습니다."),
    )


def adjust_bookmark_end_delta(main, entries: Iterable[dict], delta_ms: int) -> tuple[int, int]:
    bookmark_entries = _editable_bookmark_entries(entries)
    if not bookmark_entries:
        QtWidgets.QMessageBox.information(main, tr(main, "북마크"), tr(main, "끝 시점을 추가/수정할 북마크가 없습니다."))
        return 0, 0
    normalized_delta = int(delta_ms)
    return _apply_bookmark_end_update(
        main,
        bookmark_entries,
        resolver=lambda entry, delta_ms=normalized_delta: _resolve_bookmark_end_with_delta(entry, delta_ms),
        empty_message=tr(main, "끝 시점을 바꿀 수 있는 북마크가 없습니다."),
    )


def _tile_media_path(tile):
    try:
        current_path = tile._current_playlist_path() or tile._current_media_path()
        return normalize_path(current_path) if current_path else None
    except Exception:
        return None


def _tile_position_ms(tile) -> int:
    try:
        return int(tile.current_playback_ms())
    except Exception:
        return 0


def _bookmark_added_text(main, path: str, position_ms: int, skipped: int, *, end_ms: int | None = None) -> str:
    suffix = tr(main, " (+중복 {count}개 제외)", count=skipped) if skipped > 0 else ""
    return tr(
        main,
        "북마크 추가: {name} @ {time}{suffix}",
        name=os.path.basename(path) or path,
        time=format_range_ms(position_ms, end_ms),
        suffix=suffix,
    )


def _tile_loop_range_ms(tile) -> tuple[int, int] | None:
    try:
        loop_enabled = bool(getattr(tile, "loop_enabled", False))
        pos_a = getattr(tile, "posA", None)
        pos_b = getattr(tile, "posB", None)
    except Exception:
        loop_enabled = False
        pos_a = pos_b = None
    if not loop_enabled or pos_a is None or pos_b is None:
        return None
    length_ms = _tile_length_ms(tile)
    if length_ms <= 0:
        return None
    start_ms = max(0, min(length_ms - 1, int(round(float(pos_a) * float(length_ms)))))
    end_ms = max(start_ms + 1, min(length_ms, int(round(float(pos_b) * float(length_ms)))))
    if end_ms <= start_ms:
        return None
    return start_ms, end_ms


def _tile_length_ms(tile) -> int:
    try:
        length_ms = int(tile.mediaplayer.get_length() or 0)
    except Exception:
        length_ms = 0
    if length_ms > 0:
        return length_ms
    path = _tile_media_path(tile)
    if not path or not os.path.exists(path):
        return 0
    try:
        import cv2  # type: ignore

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            cap.release()
            return 0
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        total_frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        cap.release()
        if fps > 1e-6 and total_frames > 1.0:
            return max(0, int(round((total_frames / fps) * 1000.0)))
    except Exception:
        return 0
    return 0


def _editable_bookmark_entries(entries: Iterable[dict]) -> list[dict]:
    return [entry for entry in list(entries or []) if isinstance(entry, dict)]


def _apply_bookmark_end_update(
    main,
    bookmark_entries: list[dict],
    *,
    resolver: Callable[[dict], int | None],
    empty_message: str,
) -> tuple[int, int]:
    updated = skipped = 0
    for entry in bookmark_entries:
        if _apply_bookmark_end_update_to_entry(main, entry, resolver):
            updated += 1
        else:
            skipped += 1
    if updated > 0:
        refresh_bookmark_dock(main, keep_selection=True)
        refresh_bookmark_marks(main)
        try:
            main.save_config()
        except Exception:
            pass
        status(main, tr(main, "북마크 끝 시점 추가/수정: {count}개 (+건너뜀 {skipped}개)", count=updated, skipped=skipped))
        return updated, skipped
    QtWidgets.QMessageBox.information(main, tr(main, "북마크"), empty_message)
    return 0, skipped


def _apply_bookmark_end_update_to_entry(main, entry: dict, resolver: Callable[[dict], int | None]) -> bool:
    path = str(entry.get("path", "") or "").strip()
    if not path:
        return False
    start_ms = max(0, int(entry.get("position_ms", 0) or 0))
    end_ms = resolver(entry)
    if end_ms is None or int(end_ms) <= start_ms:
        return False
    normalized_path = normalize_path(path)
    if _would_duplicate_bookmark(main, entry, normalized_path, start_ms, int(end_ms)):
        return False
    entry["end_ms"] = int(end_ms)
    return True


def _resolve_bookmark_end_from_open_tile(main, entry: dict) -> int | None:
    tile = _find_matching_open_tile(main, entry)
    if tile is None:
        return None
    end_ms = _tile_position_ms(tile)
    return int(end_ms)


def _resolve_bookmark_end_from_duration(entry: dict, duration_ms: int) -> int | None:
    start_ms = max(0, int(entry.get("position_ms", 0) or 0))
    end_ms = start_ms + max(1, int(duration_ms))
    return int(end_ms) if end_ms > start_ms else None


def _resolve_bookmark_end_with_delta(entry: dict, delta_ms: int) -> int | None:
    start_ms = max(0, int(entry.get("position_ms", 0) or 0))
    current_end = bookmark_end_ms(entry, position_ms=start_ms)
    base_end = current_end if current_end is not None else start_ms
    next_end = int(base_end) + int(delta_ms)
    return int(next_end) if next_end > start_ms else None


def _find_matching_open_tile(main, entry: dict):
    try:
        selected_tiles = list(main._selected_tiles())
    except Exception:
        selected_tiles = []
    all_tiles = list(getattr(getattr(main, "canvas", None), "tiles", []) or [])
    for tile in selected_tiles + [tile for tile in all_tiles if tile not in selected_tiles]:
        current_path = _tile_media_path(tile)
        if current_path and bookmark_matches_path(entry, current_path):
            return tile
    return None


def _would_duplicate_bookmark(main, current_entry: dict, path: str, position_ms: int, end_ms: int) -> bool:
    for entry in getattr(main, "bookmarks", []) or []:
        if entry is current_entry:
            continue
        if not bookmark_matches_path(entry, path):
            continue
        entry_position = int(entry.get("position_ms", 0))
        entry_end = bookmark_end_ms(entry, position_ms=entry_position)
        if abs(entry_position - int(position_ms)) > 500:
            continue
        if entry_end is not None and abs(int(entry_end) - int(end_ms)) <= 500:
            return True
    return False
