import os
from typing import Optional

from PyQt6 import QtWidgets
from i18n import tr

from .shared import bookmark_matches_path, normalize_path_or_empty


def load_targets_into_tiles(
    main,
    targets,
    label: str,
    *,
    prefer_open_parent_tiles: bool = False,
):
    valid_targets = _existing_targets(main, targets)
    if not valid_targets:
        QtWidgets.QMessageBox.information(
            main,
            tr(main, "북마크"),
            tr(main, "열 수 있는 북마크 대상이 없습니다."),
        )
        return
    tiles = _ensure_tiles(main)
    if not tiles:
        return
    loaded_tiles = 0
    for tile, tile_targets in zip(
        tiles,
        _group_targets_for_tiles(tiles, valid_targets, prefer_open_parent_tiles=prefer_open_parent_tiles),
    ):
        if _load_target_group_into_tile(tile, tile_targets):
            loaded_tiles += 1
    _refresh_playlist_after_bookmark_open(main)
    _show_bookmark_open_status(main, label, targets, valid_targets, loaded_tiles)


def _normalize_path(path: str) -> str:
    return os.path.normpath(os.path.abspath(path))


def _target_entry(path: str, position_ms: int, end_ms: Optional[int], video_mtime_ns: int = 0, video_size: int = 0) -> dict:
    return {
        "path": path,
        "position_ms": int(position_ms),
        "end_ms": end_ms,
        "video_mtime_ns": int(video_mtime_ns or 0),
        "video_size": int(video_size or 0),
    }


def _resolve_target_path(main, path: str, video_mtime_ns: int = 0, video_size: int = 0) -> str:
    normalized = normalize_path_or_empty(path)
    if normalized and os.path.exists(normalized):
        return normalized
    probe = _target_entry(path, 0, None, video_mtime_ns, video_size)
    for tile in list(getattr(getattr(main, "canvas", None), "tiles", []) or []):
        try:
            current = tile._current_media_path()
        except Exception:
            current = ""
        current_norm = normalize_path_or_empty(current)
        if current_norm and bookmark_matches_path(probe, current_norm):
            return current_norm
    return normalized


def _ensure_tiles(main):
    tiles = list(getattr(getattr(main, "canvas", None), "tiles", []) or [])
    if tiles:
        return tiles
    try:
        main.canvas.add_tile()
    except Exception:
        return []
    return list(getattr(main.canvas, "tiles", []) or [])


def _normalized_target(target) -> Optional[tuple[str, int, Optional[int], int, int]]:
    try:
        path = str(target[0] or "").strip()
        position_ms = max(0, int(target[1]))
        end_ms = int(target[2]) if len(target) >= 3 and target[2] is not None else None
        video_mtime_ns = int(target[3]) if len(target) >= 4 and target[3] is not None else 0
        video_size = int(target[4]) if len(target) >= 5 and target[4] is not None else 0
    except Exception:
        return None
    if not path:
        return None
    if end_ms is not None and end_ms <= position_ms:
        end_ms = None
    return path, position_ms, end_ms, video_mtime_ns, video_size


def _existing_targets(main, targets) -> list[tuple[str, int, Optional[int]]]:
    out: list[tuple[str, int, Optional[int]]] = []
    for target in list(targets or []):
        normalized = _normalized_target(target)
        if normalized is None:
            continue
        path, position_ms, end_ms, video_mtime_ns, video_size = normalized
        resolved_path = _resolve_target_path(main, path, video_mtime_ns, video_size)
        if os.path.exists(resolved_path):
            out.append((resolved_path, position_ms, end_ms))
    return out


def _group_targets_for_tiles(
    tiles,
    targets: list[tuple[str, int, Optional[int]]],
    *,
    prefer_open_parent_tiles: bool = False,
) -> list[list[tuple[str, int, Optional[int]]]]:
    grouped: list[list[tuple[str, int, Optional[int]]]] = [[] for _ in tiles]
    if not grouped:
        return grouped
    if not prefer_open_parent_tiles:
        for index, target in enumerate(targets):
            grouped[index % len(grouped)].append(target)
        return grouped
    tile_owners = _initial_tile_owners(_group_targets_by_path(targets), [_tile_media_path(tile) for tile in tiles])
    for path, path_targets in _ordered_target_groups(targets, tile_owners):
        _assign_path_targets(grouped, tile_owners, path, path_targets)
    return grouped


