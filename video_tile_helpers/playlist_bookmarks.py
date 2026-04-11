from typing import Any, TYPE_CHECKING, Optional

from PyQt6 import QtCore

if TYPE_CHECKING:
    from video_tile import VideoTile


def set_playlist_entry_start_position(tile: "VideoTile", index: int, position_ms: Optional[int]):
    if position_ms is None:
        _set_playlist_entry_bookmark_group(tile, index, None)
        return
    set_playlist_entry_bookmark_positions(tile, index, [position_ms], cursor=0)


def set_playlist_entry_bookmark_targets(
    tile: "VideoTile",
    index: int,
    bookmark_targets,
    *,
    cursor: Optional[int] = None,
):
    normalized_targets = _normalize_bookmark_targets(bookmark_targets)
    if not normalized_targets:
        _set_playlist_entry_bookmark_group(tile, index, None)
        return
    normalized_cursor = _normalize_cursor(cursor, len(normalized_targets))
    positions = [int(start_ms) for start_ms, _end_ms, _loop_enabled in normalized_targets]
    end_positions = [int(end_ms) if end_ms is not None else -1 for _start_ms, end_ms, _loop_enabled in normalized_targets]
    loop_flags = [1 if bool(loop_enabled) else 0 for _start_ms, _end_ms, loop_enabled in normalized_targets]
    group = {"positions": positions, "cursor": normalized_cursor}
    if any(end_ms is not None for _start_ms, end_ms, _loop_enabled in normalized_targets):
        group["end_positions"] = end_positions
    if any(loop_flags):
        group["loop_flags"] = loop_flags
    _set_playlist_entry_bookmark_group(tile, index, group)


def clear_playlist_entry_start_positions(tile: "VideoTile"):
    tile._playlist_entry_bookmarks = {}
    _clear_playlist_entry_end_guard(tile)


def set_playlist_entry_bookmark_positions(
    tile: "VideoTile",
    index: int,
    positions_ms,
    *,
    cursor: Optional[int] = None,
):
    set_playlist_entry_bookmark_targets(tile, index, [(value, None) for value in list(positions_ms or [])], cursor=cursor)


def playlist_entry_start_position(tile: "VideoTile", index: int) -> Optional[int]:
    group = _playlist_entry_bookmark_group(tile, index)
    positions = list(group.get("positions", []) or [])
    if not positions:
        return None
    cursor = _normalize_cursor(group.get("cursor"), len(positions))
    return positions[cursor]


def playlist_entry_end_position(tile: "VideoTile", index: int) -> Optional[int]:
    group = _playlist_entry_bookmark_group(tile, index)
    positions = list(group.get("positions", []) or [])
    if not positions:
        return None
    cursor = _normalize_cursor(group.get("cursor"), len(positions))
    end_positions = _normalize_end_positions(group.get("end_positions", []), positions)
    if not (0 <= cursor < len(end_positions)):
        return None
    return end_positions[cursor]


def playlist_entries_with_start_positions(tile: "VideoTile") -> list[dict[str, Any]]:
    playlist = list(getattr(tile, "playlist", []) or [])
    return [
        {
            "entry_id": index,
            "path": str(path or ""),
            "positions_ms": playlist_entry_bookmark_positions(tile, index),
            "end_positions_ms": [
                int(end_ms) if end_ms is not None else -1
                for end_ms in _normalize_end_positions(
                    _playlist_entry_bookmark_group(tile, index).get("end_positions", []),
                    playlist_entry_bookmark_positions(tile, index),
                )
            ],
            "loop_flags": [
                1 if enabled else 0
                for enabled in _normalize_loop_flags(
                    _playlist_entry_bookmark_group(tile, index).get("loop_flags", []),
                    playlist_entry_bookmark_positions(tile, index),
                )
            ],
            "cursor": playlist_entry_bookmark_cursor(tile, index),
            "position_ms": playlist_entry_start_position(tile, index),
            "end_ms": playlist_entry_end_position(tile, index),
        }
        for index, path in enumerate(playlist)
    ]


