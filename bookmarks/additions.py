import os
import time
import uuid

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
    position_ms = _tile_position_ms(tile)
    added, skipped = add_bookmarks_for_path_positions(main, path, [position_ms])
    if added <= 0:
        refresh_bookmark_dock(main, keep_selection=False)
        refresh_bookmark_marks(main)
        status(main, tr(main, "이미 북마크가 있습니다: {time}", time=format_ms(position_ms)))
        return
    status(main, _bookmark_added_text(main, path, position_ms, skipped))


def _tile_media_path(tile):
    try:
        return normalize_path(tile._current_media_path())
    except Exception:
        return None


def _tile_position_ms(tile) -> int:
    try:
        return int(tile.current_playback_ms())
    except Exception:
        return 0


def _bookmark_added_text(main, path: str, position_ms: int, skipped: int) -> str:
    suffix = tr(main, " (+중복 {count}개 제외)", count=skipped) if skipped > 0 else ""
    return tr(
        main,
        "북마크 추가: {name} @ {time}{suffix}",
        name=os.path.basename(path) or path,
        time=format_range_ms(position_ms, None),
        suffix=suffix,
    )
