import os
import re
from typing import Any, Optional

from PyQt6 import QtCore

from video_tile_helpers.playlist_bookmarks import (
    playlist_entries_with_start_positions,
    restore_playlist_entries_with_start_positions,
)
from i18n import tr
from .tile_state import _current_playlist_index


def playlist_filter_text(main) -> str:
    edit = getattr(main, "playlist_filter_edit", None)
    return str(edit.text() or "").strip().lower() if edit is not None else ""


def playlist_sort_mode(main) -> str:
    combo = getattr(main, "playlist_sort_mode_combo", None)
    return str(combo.currentData() or "none") if combo is not None else "none"


def playlist_sort_descending(main) -> bool:
    button = getattr(main, "playlist_sort_order_button", None)
    return bool(button.isChecked()) if button is not None else False


def set_playlist_sort_controls(main, mode: str, descending: bool):
    mode_combo = getattr(main, "playlist_sort_mode_combo", None)
    order_button = getattr(main, "playlist_sort_order_button", None)
    if mode_combo is None or order_button is None:
        return
    normalized_mode = _normalize_playlist_sort_mode(mode)
    mode_index = mode_combo.findData(normalized_mode)
    if mode_index < 0:
        mode_index = mode_combo.findData("none")
    with QtCore.QSignalBlocker(mode_combo), QtCore.QSignalBlocker(order_button):
        mode_combo.setCurrentIndex(mode_index)
        order_button.setChecked(bool(descending))
    main._sync_playlist_sort_order_button_text()


def sync_playlist_sort_order_button_text(main):
    button = getattr(main, "playlist_sort_order_button", None)
    if button is None:
        return
    button.setText(tr(main, "내림차순") if button.isChecked() else tr(main, "오름차순"))
    button.setEnabled(main._playlist_sort_mode() != "none")


def on_playlist_sort_changed(main):
    main.config["playlist_sort_mode"] = main._playlist_sort_mode()
    main.config["playlist_sort_descending"] = main._playlist_sort_descending()
    main._sync_playlist_sort_order_button_text()
    main.request_playlist_refresh(force=True)


def on_playlist_sort_order_toggled(main, checked: bool):
    main.config["playlist_sort_descending"] = bool(checked)
    main._sync_playlist_sort_order_button_text()
    main.request_playlist_refresh(force=True)


def playlist_sort_name(main, path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0].strip()


def playlist_natural_key(main, text: str):
    parts = re.split(r"(\d+)", text.casefold())
    key = []
    for part in parts:
        if not part:
            continue
        key.append((0, int(part)) if part.isdigit() else (1, part))
    return tuple(key)


def playlist_first_number_key(main, text: str):
    match = re.search(r"\d+", text)
    natural = main._playlist_natural_key(text)
    if not match:
        return (1, natural)
    try:
        return (0, int(match.group(0)), natural)
    except Exception:
        return (0, match.group(0), natural)


def playlist_first_visible_char(main, text: str) -> str:
    stripped = text.lstrip()
    return stripped[:1] if stripped else ""


def playlist_is_ascii_alpha_lead(main, text: str) -> bool:
    ch = main._playlist_first_visible_char(text)
    return bool(ch) and ch.isascii() and ch.isalpha()


def playlist_is_hangul_lead(main, text: str) -> bool:
    ch = main._playlist_first_visible_char(text)
    return bool(ch) and 0xAC00 <= ord(ch) <= 0xD7A3


def playlist_sort_key_for_path(main, path: str, mode: str):
    name = main._playlist_sort_name(path)
    natural = main._playlist_natural_key(name)
    normalized_mode = _normalize_playlist_sort_mode(mode)
    if normalized_mode == "time":
        duration_ms, _duration_text = main._playlist_duration_info(path)
        return (int(duration_ms or 0), natural)
    if normalized_mode == "number":
        return main._playlist_first_number_key(name)
    if normalized_mode == "alpha_hangul":
        return (_playlist_alpha_hangul_bucket(main, name), natural)
    return natural


def sorted_playlist_for_mode(main, plist: list[str], mode: str, descending: bool) -> list[str]:
    return sorted(plist, key=lambda p, m=mode: main._playlist_sort_key_for_path(p, m), reverse=descending)


def apply_playlist_sort(main):
    mode = main._playlist_sort_mode()
    if mode == "none":
        return
    descending = main._playlist_sort_descending()
    for tile in getattr(main.canvas, "tiles", []):
        entries = playlist_entries_with_start_positions(tile)
        if len(entries) < 2:
            continue
        current_entry_id = _current_playlist_entry_id(tile, entries)
        entries.sort(key=lambda entry, m=mode: main._playlist_sort_key_for_path(str(entry.get("path", "")), m), reverse=descending)
        restore_playlist_entries_with_start_positions(tile, entries)
        if current_entry_id is not None:
            _restore_current_playlist_entry_id(tile, entries, current_entry_id)


def _current_playlist_entry_id(tile, entries: list[dict[str, Any]]) -> Optional[int]:
    current_index = _current_playlist_index(tile)
    if not (0 <= current_index < len(entries)):
        return None
    return int(entries[current_index].get("entry_id", current_index))


def _restore_current_playlist_entry_id(tile, entries: list[dict[str, Any]], current_entry_id: int):
    for index, entry in enumerate(entries):
        if int(entry.get("entry_id", -1)) == int(current_entry_id):
            tile.current_index = index
            break


def playlist_path_matches_filter(main, path: str, query: str) -> bool:
    if not query:
        return True
    haystacks = [os.path.basename(path).lower(), os.path.abspath(path).lower()]
    return any(query in text for text in haystacks)


def normalize_playlist_path(main, path: Optional[str]) -> str:
    if not path:
        return ""
    try:
        return os.path.normcase(os.path.abspath(path))
    except Exception:
        return str(path)


def _normalize_playlist_sort_mode(mode: str) -> str:
    normalized_mode = str(mode or "none")
    return "alpha_hangul" if normalized_mode in {"alpha", "hangul"} else normalized_mode


def _playlist_alpha_hangul_bucket(main, text: str) -> int:
    if main._playlist_is_ascii_alpha_lead(text):
        return 0
    if main._playlist_is_hangul_lead(text):
        return 1
    return 2