def restore_playlist_entries_with_start_positions(tile: "VideoTile", entries: list[dict[str, Any]]):
    tile.playlist = [str(entry.get("path", "") or "") for entry in entries]
    clear_playlist_entry_start_positions(tile)
    for index, entry in enumerate(entries):
        bookmark_targets = _entry_bookmark_targets(entry)
        if bookmark_targets:
            set_playlist_entry_bookmark_targets(tile, index, bookmark_targets, cursor=entry.get("cursor"))
        else:
            set_playlist_entry_start_position(tile, index, entry.get("position_ms"))


def remove_playlist_entry_start_positions(tile: "VideoTile", removed_rows):
    removed = sorted({max(0, int(row)) for row in (removed_rows or [])})
    if not removed:
        return
    shifted: dict[int, dict[str, Any]] = {}
    for index, group in (getattr(tile, "_playlist_entry_bookmarks", {}) or {}).items():
        normalized_index = max(0, int(index))
        if normalized_index in removed:
            continue
        shift = sum(1 for row in removed if row < normalized_index)
        shifted[max(0, normalized_index - shift)] = _copy_group(group)
    tile._playlist_entry_bookmarks = shifted


def playlist_entry_bookmark_positions(tile: "VideoTile", index: int) -> list[int]:
    group = _playlist_entry_bookmark_group(tile, index)
    return list(group.get("positions", []) or [])


def playlist_entry_bookmark_cursor(tile: "VideoTile", index: int) -> Optional[int]:
    positions = playlist_entry_bookmark_positions(tile, index)
    if not positions:
        return None
    return _normalize_cursor(_playlist_entry_bookmark_group(tile, index).get("cursor"), len(positions))


def select_playlist_entry_bookmark(tile: "VideoTile", index: int, bookmark_subindex: Optional[int] = None):
    try:
        normalized_index = max(0, int(index))
    except Exception:
        return
    tile.current_index = normalized_index
    positions = playlist_entry_bookmark_positions(tile, normalized_index)
    if not positions:
        return
    if bookmark_subindex is None:
        bookmark_subindex = 0
    set_playlist_entry_bookmark_cursor(tile, normalized_index, int(bookmark_subindex))


def set_playlist_entry_bookmark_cursor(tile: "VideoTile", index: int, cursor: int):
    group = _playlist_entry_bookmark_group(tile, index)
    positions = list(group.get("positions", []) or [])
    if not positions:
        return
    updated = _copy_group(group)
    updated["cursor"] = _normalize_cursor(cursor, len(positions))
    _set_playlist_entry_bookmark_group(tile, index, updated)


def advance_current_playlist_bookmark(tile: "VideoTile", direction: int) -> bool:
    try:
        current_index = int(getattr(tile, "current_index", -1))
    except Exception:
        return False
    positions = playlist_entry_bookmark_positions(tile, current_index)
    if len(positions) < 2:
        return False
    current_cursor = playlist_entry_bookmark_cursor(tile, current_index)
    if current_cursor is None:
        current_cursor = 0
    next_cursor = int(current_cursor) + (1 if int(direction) >= 0 else -1)
    if not (0 <= next_cursor < len(positions)):
        return False
    set_playlist_entry_bookmark_cursor(tile, current_index, next_cursor)
    return True


def apply_current_playlist_start_position(tile: "VideoTile", *, attempts: int = 8, delay_ms: int = 220):
    target_path, target_position, target_end, target_auto_advance, target_loop_enabled = _current_playlist_target(tile)
    if not target_path or target_position is None:
        _clear_playlist_entry_end_guard(tile)
        _clear_playlist_entry_loop(tile)
        return
    normalized_path = tile._normalize_media_path(target_path)
    _clear_playlist_entry_end_guard(tile)

    def _attempt(remaining: int):
        current_path = _current_media_path(tile)
        if current_path and tile._normalize_media_path(current_path) == normalized_path:
            _apply_playlist_target_loop_state(
                tile,
                target_position,
                target_end,
                loop_enabled=target_loop_enabled,
                auto_advance=target_auto_advance,
            )
            try:
                tile.safe_seek_from_ui(int(target_position))
            except Exception:
                pass
            return
        if remaining <= 0:
            _apply_playlist_target_loop_state(
                tile,
                target_position,
                target_end,
                loop_enabled=target_loop_enabled,
                auto_advance=target_auto_advance,
            )
            try:
                tile.safe_seek_from_ui(int(target_position))
            except Exception:
                pass
            return
        QtCore.QTimer.singleShot(delay_ms, lambda: _attempt(remaining - 1))

    _attempt(max(0, int(attempts)))


