import os
from typing import Any

from PyQt6 import QtCore

from i18n import tr

BOOKMARK_ROLE = int(QtCore.Qt.ItemDataRole.UserRole)
NODE_TYPE_ROLE = BOOKMARK_ROLE + 1
NODE_KEY_ROLE = BOOKMARK_ROLE + 2
NODE_PATH_ROLE = BOOKMARK_ROLE + 3
NODE_CATEGORY_ROLE = BOOKMARK_ROLE + 4
DEFAULT_CATEGORY = "미분류"


def normalize_path(path: str) -> str:
    return os.path.normpath(os.path.abspath(path))


def normalize_path_or_empty(path: str) -> str:
    text = str(path or "").strip()
    return normalize_path(text) if text else ""


def _path_signature(path: str) -> tuple[int, int]:
    normalized = normalize_path_or_empty(path)
    if not normalized:
        return (0, 0)
    try:
        st = os.stat(normalized)
        return (int(st.st_mtime_ns), int(st.st_size))
    except Exception:
        return (0, 0)


def path_signature_fields(path: str) -> dict[str, int]:
    mtime_ns, size = _path_signature(path)
    return {
        "video_mtime_ns": int(mtime_ns),
        "video_size": int(size),
    }


def bookmark_signature(entry: Any) -> tuple[int, int]:
    if not isinstance(entry, dict):
        return (0, 0)
    try:
        mtime_ns = int(entry.get("video_mtime_ns", 0) or 0)
    except Exception:
        mtime_ns = 0
    try:
        size = int(entry.get("video_size", 0) or 0)
    except Exception:
        size = 0
    return (mtime_ns, size)


def bookmark_matches_path(entry: Any, path: str) -> bool:
    if not isinstance(entry, dict):
        return False
    requested = normalize_path_or_empty(path)
    stored = normalize_path_or_empty(entry.get("path", ""))
    if requested and stored and requested == stored:
        return True
    requested_sig = _path_signature(requested)
    if requested_sig == (0, 0):
        return False
    stored_sig = bookmark_signature(entry)
    if stored_sig != (0, 0):
        return requested_sig == stored_sig
    if stored:
        return requested_sig == _path_signature(stored)
    return False


def resolve_bookmark_path(main, entry: Any) -> str:
    if not isinstance(entry, dict):
        return ""
    stored = normalize_path_or_empty(entry.get("path", ""))
    if stored and os.path.exists(stored):
        return stored
    for tile in list(getattr(getattr(main, "canvas", None), "tiles", []) or []):
        try:
            current = tile._current_media_path()
        except Exception:
            current = ""
        current_norm = normalize_path_or_empty(current)
        if current_norm and bookmark_matches_path(entry, current_norm):
            return current_norm
    return ""


def normalize_category(name: Any) -> str:
    if not isinstance(name, str):
        return DEFAULT_CATEGORY
    text = " ".join(name.split()).strip()
    return text or DEFAULT_CATEGORY


def display_category(main, category: str) -> str:
    normalized = normalize_category(category)
    return tr(main, DEFAULT_CATEGORY) if normalized == DEFAULT_CATEGORY else normalized


def format_ms(ms: int) -> str:
    total_seconds = max(0, int(ms) // 1000)
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"


def format_range_ms(start_ms: int, end_ms: Any) -> str:
    start_label = format_ms(int(start_ms))
    try:
        end_value = int(end_ms)
    except Exception:
        end_value = -1
    if end_value <= int(start_ms):
        return start_label
    return f"{start_label}~{format_ms(end_value)}"


def status(main, text: str, timeout_ms: int = 3000):
    try:
        main.statusBar().showMessage(text, timeout_ms)
    except Exception:
        pass
