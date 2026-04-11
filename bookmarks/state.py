import os
import time
import uuid
from typing import Any, Dict, Optional

from .shared import (
    DEFAULT_CATEGORY,
    bookmark_signature,
    bookmark_matches_path,
    normalize_category,
    normalize_path,
    normalize_path_or_empty,
    path_signature_fields,
)


def normalized_bookmark(entry: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(entry, dict):
        return None
    path = entry.get("path")
    if not isinstance(path, str) or not path.strip():
        return None
    position_ms = _safe_int(entry.get("position_ms", 0))
    end_ms = bookmark_end_ms(entry, position_ms=position_ms)
    created_at = _safe_int(entry.get("created_at", 0)) or int(time.time())
    normalized = {
        "id": str(entry.get("id") or uuid.uuid4().hex),
        "path": normalize_path(path),
        "position_ms": max(0, position_ms),
        "created_at": created_at,
        "category": normalize_category(entry.get("category", DEFAULT_CATEGORY)),
    }
    try:
        normalized["video_mtime_ns"] = int(entry.get("video_mtime_ns", 0) or 0)
    except Exception:
        normalized["video_mtime_ns"] = 0
    try:
        normalized["video_size"] = int(entry.get("video_size", 0) or 0)
    except Exception:
        normalized["video_size"] = 0
    if normalized["video_mtime_ns"] <= 0 or normalized["video_size"] <= 0:
        normalized.update(path_signature_fields(path))
    if end_ms is not None:
        normalized["end_ms"] = int(end_ms)
    return normalized


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def bookmark_end_ms(entry: Any, *, position_ms: Optional[int] = None) -> Optional[int]:
    if not isinstance(entry, dict):
        return None
    start_ms = max(0, int(position_ms)) if position_ms is not None else max(0, _safe_int(entry.get("position_ms", 0)))
    end_ms = _safe_int(entry.get("end_ms", 0))
    return int(end_ms) if end_ms > start_ms else None


def bookmarks_for_file(main, path: str) -> list[dict[str, Any]]:
    return [entry for entry in getattr(main, "bookmarks", []) or [] if bookmark_matches_path(entry, path)]


def default_category_for_path(main, path: str) -> str:
    for entry in bookmarks_for_file(main, path):
        category = normalize_category(entry.get("category", DEFAULT_CATEGORY))
        if category:
            return category
    return DEFAULT_CATEGORY


def bookmark_category_names(main) -> list[str]:
    out: list[str] = [DEFAULT_CATEGORY]
    seen: set[str] = {DEFAULT_CATEGORY}
    for source in (getattr(main, "bookmark_categories", []) or [], getattr(main, "bookmarks", []) or []):
        for item in source:
            category = normalize_category(item if isinstance(item, str) else item.get("category", DEFAULT_CATEGORY))
            if category in seen:
                continue
            seen.add(category)
            out.append(category)
    return out


def category_sort_key(category: str) -> tuple[int, str]:
    normalized = normalize_category(category)
    return (0 if normalized == DEFAULT_CATEGORY else 1, normalized.lower())


def bookmark_categories_payload(main) -> list[str]:
    return list(bookmark_category_names(main))


def bookmark_payload(main) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int, int]] = set()
    for entry in getattr(main, "bookmarks", []) or []:
        normalized = normalized_bookmark(entry)
        if normalized is None:
            continue
        dedupe_key = (
            normalized["path"],
            int(normalized["position_ms"]),
            int(normalized.get("end_ms", -1) or -1),
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        out.append(dict(normalized))
    return out


def bookmark_marks_visible(main) -> bool:
    action = getattr(main, "act_toggle_bookmark_marks", None)
    if action is not None:
        try:
            return bool(action.isChecked())
        except Exception:
            pass
    return bool(getattr(main, "config", {}).get("bookmark_marks_visible", True))


def bookmark_positions_for_path(main, path: Optional[str]) -> list[int]:
    if not path:
        return []
    positions = {int(entry.get("position_ms", 0)) for entry in getattr(main, "bookmarks", []) or [] if bookmark_matches_path(entry, path)}
    return sorted(positions)


def refresh_bookmark_marks(main):
    for tile in list(getattr(getattr(main, "canvas", None), "tiles", []) or []):
        try:
            if hasattr(tile, "refresh_bookmark_marks"):
                tile.refresh_bookmark_marks(force=True)
        except Exception:
            pass


def relink_bookmarks_for_media_path(
    main,
    old_path: str,
    new_path: str,
    *,
    old_mtime_ns: int = 0,
    old_size: int = 0,
) -> int:
    old_norm = normalize_path_or_empty(old_path)
    new_norm = normalize_path_or_empty(new_path)
    if not old_norm or not new_norm:
        return 0
    old_signature = (int(old_mtime_ns or 0), int(old_size or 0))
    new_signature = path_signature_fields(new_norm)
    changed = 0
    for entry in getattr(main, "bookmarks", []) or []:
        if not isinstance(entry, dict):
            continue
        if not _bookmark_path_matches_relink_target(entry, old_norm, old_signature):
            continue
        entry["path"] = new_norm
        entry["video_mtime_ns"] = int(new_signature.get("video_mtime_ns", 0) or 0)
        entry["video_size"] = int(new_signature.get("video_size", 0) or 0)
        changed += 1
    if changed <= 0:
        return 0
    from .dock import refresh_bookmark_dock

    refresh_bookmark_dock(main, keep_selection=False)
    refresh_bookmark_marks(main)
    return changed


def _bookmark_path_matches_relink_target(
    entry: dict[str, Any],
    old_norm: str,
    old_signature: tuple[int, int],
) -> bool:
    stored = normalize_path_or_empty(entry.get("path", ""))
    if stored and os.path.normcase(stored) == os.path.normcase(old_norm):
        return True
    if old_signature == (0, 0):
        return False
    return bookmark_signature(entry) == old_signature


def load_bookmarks(main, payload: Any):
    main.bookmarks = _deduped_bookmarks(payload if isinstance(payload, list) else [])
    from .dock import refresh_bookmark_dock

    refresh_bookmark_dock(main, keep_selection=False)
    refresh_bookmark_marks(main)


def _deduped_bookmarks(entries) -> list[dict[str, Any]]:
    seen_keys: set[tuple[str, int, int]] = set()
    bookmarks: list[dict[str, Any]] = []
    for entry in entries:
        normalized = normalized_bookmark(entry)
        if normalized is None:
            continue
        dedupe_key = (
            normalized["path"],
            int(normalized["position_ms"]),
            int(normalized.get("end_ms", -1) or -1),
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        bookmarks.append(normalized)
    return bookmarks


def load_bookmark_categories(main, payload: Any):
    items = payload if isinstance(payload, list) else []
    categories: list[str] = []
    seen: set[str] = set()
    for item in items:
        category = normalize_category(item)
        if category in seen:
            continue
        seen.add(category)
        categories.append(category)
    main.bookmark_categories = categories
    from .dock import refresh_bookmark_dock

    refresh_bookmark_dock(main, keep_selection=False)


def set_bookmark_marks_visible(main, checked: bool):
    visible = bool(checked)
    action = getattr(main, "act_toggle_bookmark_marks", None)
    if action is not None and action.isChecked() != visible:
        action.blockSignals(True)
        action.setChecked(visible)
        action.blockSignals(False)
    main.config["bookmark_marks_visible"] = visible
    refresh_bookmark_marks(main)