def _current_playlist_target(tile: "VideoTile") -> tuple[Optional[str], Optional[int], Optional[int], bool, bool]:
    playlist = list(getattr(tile, "playlist", []) or [])
    current_index = int(getattr(tile, "current_index", -1))
    if not (0 <= current_index < len(playlist)):
        return None, None, None, False, False
    path = str(playlist[current_index] or "").strip()
    position_ms = playlist_entry_start_position(tile, current_index)
    end_ms, auto_advance, loop_enabled = _playlist_entry_guard_target(tile, current_index)
    if position_ms is None:
        # Legacy fallback for in-memory state created before grouped bookmark entries.
        position_ms = (getattr(tile, "_playlist_start_positions", {}) or {}).get(current_index)
    if not path or position_ms is None:
        return None, None, None, False, False
    if end_ms is not None and int(end_ms) <= int(position_ms):
        end_ms = None
    return path, max(0, int(position_ms)), end_ms, bool(auto_advance), bool(loop_enabled)


def _playlist_entry_guard_target(tile: "VideoTile", index: int) -> tuple[Optional[int], bool, bool]:
    positions = playlist_entry_bookmark_positions(tile, index)
    if not positions:
        return None, False, False
    cursor = playlist_entry_bookmark_cursor(tile, index)
    if cursor is None or not (0 <= int(cursor) < len(positions)):
        cursor = 0
    cursor = int(cursor)
    start_ms = int(positions[cursor])
    explicit_end = playlist_entry_end_position(tile, index)
    loop_flags = _normalize_loop_flags(_playlist_entry_bookmark_group(tile, index).get("loop_flags", []), positions)
    loop_enabled = bool(loop_flags[cursor]) if 0 <= cursor < len(loop_flags) else False
    next_start = int(positions[cursor + 1]) if cursor + 1 < len(positions) else None
    if next_start is not None and next_start <= start_ms:
        next_start = None
    boundary = explicit_end
    if next_start is not None:
        boundary = next_start if boundary is None else min(int(boundary), next_start)
    if boundary is None or int(boundary) <= start_ms:
        return None, False, loop_enabled
    return int(boundary), next_start is not None and not loop_enabled, loop_enabled


def _current_media_path(tile: "VideoTile") -> Optional[str]:
    try:
        return tile._current_media_path()
    except Exception:
        return None


def _playlist_entry_bookmark_group(tile: "VideoTile", index: int) -> dict[str, Any]:
    try:
        normalized_index = max(0, int(index))
    except Exception:
        return {}
    group = (getattr(tile, "_playlist_entry_bookmarks", {}) or {}).get(normalized_index)
    if not isinstance(group, dict):
        return {}
    return group


def _set_playlist_entry_bookmark_group(tile: "VideoTile", index: int, group: Optional[dict[str, Any]]):
    try:
        normalized_index = max(0, int(index))
    except Exception:
        return
    groups = dict(getattr(tile, "_playlist_entry_bookmarks", {}) or {})
    if not group:
        groups.pop(normalized_index, None)
    else:
        groups[normalized_index] = _copy_group(group)
    tile._playlist_entry_bookmarks = groups


def _copy_group(group: dict[str, Any]) -> dict[str, Any]:
    positions = _normalize_positions(group.get("positions", []))
    if not positions:
        return {}
    copied = {
        "positions": positions,
        "cursor": _normalize_cursor(group.get("cursor"), len(positions)),
    }
    end_positions = _normalize_end_positions(group.get("end_positions", []), positions)
    if any(end_ms is not None for end_ms in end_positions):
        copied["end_positions"] = [int(end_ms) if end_ms is not None else -1 for end_ms in end_positions]
    loop_flags = _normalize_loop_flags(group.get("loop_flags", []), positions)
    if any(loop_flags):
        copied["loop_flags"] = [1 if enabled else 0 for enabled in loop_flags]
    return copied


