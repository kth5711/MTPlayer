import os

from PyQt6 import QtCore, QtWidgets

from i18n import tr

from .open import _apply_infinite_roller_bookmark_targets
from .selection import selected_entries
from .shared import format_range_ms, normalize_path, resolve_bookmark_path, status
from .state import bookmark_end_ms


def jump_to_selected_bookmark(main):
    entries = selected_entries(main)
    if not entries:
        return
    entry = entries[0]
    path = resolve_bookmark_path(main, entry) or str(entry.get("path", ""))
    if not os.path.exists(path):
        _warn_missing_path(main, str(entry.get("path", "")) or path)
        return
    end_ms = bookmark_end_ms(entry)
    if bool(getattr(getattr(main, "canvas", None), "infinite_roller_active", lambda: False)()):
        target = _open_target_in_infinite_roller(main, path, int(entry.get("position_ms", 0)), end_ms)
        if target is None:
            return
        _queue_seek(target, path, int(entry.get("position_ms", 0)), end_ms)
        status(
            main,
            tr(
                main,
                "북마크 이동: {name} @ {time}",
                name=os.path.basename(path) or path,
                time=format_range_ms(int(entry.get("position_ms", 0)), end_ms),
            ),
        )
        return
    target = _find_target_tile(main, path)
    _load_or_resume_target(main, target, path)
    _queue_seek(target, path, int(entry.get("position_ms", 0)), end_ms)
    status(
        main,
        tr(
            main,
            "북마크 이동: {name} @ {time}",
            name=os.path.basename(path) or path,
            time=format_range_ms(int(entry.get("position_ms", 0)), end_ms),
        ),
    )


def _warn_missing_path(main, path: str):
    QtWidgets.QMessageBox.warning(main, tr(main, "북마크"), tr(main, "파일을 찾을 수 없습니다.\n\n{path}", path=path))


def _find_target_tile(main, target_path: str):
    normalized_target = normalize_path(target_path)
    for tile in list(getattr(main.canvas, "tiles", [])):
        if _tile_path(tile) == normalized_target:
            return tile
    for tile in list(getattr(main.canvas, "tiles", [])):
        try:
            if not getattr(tile, "playlist", None):
                return tile
        except Exception:
            continue
    main.canvas.add_tile()
    return main.canvas.tiles[-1]


def _tile_path(tile):
    try:
        current = tile._current_playlist_path() or tile._current_media_path()
    except Exception:
        return None
    return normalize_path(current) if current else None


def _load_or_resume_target(main, target, path: str):
    current_path = _tile_path(target)
    if current_path and current_path == normalize_path(path):
        try:
            target.play()
        except Exception:
            pass
        return
    target.clear_playlist()
    target.add_to_playlist(path, play_now=True)
    try:
        main.update_playlist()
    except Exception:
        pass


def _open_target_in_infinite_roller(main, path: str, position_ms: int, end_ms: int | None):
    normalized_target = normalize_path(path)
    for tile in list(getattr(main.canvas, "tiles", []) or []):
        if _tile_path(tile) == normalized_target:
            try:
                tile.play()
            except Exception:
                pass
            return tile
    main.canvas.set_infinite_roller_sources([path])
    try:
        main.canvas.relayout()
    except Exception:
        pass
    _apply_infinite_roller_bookmark_targets(main, [(path, [(path, int(position_ms), end_ms, False)])])
    try:
        main.update_playlist()
    except Exception:
        pass
    try:
        docked_tiles = list(main.canvas.docked_tiles())
    except Exception:
        docked_tiles = []
    target = docked_tiles[0] if docked_tiles else None
    if target is None:
        tiles = list(getattr(main.canvas, "tiles", []) or [])
        target = tiles[0] if tiles else None
    if target is None:
        return None
    QtCore.QTimer.singleShot(0, main.canvas.activate_roller_after_source_change)
    return target


def _queue_seek(tile, target_path: str, position_ms: int, end_ms: int | None, attempts: int = 8):
    normalized_target = normalize_path(target_path)

    def _attempt(remaining: int):
        if _tile_path(tile) == normalized_target or remaining <= 0:
            tile._playlist_bookmark_end_ms = int(end_ms) if end_ms is not None and int(end_ms) > int(position_ms) else None
            tile._playlist_bookmark_guard_active = tile._playlist_bookmark_end_ms is not None
            tile._playlist_bookmark_auto_advance = False
            tile.safe_seek_from_ui(position_ms)
            return
        QtCore.QTimer.singleShot(220, lambda: _attempt(remaining - 1))

    _attempt(max(0, int(attempts)))