def _load_target_group_into_tile(tile, tile_targets: list[tuple[str, int, Optional[int]]]) -> bool:
    if not tile_targets:
        return False
    tile.clear_playlist()
    grouped_targets: dict[str, list[tuple[int, Optional[int]]]] = {}
    for path, position_ms, end_ms in tile_targets:
        grouped_targets.setdefault(path, []).append((int(position_ms), end_ms))
    for path, bookmark_targets in grouped_targets.items():
        tile.playlist.append(path)
        tile.set_playlist_entry_bookmark_targets(len(tile.playlist) - 1, bookmark_targets, cursor=0)
    tile.select_playlist_entry_bookmark(0, 0)
    loaded = bool(tile.set_media(tile.playlist[0], show_error_dialog=False))
    if loaded:
        tile.play()
        tile._apply_current_playlist_start_position()
    tile._update_add_button()
    return loaded


def _tile_media_path(tile) -> str:
    try:
        path = tile._current_media_path()
    except Exception:
        path = None
    if not path:
        return ""
    return _normalize_path(str(path))


def _group_targets_by_path(targets: list[tuple[str, int, Optional[int]]]) -> list[tuple[str, list[tuple[str, int, Optional[int]]]]]:
    ordered_paths: list[str] = []
    grouped: dict[str, list[tuple[str, int, Optional[int]]]] = {}
    for path, position_ms, end_ms in targets:
        normalized_path = _normalize_path(path)
        if normalized_path not in grouped:
            grouped[normalized_path] = []
            ordered_paths.append(normalized_path)
        grouped[normalized_path].append((path, int(position_ms), end_ms))
    return [(path, grouped[path]) for path in ordered_paths]


def _candidate_tile_indices(tile_count: int, tile_owners: dict[int, str], target_path: str) -> list[int]:
    owned = [index for index, owner in tile_owners.items() if owner == target_path]
    free = [index for index in range(tile_count) if index not in tile_owners]
    if owned or free:
        return owned + free
    return list(range(tile_count))


def _initial_tile_owners(
    grouped_targets: list[tuple[str, list[tuple[str, int, Optional[int]]]]],
    tile_paths: list[str],
) -> dict[int, str]:
    target_paths = {path for path, _ in grouped_targets}
    return {
        index: path
        for index, path in enumerate(tile_paths)
        if path and path in target_paths
    }


def _ordered_target_groups(
    targets: list[tuple[str, int, Optional[int]]],
    tile_owners: dict[int, str],
) -> list[tuple[str, list[tuple[str, int, Optional[int]]]]]:
    grouped_targets = _group_targets_by_path(targets)
    reserved_paths = set(tile_owners.values())
    matched = [(path, path_targets) for path, path_targets in grouped_targets if path in reserved_paths]
    unmatched = [(path, path_targets) for path, path_targets in grouped_targets if path not in reserved_paths]
    return matched + unmatched


def _assign_path_targets(
    grouped: list[list[tuple[str, int]]],
    tile_owners: dict[int, str],
    target_path: str,
    path_targets: list[tuple[str, int, Optional[int]]],
):
    candidate_indices = _candidate_tile_indices(len(grouped), tile_owners, target_path)
    used_indices: set[int] = set()
    for offset, target in enumerate(path_targets):
        target_index = candidate_indices[offset % len(candidate_indices)]
        grouped[target_index].append(target)
        used_indices.add(target_index)
    for target_index in used_indices:
        tile_owners.setdefault(target_index, target_path)


def _refresh_playlist_after_bookmark_open(main):
    try:
        main.update_playlist()
    except Exception:
        pass
    try:
        main.setFocus()
    except Exception:
        pass


def _show_bookmark_open_status(
    main,
    label: str,
    targets,
    valid_targets,
    loaded_tiles: int,
):
    skipped = max(0, len(targets) - len(valid_targets))
    extra = tr(main, ", 누락 {count}개", count=skipped) if skipped > 0 else ""
    try:
        main.statusBar().showMessage(
            tr(
                main,
                "{label}: {valid_count}개 항목을 {loaded_tiles}개 타일에 분배{extra}",
                label=label,
                valid_count=len(valid_targets),
                loaded_tiles=loaded_tiles,
                extra=extra,
            ),
            4000,
        )
    except Exception:
        pass