def _normalize_positions(positions_ms) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for value in list(positions_ms or []):
        normalized = max(0, int(value))
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _normalize_bookmark_targets(bookmark_targets) -> list[tuple[int, Optional[int], bool]]:
    out: list[tuple[int, Optional[int], bool]] = []
    seen: set[tuple[int, int, int]] = set()
    for target in list(bookmark_targets or []):
        try:
            start_ms = max(0, int(target[0]))
            end_ms = int(target[1]) if len(target) >= 2 and target[1] is not None else None
            loop_enabled = bool(target[2]) if len(target) >= 3 else False
        except Exception:
            continue
        if end_ms is not None and end_ms <= start_ms:
            end_ms = None
            loop_enabled = False
        if end_ms is None:
            loop_enabled = False
        dedupe_key = (start_ms, int(end_ms) if end_ms is not None else -1, 1 if loop_enabled else 0)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        out.append((start_ms, end_ms, loop_enabled))
    return out


def _normalize_end_positions(end_positions_ms, positions: list[int]) -> list[Optional[int]]:
    raw = list(end_positions_ms or [])
    out: list[Optional[int]] = []
    for index, start_ms in enumerate(positions):
        try:
            end_ms = int(raw[index]) if index < len(raw) else -1
        except Exception:
            end_ms = -1
        out.append(int(end_ms) if end_ms > int(start_ms) else None)
    return out


def _normalize_loop_flags(loop_flags, positions: list[int]) -> list[bool]:
    raw = list(loop_flags or [])
    out: list[bool] = []
    for index, _start_ms in enumerate(positions):
        try:
            enabled = bool(raw[index]) if index < len(raw) else False
        except Exception:
            enabled = False
        out.append(bool(enabled))
    return out


def _entry_bookmark_targets(entry: dict[str, Any]) -> list[tuple[int, Optional[int], bool]]:
    positions = list(entry.get("positions_ms") or [])
    if positions:
        end_positions = list(entry.get("end_positions_ms") or [])
        loop_flags = list(entry.get("loop_flags") or [])
        return _normalize_bookmark_targets(
            (
                (
                    positions[index],
                    end_positions[index] if index < len(end_positions) else None,
                    bool(loop_flags[index]) if index < len(loop_flags) else False,
                )
                for index in range(len(positions))
            )
        )
    try:
        position_ms = entry.get("position_ms")
    except Exception:
        position_ms = None
    if position_ms is None:
        return []
    return _normalize_bookmark_targets([(position_ms, entry.get("end_ms"), bool(entry.get("loop_enabled", False)))])


def _clear_playlist_entry_end_guard(tile: "VideoTile"):
    tile._playlist_bookmark_end_ms = None
    tile._playlist_bookmark_guard_active = False
    tile._playlist_bookmark_auto_advance = False


def _activate_playlist_entry_end_guard(tile: "VideoTile", start_ms: int, end_ms: Optional[int], *, auto_advance: bool = False):
    if end_ms is None or int(end_ms) <= int(start_ms):
        _clear_playlist_entry_end_guard(tile)
        return
    tile._playlist_bookmark_end_ms = int(end_ms)
    tile._playlist_bookmark_guard_active = True
    tile._playlist_bookmark_auto_advance = bool(auto_advance)


def _clear_playlist_entry_loop(tile: "VideoTile"):
    try:
        if bool(getattr(tile, "loop_enabled", False)) or getattr(tile, "posA", None) is not None or getattr(tile, "posB", None) is not None:
            tile.toggle_loop(False)
    except Exception:
        pass


def _apply_playlist_target_loop_state(
    tile: "VideoTile",
    start_ms: int,
    end_ms: Optional[int],
    *,
    loop_enabled: bool,
    auto_advance: bool,
):
    if loop_enabled and end_ms is not None and int(end_ms) > int(start_ms):
        _clear_playlist_entry_end_guard(tile)
        if tile.set_ab_range_ms(int(start_ms), int(end_ms), seek_to_start=False):
            return
    _clear_playlist_entry_loop(tile)
    _activate_playlist_entry_end_guard(tile, start_ms, end_ms, auto_advance=auto_advance)


def _normalize_cursor(cursor: Optional[int], length: int) -> int:
    if length <= 0:
        return 0
    try:
        normalized = int(cursor) if cursor is not None else 0
    except Exception:
        normalized = 0
    return max(0, min(length - 1, normalized))
