# canvas.py

import logging
import math
import os
from typing import Any, Dict, List, Optional
from PyQt6 import QtCore, QtGui, QtWidgets
from canvas_support import DetachedTileWindow
from canvas_support.overlay_groups import (
    clear_overlay_stack as clear_overlay_stack_impl,
    clear_overlay_stack_for_group as clear_overlay_stack_for_group_impl,
    overlay_audio_mode_for_tile as overlay_audio_mode_for_tile_impl,
    overlay_default_opacity as overlay_default_opacity_impl,
    overlay_group_id_for_tile as overlay_group_id_for_tile_impl,
    overlay_group_tiles as overlay_group_tiles_impl,
    overlay_stack_tiles as overlay_stack_tiles_impl,
    reapply_overlay_group_opacity_rule as reapply_overlay_group_opacity_rule_impl,
    set_overlay_audio_mode_for_tile as set_overlay_audio_mode_for_tile_impl,
    set_overlay_opacity_for_tile as set_overlay_opacity_for_tile_impl,
)
from canvas_support.overlay_sync import (
    on_overlay_geometry_changed as on_overlay_geometry_changed_impl,
    on_overlay_restack_requested as on_overlay_restack_requested_impl,
    restack_overlay_group as restack_overlay_group_impl,
    sync_overlay_group_geometry as sync_overlay_group_geometry_impl,
    sync_overlay_group_window_mode as sync_overlay_group_window_mode_impl,
)
from app_shell.session import rect_from_data, rect_to_data
from video_tile_helpers.playlist_bookmarks import remove_playlist_entry_start_positions
from video_tile import VideoTile

logger = logging.getLogger(__name__)

class Canvas(QtWidgets.QWidget):
    LAYOUT_AUTO = "auto"
    LAYOUT_WIDE = "wide"
    LAYOUT_TALL = "tall"
    LAYOUT_ROW = "row"
    LAYOUT_COLUMN = "column"
    LAYOUT_ROLLER_ROW = "roller_row"
    LAYOUT_ROLLER_COLUMN = "roller_column"
    LAYOUT_INFINITE_ROLLER_ROW = "infinite_roller_row"
    LAYOUT_INFINITE_ROLLER_COLUMN = "infinite_roller_column"
    ROLLER_AXIS_HORIZONTAL = "horizontal"
    ROLLER_AXIS_VERTICAL = "vertical"
    ROLLER_DIRECTION_FORWARD = "forward"
    ROLLER_DIRECTION_REVERSE = "reverse"
    DEFAULT_ROLLER_VISIBLE_COUNT = 3
    DEFAULT_ROLLER_SPEED_PX_PER_SEC = 90
    DEFAULT_OVERLAY_GLOBAL_APPLY_PERCENT = 10
    ROLLER_VISIBLE_COUNT_OPTIONS = (1, 2, 3, 4, 5, 6)
    ROLLER_SPEED_MIN = 10
    ROLLER_SPEED_MAX = 300
    ROLLER_PEEK_FRACTION = 0.35
    LAYOUT_LABELS = {
        LAYOUT_AUTO: "자동",
        LAYOUT_WIDE: "가로 우선",
        LAYOUT_TALL: "세로 우선",
        LAYOUT_ROW: "한 줄",
        LAYOUT_COLUMN: "한 열",
        LAYOUT_ROLLER_ROW: "롤러",
        LAYOUT_ROLLER_COLUMN: "롤러",
        LAYOUT_INFINITE_ROLLER_ROW: "영상변경롤러",
        LAYOUT_INFINITE_ROLLER_COLUMN: "영상변경롤러",
    }
    ROLLER_AXIS_LABELS = {
        ROLLER_AXIS_HORIZONTAL: "가로",
        ROLLER_AXIS_VERTICAL: "세로",
    }

    # ================== 🟢 핵심 변경 2: vlc_instance를 인자로 받도록 수정 ==================
    def __init__(self, parent=None, vlc_instance=None):
        super().__init__(parent)
        self.vlc_instance = vlc_instance  # 전달받은 엔진 저장
        self.tiles: List[VideoTile] = []
        self.spotlight_index: Optional[int] = None
        self._spotlight_restore_playing_tiles: List[VideoTile] = []
        self._spotlight_restore_snapshot_seeded = False
        self._roller_restore_playing_tiles: List[VideoTile] = []
        self._roller_restore_snapshot_seeded = False
        self.detached_windows: dict[VideoTile, DetachedTileWindow] = {}
        self._opacity_dock_tiles: set[VideoTile] = set()
        self._closing_for_app_exit = False
        self._layout_mode = self.LAYOUT_AUTO
        self._roller_visible_count = self.DEFAULT_ROLLER_VISIBLE_COUNT
        self._overlay_global_apply_percent = self.DEFAULT_OVERLAY_GLOBAL_APPLY_PERCENT
        self._roller_paused = False
        self._roller_direction = self.ROLLER_DIRECTION_FORWARD
        self._roller_playback_active = False
        self._roller_last_visible_tiles: set[VideoTile] = set()
        self._roller_offset_px = 0.0
        self._roller_px_per_sec = float(self.DEFAULT_ROLLER_SPEED_PX_PER_SEC)
        self._roller_last_tick_ms = 0
        self._virtual_roller_sources: List[Dict[str, str]] = []
        self._virtual_roller_scroll_index = 0
        self._virtual_roller_saved_states: Dict[str, Dict[str, Any]] = {}
        self._virtual_roller_pool_updating = False
        self._roller_timer = QtCore.QTimer(self)
        self._roller_timer.setInterval(30)
        self._roller_timer.timeout.connect(self._advance_roller)
        # =================================================================================

    @classmethod
    def normalize_layout_mode(cls, mode: Optional[str]) -> str:
        if mode in {cls.LAYOUT_WIDE, cls.LAYOUT_TALL}:
            return cls.LAYOUT_AUTO
        if isinstance(mode, str) and mode in cls.LAYOUT_LABELS:
            return mode
        return cls.LAYOUT_AUTO

    @classmethod
    def normalize_roller_visible_count(cls, count: Any) -> int:
        try:
            normalized = int(count)
        except (TypeError, ValueError):
            normalized = cls.DEFAULT_ROLLER_VISIBLE_COUNT
        if normalized not in cls.ROLLER_VISIBLE_COUNT_OPTIONS:
            normalized = min(
                cls.ROLLER_VISIBLE_COUNT_OPTIONS,
                key=lambda option: abs(int(option) - int(normalized)),
            )
        return int(normalized)

    @classmethod
    def normalize_overlay_global_apply_percent(cls, value: Any) -> int:
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            normalized = cls.DEFAULT_OVERLAY_GLOBAL_APPLY_PERCENT
        return max(1, min(100, normalized))

    @classmethod
    def normalize_roller_speed(cls, value: Any) -> int:
        try:
            normalized = int(round(float(value)))
        except (TypeError, ValueError):
            normalized = cls.DEFAULT_ROLLER_SPEED_PX_PER_SEC
        return max(cls.ROLLER_SPEED_MIN, min(cls.ROLLER_SPEED_MAX, normalized))

    def layout_mode(self) -> str:
        return self._layout_mode

    def roller_visible_count(self) -> int:
        return int(self._roller_visible_count)

    def roller_speed_px_per_sec(self) -> int:
        return int(self.normalize_roller_speed(self._roller_px_per_sec))

    def overlay_global_apply_percent(self) -> int:
        return int(self._overlay_global_apply_percent)

    def roller_paused(self) -> bool:
        return bool(self._roller_paused)

    @classmethod
    def normalize_roller_direction(cls, value: Any) -> str:
        text = str(value or "").strip().lower()
        if text == cls.ROLLER_DIRECTION_REVERSE:
            return cls.ROLLER_DIRECTION_REVERSE
        return cls.ROLLER_DIRECTION_FORWARD

    def roller_direction(self) -> str:
        return self.normalize_roller_direction(self._roller_direction)

    def roller_direction_sign(self) -> int:
        return -1 if self.roller_direction() == self.ROLLER_DIRECTION_REVERSE else 1

    def set_layout_mode(self, mode: Optional[str]):
        previous_roller_mode = self._roller_mode()
        previous_virtual_mode = self._virtual_roller_mode(previous_roller_mode)
        normalized = self.normalize_layout_mode(mode)
        if normalized == self._layout_mode:
            return
        next_roller_mode = normalized if normalized in self._roller_layout_modes() else None
        next_virtual_mode = self._virtual_roller_mode(normalized)
        leaving_virtual_mode = previous_virtual_mode is not None and next_virtual_mode is None
        resume_tiles: List[VideoTile] = []
        if previous_roller_mode is None and next_roller_mode is not None:
            if not self._roller_restore_snapshot_seeded:
                self._roller_restore_playing_tiles = [t for t in self.tiles if self._tile_is_playing(t)]
            self._roller_restore_snapshot_seeded = True
            self._roller_playback_active = bool(self._roller_restore_playing_tiles)
            self._roller_last_visible_tiles = set()
        elif previous_roller_mode is not None and next_roller_mode is None:
            resume_tiles = [t for t in self._roller_restore_playing_tiles if t in self.tiles]
            self._roller_restore_playing_tiles = []
            self._roller_restore_snapshot_seeded = False
            self._roller_playback_active = False
            self._roller_last_visible_tiles = set()
        if previous_virtual_mode is None and next_virtual_mode is not None:
            if self.detached_windows and not self._keep_detached_tiles_for_focus_modes():
                self.redock_all_detached()
            self._virtual_roller_sources = self._collect_virtual_roller_sources()
            self._virtual_roller_scroll_index = 0
        self._layout_mode = normalized
        self._roller_offset_px = 0.0
        self._roller_last_tick_ms = 0
        if leaving_virtual_mode:
            self._expand_virtual_roller_sources_to_tiles()
            self._virtual_roller_sources = []
            self._virtual_roller_scroll_index = 0
        if next_virtual_mode is not None:
            self._configure_virtual_roller_tiles()
        elif next_roller_mode is not None:
            self._ensure_roller_entry_tiles(next_roller_mode)
        self.relayout()
        if resume_tiles:
            QtCore.QTimer.singleShot(0, lambda tiles=resume_tiles: self._restore_roller_tiles(tiles))

    def set_roller_visible_count(self, count: Any):
        normalized = self.normalize_roller_visible_count(count)
        if normalized == self._roller_visible_count:
            return
        self._roller_visible_count = normalized
        self._roller_offset_px = 0.0
        self._roller_last_tick_ms = 0
        if self._virtual_roller_mode() is not None:
            self._configure_virtual_roller_tiles()
        elif self._roller_mode() is not None:
            self._ensure_roller_entry_tiles(self._roller_mode())
        self.relayout()

    def set_roller_speed(self, value: Any):
        normalized = self.normalize_roller_speed(value)
        if normalized == self.roller_speed_px_per_sec():
            return
        self._roller_px_per_sec = float(normalized)
        if self._roller_timer.isActive():
            self._roller_last_tick_ms = QtCore.QDateTime.currentMSecsSinceEpoch()
        else:
            self._roller_last_tick_ms = 0

    def set_overlay_global_apply_percent(self, value: Any, *, apply_existing: bool = False):
        normalized = self.normalize_overlay_global_apply_percent(value)
        changed = normalized != self._overlay_global_apply_percent
        self._overlay_global_apply_percent = normalized
        if apply_existing:
            group_ids = {
                window.overlay_group_id()
                for window in self.detached_windows.values()
                if window is not None and window.overlay_active()
            }
            for group_id in sorted(group_ids):
                self._reapply_overlay_group_opacity_rule(group_id)
        elif changed:
            self.update()

    def set_roller_paused(self, paused: Any):
        normalized = bool(paused)
        if normalized == self._roller_paused:
            return
        self._roller_paused = normalized
        self._roller_last_tick_ms = 0
        self.relayout()

    def set_roller_direction(self, direction: Any):
        normalized = self.normalize_roller_direction(direction)
        if normalized == self.roller_direction():
            return
        self._roller_direction = normalized
        self._roller_last_tick_ms = 0
        self.relayout()

    def _roller_mode(self) -> Optional[str]:
        mode = self.normalize_layout_mode(self._layout_mode)
        if mode in self._roller_layout_modes():
            return mode
        return None

    @classmethod
    def _roller_layout_modes(cls) -> set[str]:
        return {
            cls.LAYOUT_ROLLER_ROW,
            cls.LAYOUT_ROLLER_COLUMN,
            cls.LAYOUT_INFINITE_ROLLER_ROW,
            cls.LAYOUT_INFINITE_ROLLER_COLUMN,
        }

    @classmethod
    def _virtual_roller_layout_modes(cls) -> set[str]:
        return {
            cls.LAYOUT_INFINITE_ROLLER_ROW,
            cls.LAYOUT_INFINITE_ROLLER_COLUMN,
        }

    @classmethod
    def _roller_axis_groups(cls) -> Dict[str, tuple[str, str]]:
        return {
            cls.ROLLER_AXIS_HORIZONTAL: (cls.LAYOUT_ROLLER_ROW, cls.LAYOUT_INFINITE_ROLLER_ROW),
            cls.ROLLER_AXIS_VERTICAL: (cls.LAYOUT_ROLLER_COLUMN, cls.LAYOUT_INFINITE_ROLLER_COLUMN),
        }

    def _virtual_roller_mode(self, mode: Optional[str] = None) -> Optional[str]:
        normalized = self.normalize_layout_mode(self._layout_mode if mode is None else mode)
        if normalized in self._virtual_roller_layout_modes():
            return normalized
        return None

    @classmethod
    def _roller_axis_mode(cls, mode: str) -> str:
        if mode == cls.LAYOUT_INFINITE_ROLLER_COLUMN:
            return cls.LAYOUT_ROLLER_COLUMN
        if mode == cls.LAYOUT_INFINITE_ROLLER_ROW:
            return cls.LAYOUT_ROLLER_ROW
        return mode

    def _roller_entry_tile_count(self) -> int:
        return max(1, int(self.roller_visible_count()))

    def _ensure_roller_entry_tiles(self, mode: Optional[str] = None):
        normalized = self.normalize_layout_mode(self._layout_mode if mode is None else mode)
        if normalized not in self._roller_layout_modes():
            return
        if normalized in self._virtual_roller_layout_modes() and self._virtual_roller_sources:
            return
        desired = self._roller_entry_tile_count()
        while len(self.docked_tiles()) < desired:
            self.add_tile()

    def infinite_roller_sources(self) -> List[Dict[str, str]]:
        return [dict(entry) for entry in self._virtual_roller_sources]

    def infinite_roller_saved_states(self) -> List[Dict[str, Any]]:
        payload: List[Dict[str, Any]] = []
        for key, state in (self._virtual_roller_saved_states or {}).items():
            if not key or not isinstance(state, dict):
                continue
            payload.append({"path": key, "state": dict(state)})
        return payload

    def infinite_roller_active(self) -> bool:
        return self._virtual_roller_mode() is not None

    def set_infinite_roller_sources(self, paths: List[str]):
        self._virtual_roller_sources = self._build_virtual_roller_sources_from_paths(paths)
        self._prune_virtual_roller_saved_states()
        self._virtual_roller_scroll_index = 0
        self._roller_offset_px = 0.0
        self._roller_last_tick_ms = 0
        if self._virtual_roller_mode() is not None:
            self._configure_virtual_roller_tiles()
            self.relayout()

    def set_infinite_roller_bookmark_targets(self, targets: List[tuple]):
        self._virtual_roller_sources = self._build_virtual_roller_sources_from_bookmark_targets(targets)
        self._prune_virtual_roller_saved_states()
        self._virtual_roller_scroll_index = 0
        self._roller_offset_px = 0.0
        self._roller_last_tick_ms = 0
        if self._virtual_roller_mode() is not None:
            self._configure_virtual_roller_tiles()
            self.relayout()

    def restore_infinite_roller_sources(self, entries: Any, scroll_index: Any = 0):
        if not isinstance(entries, list):
            self._virtual_roller_sources = []
            self._virtual_roller_scroll_index = 0
            return
        normalized_entries: List[Dict[str, str]] = []
        seen: set[str] = set()
        for entry in entries:
            if isinstance(entry, dict):
                path = str(entry.get("path", "") or "").strip()
                subtitle = str(entry.get("subtitle", "") or "").strip()
                source_id = str(entry.get("source_id", "") or "").strip()
                raw_bookmark_targets = entry.get("bookmark_targets")
            else:
                path = str(entry or "").strip()
                subtitle = ""
                source_id = ""
                raw_bookmark_targets = None
            if not path:
                continue
            key = self._virtual_roller_source_key(path)
            dedupe_key = f"{key}\0{source_id}" if source_id else key
            if not key or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            payload = {"path": path}
            if source_id:
                payload["source_id"] = source_id
            bookmark_targets = self._normalize_virtual_source_bookmark_targets(raw_bookmark_targets)
            if bookmark_targets:
                payload["bookmark_targets"] = self._serialize_virtual_bookmark_targets(bookmark_targets)
            if subtitle:
                payload["subtitle"] = subtitle
            normalized_entries.append(payload)
        self._virtual_roller_sources = normalized_entries
        self._prune_virtual_roller_saved_states()
        source_count = len(normalized_entries)
        if source_count <= 0:
            self._virtual_roller_scroll_index = 0
            return
        try:
            normalized_scroll = int(scroll_index)
        except (TypeError, ValueError):
            normalized_scroll = 0
        self._virtual_roller_scroll_index = normalized_scroll % source_count
        self._roller_offset_px = 0.0
        self._roller_last_tick_ms = 0
        if self._virtual_roller_mode() is not None:
            self._configure_virtual_roller_tiles()
            self.relayout()

    def restore_infinite_roller_saved_states(self, entries: Any):
        restored: Dict[str, Dict[str, Any]] = {}
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                key = self._virtual_roller_source_key(entry.get("path", ""))
                state = entry.get("state")
                if not key or not isinstance(state, dict):
                    continue
                restored[key] = dict(state)
        self._virtual_roller_saved_states = restored
        self._prune_virtual_roller_saved_states()

    def _virtual_roller_source_key(self, path: str) -> str:
        text = str(path or "").strip()
        if not text:
            return ""
        if os.path.exists(text):
            try:
                return os.path.normcase(os.path.abspath(text))
            except Exception:
                return text
        return text

    def _build_virtual_roller_sources_from_paths(self, paths: List[str]) -> List[Dict[str, str]]:
        items: List[Dict[str, str]] = []
        seen: set[str] = set()
        for raw_path in list(paths or []):
            path = str(raw_path or "").strip()
            if not path:
                continue
            key = self._virtual_roller_source_key(path)
            if not key or key in seen:
                continue
            seen.add(key)
            items.append({"path": path})
        return items

    def _build_virtual_roller_sources_from_bookmark_targets(self, targets: List[tuple]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for index, target in enumerate(list(targets or [])):
            try:
                path = str(target[0] or "").strip()
                position_ms = max(0, int(target[1]))
                end_ms = int(target[2]) if len(target) >= 3 and target[2] is not None else None
                loop_enabled = bool(target[3]) if len(target) >= 4 else False
            except Exception:
                continue
            if not path:
                continue
            if end_ms is not None and end_ms <= position_ms:
                end_ms = None
                loop_enabled = False
            items.append(
                {
                    "path": path,
                    "source_id": f"bookmark:{index}:{position_ms}:{end_ms if end_ms is not None else -1}",
                    "bookmark_targets": self._serialize_virtual_bookmark_targets(
                        [(position_ms, end_ms, bool(loop_enabled))]
                    ),
                }
            )
        return items

    def _serialize_virtual_bookmark_targets(self, targets) -> list[list[Any]]:
        serialized: list[list[Any]] = []
        for position_ms, end_ms, loop_enabled in self._normalize_virtual_source_bookmark_targets(targets):
            serialized.append([int(position_ms), int(end_ms) if end_ms is not None else None, bool(loop_enabled)])
        return serialized

    def _normalize_virtual_source_bookmark_targets(self, raw_targets) -> list[tuple[int, Optional[int], bool]]:
        normalized: list[tuple[int, Optional[int], bool]] = []
        if not isinstance(raw_targets, list):
            return normalized
        for raw in raw_targets:
            try:
                if isinstance(raw, dict):
                    position_ms = int(raw.get("position_ms", raw.get("start_ms", 0)) or 0)
                    raw_end = raw.get("end_ms")
                    loop_enabled = bool(raw.get("loop_enabled", raw.get("loop", False)))
                else:
                    position_ms = int(raw[0])
                    raw_end = raw[1] if len(raw) >= 2 else None
                    loop_enabled = bool(raw[2]) if len(raw) >= 3 else False
                end_ms = int(raw_end) if raw_end is not None else None
            except Exception:
                continue
            position_ms = max(0, int(position_ms))
            if end_ms is not None and end_ms <= position_ms:
                end_ms = None
                loop_enabled = False
            normalized.append((position_ms, end_ms, loop_enabled))
        return normalized

    def _collect_virtual_roller_sources(self) -> List[Dict[str, str]]:
        tile_sources: List[List[Dict[str, str]]] = []
        target_tiles = [tile for tile in self.docked_tiles() if tile in self.tiles]
        if not target_tiles:
            target_tiles = list(self.tiles)
        for tile in target_tiles:
            entries: List[Dict[str, str]] = []
            playlist = [str(path or "").strip() for path in list(getattr(tile, "playlist", []) or [])]
            playlist = [path for path in playlist if path]
            if playlist:
                for path in playlist:
                    entry = {"path": path}
                    subtitle = str(tile.get_external_subtitle_for_path(path) or "").strip()
                    if subtitle:
                        entry["subtitle"] = subtitle
                    entries.append(entry)
            else:
                current_path = ""
                try:
                    current_path = str(tile._current_playlist_path() or tile._current_media_path() or "").strip()
                except Exception:
                    logger.debug("virtual roller current-path probe failed", exc_info=True)
                if current_path:
                    entry = {"path": current_path}
                    subtitle = str(tile.get_external_subtitle_for_path(current_path) or "").strip()
                    if subtitle:
                        entry["subtitle"] = subtitle
                    entries.append(entry)
            if entries:
                tile_sources.append(entries)
        max_len = max((len(entries) for entries in tile_sources), default=0)
        collected: List[Dict[str, str]] = []
        seen: set[str] = set()
        for offset in range(max_len):
            for entries in tile_sources:
                if offset >= len(entries):
                    continue
                entry = dict(entries[offset])
                key = self._virtual_roller_source_key(entry.get("path", ""))
                if not key or key in seen:
                    continue
                seen.add(key)
                collected.append(entry)
        return collected

    def _prune_virtual_roller_saved_states(self):
        valid_keys = {
            self._virtual_roller_source_key(entry.get("path", ""))
            for entry in self._virtual_roller_sources
        }
        valid_keys.discard("")
        if not valid_keys:
            self._virtual_roller_saved_states = {}
            return
        self._virtual_roller_saved_states = {
            key: dict(state)
            for key, state in (self._virtual_roller_saved_states or {}).items()
            if key in valid_keys and isinstance(state, dict)
        }

    def _capture_virtual_roller_active_states(self):
        if self._virtual_roller_mode() is None:
            return
        for tile in self.docked_tiles():
            self._save_virtual_roller_state_for_tile(tile)

    def _save_virtual_roller_state_for_tile(self, tile: VideoTile):
        try:
            current_path = str(tile._current_playlist_path() or tile._current_media_path() or "").strip()
        except Exception:
            logger.debug("virtual roller current-path probe failed during state capture", exc_info=True)
            current_path = ""
        key = self._virtual_roller_source_key(current_path)
        if not key:
            return
        try:
            self._virtual_roller_saved_states[key] = dict(tile.to_state())
        except Exception:
            logger.debug("virtual roller tile state capture failed", exc_info=True)

    def _saved_virtual_roller_state(self, path: str) -> Optional[Dict[str, Any]]:
        key = self._virtual_roller_source_key(path)
        if not key:
            return None
        state = (self._virtual_roller_saved_states or {}).get(key)
        if not isinstance(state, dict):
            return None
        return dict(state)

    def _detached_virtual_roller_source_keys(self) -> set[str]:
        keys: set[str] = set()
        for tile in list(self.detached_windows.keys()):
            try:
                current_path = str(tile._current_playlist_path() or tile._current_media_path() or "").strip()
            except Exception:
                logger.debug("detached virtual roller current-path probe failed", exc_info=True)
                current_path = ""
            key = self._virtual_roller_source_key(current_path)
            if key:
                keys.add(key)
        return keys

    def _virtual_roller_assignable_sources(self) -> List[Dict[str, str]]:
        source_count = len(self._virtual_roller_sources)
        if source_count <= 0:
            return []
        reserved_keys = self._detached_virtual_roller_source_keys()
        start_index = int(self._virtual_roller_scroll_index) % source_count
        ordered: List[Dict[str, str]] = []
        for offset in range(source_count):
            entry = self._virtual_roller_sources[(start_index + offset) % source_count]
            key = self._virtual_roller_source_key(entry.get("path", ""))
            if reserved_keys and key in reserved_keys:
                continue
            ordered.append(entry)
        if ordered:
            return ordered
        return list(self._virtual_roller_sources)

    def _virtual_roller_pool_size(self, source_count: int) -> int:
        source_count = max(0, int(source_count))
        if source_count <= 0:
            return self._roller_entry_tile_count()
        if source_count == 1:
            return 1
        return min(source_count, max(2, self.roller_visible_count() + 1))

    def _virtual_roller_desired_docked_pool_size(self, source_count: Optional[int] = None) -> int:
        if source_count is None:
            source_count = len(self._virtual_roller_sources)
        base_pool = self._virtual_roller_pool_size(source_count)
        if self._virtual_roller_mode() is not None:
            return base_pool
        detached_count = len(self.detached_windows)
        if detached_count <= 0:
            return base_pool
        return max(0, int(base_pool) - int(detached_count))

    def _configure_virtual_roller_tiles(self):
        if self._virtual_roller_mode() is None:
            return
        desired = self._virtual_roller_desired_docked_pool_size(len(self._virtual_roller_sources))
        self._virtual_roller_pool_updating = True
        try:
            if self.detached_windows and not self._keep_detached_tiles_for_focus_modes():
                self.redock_all_detached()
            while len(self.docked_tiles()) < desired:
                self.add_tile()
            docked_tiles = self.docked_tiles()
            while len(docked_tiles) > desired:
                tile = docked_tiles[-1]
                try:
                    tile.clear_playlist()
                except Exception:
                    logger.debug("virtual roller tile clear skipped while shrinking pool", exc_info=True)
                self.remove_tile(tile)
                docked_tiles = self.docked_tiles()
            self._assign_virtual_roller_sources(docked_tiles, 0)
        finally:
            self._virtual_roller_pool_updating = False

    def _expand_virtual_roller_sources_to_tiles(self):
        self._capture_virtual_roller_active_states()
        sources = self.infinite_roller_sources()
        if not sources:
            return
        self._virtual_roller_pool_updating = True
        try:
            if self.detached_windows and not self._keep_detached_tiles_for_focus_modes():
                self.redock_all_detached()
            desired = len(sources)
            while len(self.docked_tiles()) < desired:
                self.add_tile()
            docked_tiles = self.docked_tiles()
            while len(docked_tiles) > desired:
                tile = docked_tiles[-1]
                try:
                    tile.clear_playlist()
                except Exception:
                    logger.debug("virtual roller tile clear skipped while expanding", exc_info=True)
                self.remove_tile(tile)
                docked_tiles = self.docked_tiles()
            for idx, tile in enumerate(docked_tiles):
                if idx >= len(sources):
                    break
                self._assign_virtual_source_to_tile(tile, sources[idx])
        finally:
            self._virtual_roller_pool_updating = False

    def _assign_virtual_source_to_tile(self, tile: VideoTile, source: Dict[str, str]):
        path = str(source.get("path", "") or "").strip()
        if not path:
            try:
                tile.clear_playlist()
            except Exception:
                logger.debug("virtual roller empty-source clear failed", exc_info=True)
            return
        current_path = ""
        try:
            current_path = str(tile._current_playlist_path() or tile._current_media_path() or "").strip()
        except Exception:
            logger.debug("virtual roller current-path probe failed", exc_info=True)
        if current_path == path and list(getattr(tile, "playlist", []) or []) == [path]:
            self._apply_virtual_source_bookmark_targets(tile, 0, source)
            subtitle = str(source.get("subtitle", "") or "").strip()
            if subtitle:
                tile.set_external_subtitle_for_path(path, subtitle, overwrite=True)
            return
        if current_path:
            self._save_virtual_roller_state_for_tile(tile)
        restored = False
        saved_state = None if "bookmark_targets" in source else self._saved_virtual_roller_state(path)
        if saved_state:
            try:
                state = dict(saved_state)
                state["playlist"] = [path]
                state["current_index"] = 0
                entries = state.get("playlist_entries")
                if isinstance(entries, list) and entries:
                    entry = dict(entries[0]) if isinstance(entries[0], dict) else {}
                    entry["path"] = path
                    entry["entry_id"] = 0
                    state["playlist_entries"] = [entry]
                tile.from_state(state)
                restored = True
            except Exception:
                logger.debug("virtual roller saved-state restore failed", exc_info=True)
        if not restored:
            tile.clear_playlist()
            tile.add_to_playlist(path, play_now=False)
        self._apply_virtual_source_bookmark_targets(tile, 0, source)
        subtitle = str(source.get("subtitle", "") or "").strip()
        if subtitle:
            tile.set_external_subtitle_for_path(path, subtitle, overwrite=True)

    def _virtual_roller_lane_sources(
        self,
        ordered_sources: List[Dict[str, str]],
        first_index: int,
        lane_stride: int,
    ) -> List[Dict[str, str]]:
        if not ordered_sources:
            return []
        try:
            normalized_first = max(0, int(first_index))
        except (TypeError, ValueError):
            normalized_first = 0
        try:
            normalized_stride = max(1, int(lane_stride))
        except (TypeError, ValueError):
            normalized_stride = 1
        return [dict(ordered_sources[idx]) for idx in range(normalized_first, len(ordered_sources), normalized_stride)]

    def _assign_virtual_lane_to_tile(self, tile: VideoTile, lane_sources: List[Dict[str, str]]):
        if not lane_sources:
            try:
                tile.clear_playlist()
            except Exception:
                logger.debug("virtual roller empty-lane clear failed", exc_info=True)
            return
        lane_paths = [str(entry.get("path", "") or "").strip() for entry in lane_sources]
        lane_paths = [path for path in lane_paths if path]
        if not lane_paths:
            try:
                tile.clear_playlist()
            except Exception:
                logger.debug("virtual roller empty-lane-path clear failed", exc_info=True)
            return
        first_path = lane_paths[0]
        current_path = ""
        try:
            current_path = str(tile._current_playlist_path() or tile._current_media_path() or "").strip()
        except Exception:
            logger.debug("virtual roller current-path probe failed for lane assign", exc_info=True)
        existing_playlist = [str(path or "").strip() for path in list(getattr(tile, "playlist", []) or [])]
        if current_path == first_path and existing_playlist == lane_paths:
            self._apply_virtual_lane_bookmark_targets(tile, lane_sources)
            for source in lane_sources:
                subtitle = str(source.get("subtitle", "") or "").strip()
                path = str(source.get("path", "") or "").strip()
                if subtitle and path:
                    tile.set_external_subtitle_for_path(path, subtitle, overwrite=True)
            return
        if current_path:
            self._save_virtual_roller_state_for_tile(tile)
        restored = False
        saved_state = None if any("bookmark_targets" in source for source in lane_sources) else self._saved_virtual_roller_state(first_path)
        if saved_state:
            try:
                state = dict(saved_state)
                # In infinite-roller docked lanes, playback intent is owned by
                # the roller visibility sync path, not by saved-state restore.
                state["playing"] = False
                state["playlist"] = list(lane_paths)
                state["current_index"] = 0
                first_entry = None
                entries = state.get("playlist_entries")
                if isinstance(entries, list) and entries:
                    candidate = entries[0]
                    if isinstance(candidate, dict):
                        first_entry = dict(candidate)
                rebuilt_entries: List[Dict[str, Any]] = []
                for entry_index, path in enumerate(lane_paths):
                    if entry_index == 0 and first_entry is not None:
                        entry = dict(first_entry)
                    else:
                        entry = {}
                    entry["path"] = path
                    entry["entry_id"] = entry_index
                    rebuilt_entries.append(entry)
                state["playlist_entries"] = rebuilt_entries
                tile.from_state(state)
                restored = True
            except Exception:
                logger.debug("virtual roller lane saved-state restore failed", exc_info=True)
        if not restored:
            tile.clear_playlist()
            for path in lane_paths:
                tile.add_to_playlist(path, play_now=False)
            tile.current_index = 0 if tile.playlist else -1
        self._apply_virtual_lane_bookmark_targets(tile, lane_sources)
        for source in lane_sources:
            subtitle = str(source.get("subtitle", "") or "").strip()
            path = str(source.get("path", "") or "").strip()
            if subtitle and path:
                tile.set_external_subtitle_for_path(path, subtitle, overwrite=True)

    def _apply_virtual_lane_bookmark_targets(self, tile: VideoTile, lane_sources: List[Dict[str, Any]]) -> None:
        for entry_index, source in enumerate(list(lane_sources or [])):
            self._apply_virtual_source_bookmark_targets(tile, entry_index, source)

    def _apply_virtual_source_bookmark_targets(self, tile: VideoTile, entry_index: int, source: Dict[str, Any]) -> None:
        if "bookmark_targets" not in source:
            return
        targets = self._normalize_virtual_source_bookmark_targets(source.get("bookmark_targets"))
        try:
            tile.set_playlist_entry_bookmark_targets(int(entry_index), targets, cursor=0)
        except Exception:
            logger.debug("virtual roller bookmark target apply failed", exc_info=True)

    def _virtual_roller_bookmark_source_mode(self) -> bool:
        return any("bookmark_targets" in entry for entry in list(self._virtual_roller_sources or []))

    def _assign_virtual_roller_sources(self, docked_tiles: List[VideoTile], base_slot: int):
        ordered_sources = self._virtual_roller_assignable_sources()
        source_count = len(ordered_sources)
        if source_count <= 0:
            for tile in docked_tiles:
                try:
                    tile.clear_playlist()
                except Exception:
                    logger.debug("virtual roller tile clear failed", exc_info=True)
            return
        pool_size = len(docked_tiles)
        if pool_size <= 0:
            return
        for idx, tile in enumerate(docked_tiles):
            display_slot = (idx - int(base_slot)) % pool_size
            source_index = display_slot % source_count
            lane_sources = self._virtual_roller_lane_sources(ordered_sources, source_index, pool_size)
            self._assign_virtual_lane_to_tile(tile, lane_sources)

    def _invoke_tile_playback(self, tile: VideoTile, action: str):
        previous = bool(getattr(tile, "_suppress_playback_notify", False))
        setattr(tile, "_suppress_playback_notify", True)
        try:
            getattr(tile, action)()
        finally:
            setattr(tile, "_suppress_playback_notify", previous)

    def refresh_tile_surfaces(
        self,
        tiles: Optional[List[VideoTile]] = None,
        *,
        preserve_playback: bool = True,
        delays: tuple[int, ...] = (0, 60, 160),
    ):
        target_tiles: List[VideoTile] = []
        seen: set[VideoTile] = set()
        for tile in list(tiles or self.tiles):
            if tile in seen or tile not in self.tiles:
                continue
            seen.add(tile)
            target_tiles.append(tile)
        if not target_tiles:
            return
        playback_states = {
            tile: bool(preserve_playback and self._tile_is_playing(tile))
            for tile in target_tiles
        }
        self._refresh_tile_surfaces_step(playback_states, allow_resume=False)
        delayed_attempts = [int(delay) for delay in delays if int(delay) > 0]
        for attempt_index, delay_ms in enumerate(delayed_attempts, start=1):
            QtCore.QTimer.singleShot(
                delay_ms,
                lambda states=playback_states.copy(), allow_resume=(attempt_index >= 2): self._refresh_tile_surfaces_step(
                    states,
                    allow_resume=allow_resume,
                ),
            )

    def _refresh_tile_surfaces_step(
        self,
        playback_states: Dict[VideoTile, bool],
        *,
        allow_resume: bool = True,
    ):
        for tile, was_playing in list(playback_states.items()):
            if tile not in self.tiles:
                continue
            player = getattr(tile, "mediaplayer", None)
            if player is None:
                continue
            try:
                if tile.is_static_image():
                    tile._refresh_image_display()
                    continue
            except Exception:
                logger.debug("tile static-image probe failed during surface refresh", exc_info=True)
            try:
                if player.get_media() is None:
                    continue
            except Exception:
                logger.debug("tile media probe failed during surface refresh", exc_info=True)
                continue
            try:
                tile.bind_hwnd(force=True)
            except Exception:
                logger.debug("tile bind_hwnd(force=True) refresh failed", exc_info=True)
                continue
            try:
                tile._apply_display_mode()
            except Exception:
                logger.debug("tile display mode refresh failed after force bind", exc_info=True)
            if not was_playing or not allow_resume:
                continue
            try:
                player.set_rate(float(getattr(tile, "playback_rate", 1.0) or 1.0))
            except Exception:
                logger.debug("tile playback rate restore failed during surface refresh", exc_info=True)
            try:
                if not self._tile_is_playing(tile):
                    player.play()
            except Exception:
                logger.debug("tile playback resume failed during surface refresh", exc_info=True)
            try:
                tile._update_play_button()
            except Exception:
                logger.debug("tile play button refresh failed during surface refresh", exc_info=True)

    def _roller_visible_slots(self, n: int) -> int:
        n = max(1, int(n))
        if n <= 1:
            return 1
        requested = max(1, min(self.roller_visible_count(), n))
        if requested >= n:
            # A single-strip roller needs at least one slot of headroom to wrap
            # without showing a blank gap at the entry edge.
            return max(1, n - 1)
        return requested

    def _roller_metrics(
        self,
        mode: str,
        n: int,
        viewport_w: int,
        viewport_h: int,
    ) -> tuple[str, int, int]:
        count = max(1, int(n))
        slots = self._roller_visible_slots(count)
        effective_slots = float(slots)
        if slots > 1:
            effective_slots = max(1.0, float(slots) - float(self.ROLLER_PEEK_FRACTION))
        if mode == self.LAYOUT_ROLLER_COLUMN:
            step = max(1, int(math.ceil(max(1, viewport_h) / effective_slots)))
            return "y", step, step * count
        step = max(1, int(math.ceil(max(1, viewport_w) / effective_slots)))
        return "x", step, step * count

    def _set_roller_running(self, enabled: bool):
        if enabled:
            if not self._roller_timer.isActive():
                self._roller_last_tick_ms = QtCore.QDateTime.currentMSecsSinceEpoch()
                self._roller_timer.start()
            return
        if self._roller_timer.isActive():
            self._roller_timer.stop()
        self._roller_last_tick_ms = 0

    def _roller_has_media(self, docked_tiles: List[VideoTile]) -> bool:
        for tile in docked_tiles:
            if tile is None or tile not in self.tiles:
                continue
            try:
                if bool(getattr(tile, "playlist", None)):
                    return True
                if self._tile_has_loaded_media(tile):
                    return True
            except Exception:
                logger.debug("roller media probe failed", exc_info=True)
        return False

    def _advance_roller(self):
        if self._closing_for_app_exit:
            self._set_roller_running(False)
            return
        mode = self._roller_mode()
        docked_tiles = self.docked_tiles()
        n = len(docked_tiles)
        if (
            mode is None
            or n <= 1
            or self.roller_paused()
            or not self._roller_has_media(docked_tiles)
            or self.spotlight_index is not None
            or self.width() <= 0
            or self.height() <= 0
        ):
            self._set_roller_running(False)
            return
        metric_mode = self._roller_axis_mode(mode)
        _axis, step, total = self._roller_metrics(metric_mode, n, self.width(), self.height())
        if total <= 0:
            return
        previous_offset = float(self._roller_offset_px)
        now_ms = QtCore.QDateTime.currentMSecsSinceEpoch()
        last_ms = self._roller_last_tick_ms or now_ms
        self._roller_last_tick_ms = now_ms
        delta_ms = max(0, int(now_ms - last_ms))
        if delta_ms <= 0:
            return
        direction_sign = self.roller_direction_sign()
        delta_px = (float(delta_ms) / 1000.0) * float(self._roller_px_per_sec) * float(direction_sign)
        self._roller_offset_px = (float(self._roller_offset_px) + delta_px) % float(total)
        if (
            self._virtual_roller_mode(mode) is not None
            and step > 0
            and n > 0
            and self._virtual_roller_sources
        ):
            old_slot = int(previous_offset // float(step)) % n
            new_slot = int(float(self._roller_offset_px) // float(step)) % n
            if new_slot != old_slot:
                if direction_sign > 0:
                    delta_slots = (new_slot - old_slot) % n
                else:
                    delta_slots = (old_slot - new_slot) % n
                self._virtual_roller_scroll_index = (
                    int(self._virtual_roller_scroll_index) + (int(direction_sign) * int(delta_slots))
                ) % len(self._virtual_roller_sources)
                self._advance_virtual_roller_wrapped_tiles(
                    docked_tiles,
                    old_slot,
                    delta_slots,
                    direction_sign=direction_sign,
                )
        self.relayout()

    def _advance_virtual_roller_wrapped_tiles(
        self,
        docked_tiles: List[VideoTile],
        old_slot: int,
        delta_slots: int,
        *,
        direction_sign: int,
    ) -> None:
        if not docked_tiles or delta_slots <= 0:
            return
        tile_count = len(docked_tiles)
        for slot_offset in range(int(delta_slots)):
            if direction_sign > 0:
                tile_index = (int(old_slot) + slot_offset) % tile_count
                lane_step = 1
            else:
                tile_index = (int(old_slot) - 1 - slot_offset) % tile_count
                lane_step = -1
            tile = docked_tiles[tile_index]
            try:
                self._advance_virtual_roller_lane_on_wrap(tile, lane_step=lane_step)
            except Exception:
                logger.debug("virtual roller lane wrap advance failed", exc_info=True)

    def _advance_virtual_roller_lane_on_wrap(self, tile: VideoTile, *, lane_step: int = 1) -> None:
        playlist = [str(path or "").strip() for path in list(getattr(tile, "playlist", []) or [])]
        if len(playlist) <= 1:
            return
        current_path = ""
        try:
            current_path = str(tile._current_playlist_path() or tile._current_media_path() or "").strip()
        except Exception:
            logger.debug("virtual roller current-path probe failed during wrap advance", exc_info=True)
        if current_path:
            self._save_virtual_roller_state_for_tile(tile)
        try:
            current_index = int(getattr(tile, "current_index", 0))
        except (TypeError, ValueError):
            current_index = 0
        if not (0 <= current_index < len(playlist)):
            current_index = 0
        step_value = -1 if int(lane_step) < 0 else 1
        next_index = (current_index + step_value) % len(playlist)
        if next_index == current_index:
            return
        was_playing = self._tile_is_playing(tile)
        next_path = playlist[next_index]
        restored = False
        saved_state = None if self._virtual_roller_bookmark_source_mode() else self._saved_virtual_roller_state(next_path)
        if saved_state:
            try:
                state = dict(saved_state)
                state["playing"] = False
                state["playlist"] = list(playlist)
                state["current_index"] = next_index
                current_entry = None
                entries = state.get("playlist_entries")
                if isinstance(entries, list) and entries:
                    candidate_index = min(
                        max(int(saved_state.get("current_index", 0) or 0), 0),
                        len(entries) - 1,
                    )
                    candidate = entries[candidate_index]
                    if isinstance(candidate, dict):
                        current_entry = dict(candidate)
                rebuilt_entries: List[Dict[str, Any]] = []
                for entry_index, path in enumerate(playlist):
                    if entry_index == next_index and current_entry is not None:
                        entry = dict(current_entry)
                    else:
                        entry = {}
                    entry["path"] = path
                    entry["entry_id"] = entry_index
                    rebuilt_entries.append(entry)
                state["playlist_entries"] = rebuilt_entries
                tile.from_state(state)
                restored = True
            except Exception:
                logger.debug("virtual roller saved-state restore failed during wrap advance", exc_info=True)
        if not restored:
            tile.current_index = next_index
            if not tile.set_media(next_path, show_error_dialog=False):
                return
            try:
                tile._apply_current_playlist_start_position()
            except Exception:
                logger.debug("virtual roller lane start-position apply failed during wrap advance", exc_info=True)
        if was_playing:
            self._invoke_tile_playback(tile, "play")

    def _apply_roller_layout(self, docked_tiles: List[VideoTile], viewport_w: int, viewport_h: int) -> bool:
        mode = self._roller_mode()
        n = len(docked_tiles)
        if (
            mode is None
            or n <= 1
            or self.spotlight_index is not None
            or viewport_w <= 0
            or viewport_h <= 0
        ):
            self._set_roller_running(False)
            return False
        metric_mode = self._roller_axis_mode(mode)
        axis, step, total = self._roller_metrics(metric_mode, n, viewport_w, viewport_h)
        if total <= 0:
            self._set_roller_running(False)
            return False
        self._roller_offset_px = float(self._roller_offset_px) % float(total)
        offset = float(self._roller_offset_px)
        if self._virtual_roller_mode(mode) is not None and n > 0:
            if any(not list(getattr(tile, "playlist", []) or []) for tile in docked_tiles):
                base_slot = int(offset // float(step)) % n if step > 0 else 0
                self._assign_virtual_roller_sources(docked_tiles, base_slot)
        for idx, tile in enumerate(docked_tiles):
            pos = float(idx * step) - offset
            while pos <= -float(step):
                pos += float(total)
            if axis == "y":
                rect = QtCore.QRect(0, int(round(pos)), viewport_w, step)
            else:
                rect = QtCore.QRect(int(round(pos)), 0, step, viewport_h)
            self._set_tile_geometry_if_needed(tile, rect)
            self._set_tile_visible_if_needed(tile, True)
        viewport_rect = QtCore.QRect(0, 0, viewport_w, viewport_h)
        self._sync_roller_playback(docked_tiles, viewport_rect)
        self._set_roller_running(not self.roller_paused() and self._roller_has_media(docked_tiles))
        return True

    def _grid_dimensions_for_count(self, n: int) -> tuple[int, int]:
        n = max(0, int(n))
        if n <= 0:
            return 0, 0
        mode = self.normalize_layout_mode(self._layout_mode)
        if mode == self.LAYOUT_ROW:
            return n, 1
        if mode == self.LAYOUT_COLUMN:
            return 1, n
        if mode == self.LAYOUT_WIDE:
            cols = max(1, math.ceil(math.sqrt(n * 1.8)))
            rows = math.ceil(n / cols)
            return cols, rows
        if mode == self.LAYOUT_TALL:
            rows = max(1, math.ceil(math.sqrt(n * 1.8)))
            cols = math.ceil(n / rows)
            return cols, rows
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols) if cols > 0 else 0
        return cols, rows

    def _distribute_extent(self, total: int, parts: int) -> list[int]:
        total = max(0, int(total))
        parts = max(1, int(parts))
        base = total // parts
        remainder = total % parts
        return [base + (1 if index < remainder else 0) for index in range(parts)]

    def _auto_row_distribution(self, n: int) -> list[int]:
        n = max(0, int(n))
        if n <= 0:
            return []
        _cols, rows = self._grid_dimensions_for_count(n)
        if rows <= 1:
            return [n]
        distribution: list[int] = []
        remaining = n
        for row_index in range(rows):
            remaining_rows = rows - row_index
            count = max(1, math.ceil(remaining / remaining_rows))
            distribution.append(count)
            remaining -= count
        return distribution

    def _apply_balanced_auto_layout(
        self,
        docked_tiles: List[VideoTile],
        viewport_w: int,
        viewport_h: int,
    ) -> bool:
        if self.normalize_layout_mode(self._layout_mode) != self.LAYOUT_AUTO:
            return False
        n = len(docked_tiles)
        if n <= 0:
            return False
        row_counts = self._auto_row_distribution(n)
        if not row_counts:
            return False
        row_heights = self._distribute_extent(viewport_h, len(row_counts))
        tile_index = 0
        y = 0
        for row_count, row_height in zip(row_counts, row_heights):
            col_widths = self._distribute_extent(viewport_w, row_count)
            x = 0
            for col_width in col_widths:
                if tile_index >= n:
                    break
                tile = docked_tiles[tile_index]
                tile_index += 1
                rect = QtCore.QRect(x, y, col_width, row_height)
                geom_changed = self._set_tile_geometry_if_needed(tile, rect)
                vis_changed = self._set_tile_visible_if_needed(tile, True)
                if geom_changed or vis_changed:
                    tile.bind_hwnd()
                x += col_width
            y += row_height
        return tile_index == n

    def docked_tiles(self) -> List[VideoTile]:
        return [
            t for t in self.tiles
            if t not in self.detached_windows and t not in self._opacity_dock_tiles
        ]

    def mark_tiles_in_opacity_dock(self, tiles: List[VideoTile]):
        changed = False
        for tile in list(tiles or []):
            if tile in self.tiles and tile not in self.detached_windows and tile not in self._opacity_dock_tiles:
                self._opacity_dock_tiles.add(tile)
                changed = True
        if changed:
            self.relayout()

    def unmark_tiles_in_opacity_dock(self, tiles: List[VideoTile]):
        changed = False
        for tile in list(tiles or []):
            if tile in self._opacity_dock_tiles:
                self._opacity_dock_tiles.discard(tile)
                changed = True
        if changed:
            self.relayout()

    def is_detached(self, tile: VideoTile) -> bool:
        return tile in self.detached_windows

    def detached_window_for_tile(self, tile: VideoTile) -> Optional[DetachedTileWindow]:
        return self.detached_windows.get(tile)

    def active_detached_window(self) -> Optional[DetachedTileWindow]:
        app = QtWidgets.QApplication.instance()
        if app is None:
            return None
        window = app.activeWindow()
        if isinstance(window, DetachedTileWindow) and window in self.detached_windows.values():
            return window
        focus_widget = app.focusWidget()
        try:
            focus_window = focus_widget.window() if focus_widget is not None else None
        except RuntimeError:
            focus_window = None
        if isinstance(focus_window, DetachedTileWindow) and focus_window in self.detached_windows.values():
            return focus_window
        return None

    def is_managed_window(self, window: Optional[QtWidgets.QWidget]) -> bool:
        if window is None:
            return False
        if window is self.window():
            return True
        return window in self.detached_windows.values()

    def canvas_global_rect(self) -> QtCore.QRect:
        top_left = self.mapToGlobal(QtCore.QPoint(0, 0))
        return QtCore.QRect(top_left, self.size())

    def _canvas_drop_target_available(self) -> bool:
        try:
            window = self.window()
            if window is None:
                return False
            if not window.isVisible():
                return False
            if bool(window.windowState() & QtCore.Qt.WindowState.WindowMinimized) or window.isMinimized():
                return False
        except RuntimeError:
            logger.debug("canvas drop-target window probe failed", exc_info=True)
            return False
        try:
            return self.isVisible()
        except RuntimeError:
            logger.debug("canvas visibility probe failed", exc_info=True)
            return True

    def contains_global_point(self, gp: QtCore.QPoint) -> bool:
        if not self._canvas_drop_target_available():
            return False
        return self.canvas_global_rect().contains(gp)

    def docked_tile_at_global(self, gp: QtCore.QPoint, exclude: Optional[VideoTile] = None) -> Optional[VideoTile]:
        if not self._canvas_drop_target_available():
            return None
        for tile in self.docked_tiles():
            if tile is exclude:
                continue
            rect = QtCore.QRect(tile.mapToGlobal(QtCore.QPoint(0, 0)), tile.size())
            if rect.contains(gp):
                return tile
        return None

    def move_tile_to_index(self, tile: VideoTile, index: int):
        if tile not in self.tiles:
            return
        old_index = self.tiles.index(tile)
        self.tiles.pop(old_index)
        index = max(0, min(index, len(self.tiles)))
        if index > old_index:
            index -= 1
        self.tiles.insert(index, tile)

    def swap_tiles(self, first: VideoTile, second: VideoTile):
        if first not in self.tiles or second not in self.tiles or first is second:
            return
        i = self.tiles.index(first)
        j = self.tiles.index(second)
        self.tiles[i], self.tiles[j] = self.tiles[j], self.tiles[i]
        self.relayout()
        self._notify_playlist_changed()

    def _always_on_top_enabled(self) -> bool:
        mw = self.window()
        try:
            return bool(getattr(mw, "always_on_top_action").isChecked())
        except (AttributeError, RuntimeError):
            logger.debug("canvas always-on-top action probe failed", exc_info=True)
            return False

    def _compact_mode_enabled(self) -> bool:
        mw = self.window()
        try:
            return bool(getattr(mw, "_is_compact_mode")())
        except (AttributeError, RuntimeError):
            logger.debug("canvas compact action probe failed", exc_info=True)
            return False

    def set_detached_windows_on_top(self, enabled: bool):
        for window in list(self.detached_windows.values()):
            try:
                window.set_always_on_top(enabled)
            except RuntimeError:
                logger.warning("set_always_on_top failed for detached window", exc_info=True)

    def set_detached_windows_compact_mode(self, enabled: bool):
        for window in list(self.detached_windows.values()):
            try:
                window.set_compact_mode(enabled)
            except RuntimeError:
                logger.warning("set_compact_mode failed for detached window", exc_info=True)

    def set_tile_window_opacity(self, tile: VideoTile, opacity: float):
        self.set_tile_window_opacity_with_geometry(tile, opacity)

    def fit_tile_window_to_media(self, tile: VideoTile) -> bool:
        if tile not in self.tiles:
            return False
        if not self.is_detached(tile):
            self.detach_tile(tile)
        window = self.detached_window_for_tile(tile)
        if window is None:
            return False
        return bool(window.fit_to_media_size())

    def set_tile_window_opacity_with_geometry(
        self,
        tile: VideoTile,
        opacity: float,
        *,
        detach_geometry: Optional[QtCore.QRect] = None,
    ):
        if tile not in self.tiles:
            return
        if not self.is_detached(tile):
            self.detach_tile(tile, initial_geometry=detach_geometry)
        window = self.detached_window_for_tile(tile)
        if window is None:
            return
        window.set_window_opacity_value(opacity)
        if window.overlay_active():
            self._restack_overlay_group(window.overlay_group_id())

    def docked_media_tiles(self) -> List[VideoTile]:
        items: List[VideoTile] = []
        for tile in self.docked_tiles():
            has_media = bool(getattr(tile, "playlist", None)) or bool(getattr(tile, "is_static_image", lambda: False)())
            if has_media:
                items.append(tile)
        return items

    def set_tiles_window_opacity(self, tiles: List[VideoTile], opacity: float) -> List[VideoTile]:
        changed: List[VideoTile] = []
        seen: set[VideoTile] = set()
        detach_geometries: Dict[VideoTile, QtCore.QRect] = {}
        for tile in list(tiles or []):
            if tile in seen or tile not in self.tiles:
                continue
            seen.add(tile)
            if self.is_detached(tile):
                continue
            try:
                detach_geometries[tile] = QtCore.QRect(tile.mapToGlobal(QtCore.QPoint(0, 0)), tile.size())
            except RuntimeError:
                logger.debug("batch opacity detach geometry capture skipped", exc_info=True)
        seen.clear()
        for tile in list(tiles or []):
            if tile in seen or tile not in self.tiles:
                continue
            seen.add(tile)
            self.set_tile_window_opacity_with_geometry(
                tile,
                opacity,
                detach_geometry=detach_geometries.get(tile),
            )
            changed.append(tile)
        return changed

    def overlay_group_id_for_tile(self, tile: VideoTile) -> str:
        return overlay_group_id_for_tile_impl(self, tile)

    def overlay_group_tiles(self, group_id: str) -> List[VideoTile]:
        return overlay_group_tiles_impl(self, group_id)

    def _overlay_default_opacity(self, order: int, total_count: int) -> float:
        return overlay_default_opacity_impl(self, order, total_count)

    def overlay_audio_mode_for_tile(self, tile: VideoTile) -> str:
        return overlay_audio_mode_for_tile_impl(self, tile)

    def _reapply_overlay_group_opacity_rule(self, group_id: str):
        reapply_overlay_group_opacity_rule_impl(self, group_id)

    def overlay_stack_tiles(self, leader_tile: VideoTile, tiles: Optional[List[VideoTile]] = None) -> bool:
        return overlay_stack_tiles_impl(self, leader_tile, tiles=tiles)

    def set_overlay_opacity_for_tile(self, tile: VideoTile, opacity: float):
        set_overlay_opacity_for_tile_impl(self, tile, opacity)

    def set_overlay_audio_mode_for_tile(self, tile: VideoTile, mode: str):
        set_overlay_audio_mode_for_tile_impl(self, tile, mode)

    def clear_overlay_stack(self, tile: VideoTile):
        clear_overlay_stack_impl(self, tile)

    def clear_overlay_stack_for_group(self, group_id: str, *, restore_focus: bool = True):
        clear_overlay_stack_for_group_impl(self, group_id, restore_focus=restore_focus)

    def _sync_overlay_group_geometry(self, leader_tile: VideoTile, geometry: QtCore.QRect):
        sync_overlay_group_geometry_impl(self, leader_tile, geometry)

    def _sync_overlay_group_window_mode(self, leader_tile: VideoTile):
        sync_overlay_group_window_mode_impl(self, leader_tile)

    def _restack_overlay_group(self, group_id: str):
        restack_overlay_group_impl(self, group_id)

    def _on_overlay_geometry_changed(self, tile: VideoTile, geometry: QtCore.QRect):
        on_overlay_geometry_changed_impl(self, tile, geometry)

    def _on_overlay_restack_requested(self, tile: VideoTile):
        on_overlay_restack_requested_impl(self, tile)

    def _minimize_main_window_if_no_docked_tiles(self):
        if self.docked_tiles():
            return
        mw = self.window()
        if mw is None:
            return
        try:
            if bool(getattr(mw, "is_opacity_mode_active", lambda: False)()):
                return
        except Exception:
            pass
        try:
            already_minimized = bool(mw.windowState() & QtCore.Qt.WindowState.WindowMinimized) or mw.isMinimized()
        except RuntimeError:
            logger.debug("main window minimized-state probe failed", exc_info=True)
            already_minimized = False
        if already_minimized:
            return
        try:
            mw.showMinimized()
        except RuntimeError:
            logger.warning("main window showMinimized failed", exc_info=True)

    def detach_tile(
        self,
        tile: VideoTile,
        *,
        global_pos: Optional[QtCore.QPoint] = None,
        grab_offset: Optional[QtCore.QPoint] = None,
        initial_geometry: Optional[QtCore.QRect] = None,
        restore_focus: bool = True,
    ):
        if tile not in self.tiles or self.is_detached(tile):
            return
        if (
            self._virtual_roller_mode() is not None
            and tile in self.docked_tiles()
            and not bool(getattr(tile, "_virtual_roller_detached_clone", False))
        ):
            if self._detach_virtual_roller_tile(
                tile,
                global_pos=global_pos,
                grab_offset=grab_offset,
                initial_geometry=initial_geometry,
                restore_focus=restore_focus,
            ):
                return
        opacity_dock_owner = getattr(tile, "_opacity_dock_owner", None)
        if opacity_dock_owner is not None:
            release = getattr(opacity_dock_owner, "release_tile_to_detached", None)
            if callable(release):
                try:
                    release(tile)
                except Exception:
                    logger.debug("opacity dock tile release skipped during detach", exc_info=True)
        if self.spotlight_index is not None:
            self.set_spotlight(None)
        if initial_geometry is not None:
            target_geometry = QtCore.QRect(initial_geometry)
        else:
            tile_top_left = tile.mapToGlobal(QtCore.QPoint(0, 0))
            tile_size = tile.size()
            if global_pos is not None and grab_offset is not None:
                top_left = global_pos - grab_offset
            else:
                top_left = tile_top_left
            target_geometry = QtCore.QRect(top_left, tile_size)
        window = DetachedTileWindow(
            tile,
            always_on_top=self._always_on_top_enabled(),
            compact_mode=self._compact_mode_enabled(),
        )
        window.redockRequested.connect(self._redock_from_window_request)
        window.overlayGeometryChanged.connect(self._on_overlay_geometry_changed)
        window.overlayRestackRequested.connect(self._on_overlay_restack_requested)
        self.detached_windows[tile] = window
        tile.setParent(window.centralWidget())
        window.attach_tile(tile)
        window.set_window_opacity_value(getattr(tile, "detached_window_opacity", 1.0), update_tile=False)
        window.setGeometry(target_geometry)
        window.show()
        if restore_focus:
            window.raise_()
            try:
                window.activateWindow()
            except RuntimeError:
                logger.debug("detached window activateWindow skipped after detach", exc_info=True)
        try:
            from canvas_support.focus_review_window import reanchor_focus_review_window

            reanchor_focus_review_window(tile)
        except Exception:
            logger.debug("focus review window reanchor skipped during detach", exc_info=True)
        tile.show()
        tile.bind_hwnd(force=True)
        self.relayout()
        self.refresh_tile_surfaces(self.docked_tiles() + [tile])
        self._minimize_main_window_if_no_docked_tiles()
        if restore_focus:
            window.restore_focus()
        self._notify_playlist_changed()

    def _detach_virtual_roller_tile(
        self,
        tile: VideoTile,
        *,
        global_pos: Optional[QtCore.QPoint] = None,
        grab_offset: Optional[QtCore.QPoint] = None,
        initial_geometry: Optional[QtCore.QRect] = None,
        restore_focus: bool = True,
    ) -> bool:
        try:
            current_path = str(tile._current_playlist_path() or tile._current_media_path() or "").strip()
        except Exception:
            logger.debug("virtual roller detach current-path probe failed", exc_info=True)
            current_path = ""
        if not current_path:
            return False
        if initial_geometry is not None:
            target_geometry = QtCore.QRect(initial_geometry)
        else:
            tile_top_left = tile.mapToGlobal(QtCore.QPoint(0, 0))
            tile_size = tile.size()
            if global_pos is not None and grab_offset is not None:
                top_left = global_pos - grab_offset
            else:
                top_left = tile_top_left
            target_geometry = QtCore.QRect(top_left, tile_size)
        try:
            cloned_state = dict(tile.to_state())
        except Exception:
            logger.debug("virtual roller detach tile state capture failed", exc_info=True)
            return False
        first_entry = None
        entries = cloned_state.get("playlist_entries")
        if isinstance(entries, list) and entries:
            candidate = entries[min(max(int(getattr(tile, "current_index", 0) or 0), 0), len(entries) - 1)]
            if isinstance(candidate, dict):
                first_entry = dict(candidate)
        current_subtitle = str(tile.get_external_subtitle_for_path(current_path) or "").strip()
        cloned_state["playlist"] = [current_path]
        cloned_state["current_index"] = 0
        if first_entry is not None:
            first_entry["path"] = current_path
            first_entry["entry_id"] = 0
            cloned_state["playlist_entries"] = [first_entry]
        else:
            cloned_state["playlist_entries"] = [{"path": current_path, "entry_id": 0}]
        if current_subtitle:
            cloned_state["subtitles"] = {tile._normalize_media_path(current_path): current_subtitle}
        else:
            cloned_state["subtitles"] = {}
        detached_tile = self._create_tile_widget()
        self.tiles.append(detached_tile)
        setattr(detached_tile, "_virtual_roller_detached_clone", True)
        setattr(detached_tile, "_virtual_roller_source_key", self._virtual_roller_source_key(current_path))
        window = DetachedTileWindow(
            detached_tile,
            always_on_top=self._always_on_top_enabled(),
            compact_mode=self._compact_mode_enabled(),
        )
        window.redockRequested.connect(self._redock_from_window_request)
        window.overlayGeometryChanged.connect(self._on_overlay_geometry_changed)
        window.overlayRestackRequested.connect(self._on_overlay_restack_requested)
        self.detached_windows[detached_tile] = window
        try:
            detached_tile.from_state(cloned_state)
        except Exception:
            logger.debug("virtual roller detached tile state restore failed", exc_info=True)
        window.set_window_opacity_value(getattr(detached_tile, "detached_window_opacity", 1.0), update_tile=False)
        window.setGeometry(target_geometry)
        window.show()
        if restore_focus:
            window.raise_()
            try:
                window.activateWindow()
            except RuntimeError:
                logger.debug("virtual roller detached window activateWindow skipped", exc_info=True)
        detached_tile.show()
        try:
            detached_tile.bind_hwnd(force=True)
        except Exception:
            logger.debug("virtual roller detached tile force-bind skipped", exc_info=True)
        should_resume_source = self._advance_virtual_roller_lane_after_detach(tile, current_path)
        if should_resume_source:
            self._roller_playback_active = True
            self._roller_last_visible_tiles.discard(tile)
        self.relayout()
        self.refresh_tile_surfaces([tile, detached_tile])
        self._minimize_main_window_if_no_docked_tiles()
        if restore_focus:
            window.restore_focus()
        self._notify_playlist_changed()
        return True

    def _advance_virtual_roller_lane_after_detach(self, tile: VideoTile, removed_path: str) -> bool:
        playlist = [str(path or "").strip() for path in list(getattr(tile, "playlist", []) or [])]
        if not playlist:
            return False
        if len(playlist) <= 1:
            # When this lane only has the current source, detach should behave as
            # a pure clone. Keeping the source tile intact avoids dropping the
            # docked lane to an empty playlist, which can cascade into roller
            # pause/reconfiguration side effects.
            return self._tile_is_playing(tile)
        try:
            removed_index = int(getattr(tile, "current_index", 0))
        except (TypeError, ValueError):
            removed_index = 0
        if not (0 <= removed_index < len(playlist)):
            try:
                removed_index = playlist.index(str(removed_path or "").strip())
            except ValueError:
                removed_index = 0
        was_playing = self._tile_is_playing(tile)
        playlist.pop(removed_index)
        try:
            remove_playlist_entry_start_positions(tile, [removed_index])
        except Exception:
            logger.debug("virtual roller lane bookmark removal skipped during detach", exc_info=True)
        try:
            tile.pop_external_subtitle_for_path(removed_path)
        except Exception:
            logger.debug("virtual roller lane subtitle removal skipped during detach", exc_info=True)
        tile.playlist = playlist
        if not playlist:
            tile.clear_playlist()
            return False
        next_index = min(max(0, removed_index), len(playlist) - 1)
        tile.current_index = next_index
        next_path = playlist[next_index]
        if not tile.set_media(next_path, show_error_dialog=False):
            return False
        try:
            tile._apply_current_playlist_start_position()
        except Exception:
            logger.debug("virtual roller lane start-position apply failed during detach", exc_info=True)
        if was_playing:
            self._invoke_tile_playback(tile, "play")
            return True
        self._invoke_tile_playback(tile, "pause")
        return False

    def _disconnect_detached_window_signals(self, window: DetachedTileWindow):
        try:
            window.redockRequested.disconnect(self._redock_from_window_request)
        except (RuntimeError, TypeError):
            logger.debug("detached window redockRequested disconnect skipped", exc_info=True)
        try:
            window.overlayGeometryChanged.disconnect(self._on_overlay_geometry_changed)
        except (RuntimeError, TypeError):
            logger.debug("detached window overlayGeometryChanged disconnect skipped", exc_info=True)
        try:
            window.overlayRestackRequested.disconnect(self._on_overlay_restack_requested)
        except (RuntimeError, TypeError):
            logger.debug("detached window overlayRestackRequested disconnect skipped", exc_info=True)

    def _redock_virtual_roller_detached_clone(self, tile: VideoTile):
        window = self.detached_windows.pop(tile, None)
        if window is None:
            return
        try:
            window._cancel_deferred_callbacks()
        except RuntimeError:
            logger.debug("virtual roller detached clone deferred cancel skipped", exc_info=True)
        self._disconnect_detached_window_signals(window)
        taken_tile = window.take_tile() or tile
        self._save_virtual_roller_state_for_tile(taken_tile)
        try:
            taken_tile.shutdown()
        except Exception:
            logger.warning("virtual roller detached clone shutdown failed during redock", exc_info=True)
            try:
                taken_tile.stop()
            except Exception:
                logger.debug("virtual roller detached clone stop fallback failed", exc_info=True)
        if taken_tile in self.tiles:
            self.tiles.remove(taken_tile)
        try:
            taken_tile.setParent(None)
        except RuntimeError:
            logger.debug("virtual roller detached clone parent reset skipped", exc_info=True)
        try:
            taken_tile.deleteLater()
        except RuntimeError:
            logger.debug("virtual roller detached clone deleteLater skipped", exc_info=True)
        window.hide()
        window.deleteLater()
        self.relayout()
        self.refresh_tile_surfaces(self.docked_tiles())
        self._notify_playlist_changed()

    def redock_tile(self, tile: VideoTile, target_tile: Optional[VideoTile] = None):
        overlay_group_id = self.overlay_group_id_for_tile(tile)
        if overlay_group_id:
            self.clear_overlay_stack_for_group(overlay_group_id, restore_focus=False)
        if bool(getattr(tile, "_virtual_roller_detached_clone", False)):
            self._redock_virtual_roller_detached_clone(tile)
            return
        window = self.detached_windows.pop(tile, None)
        if window is None:
            return
        try:
            window._cancel_deferred_callbacks()
        except RuntimeError:
            logger.debug("detached window deferred cancel skipped during redock", exc_info=True)
        self._disconnect_detached_window_signals(window)
        taken_tile = window.take_tile() or tile
        # Returning to the dock resets detached-only presentation state.
        # A future detach should start from the default fully opaque window.
        try:
            taken_tile.detached_window_opacity = 1.0
        except Exception:
            logger.debug("redocked tile opacity reset skipped", exc_info=True)
        try:
            from canvas_support.focus_review_window import reanchor_focus_review_window

            reanchor_focus_review_window(taken_tile)
        except Exception:
            logger.debug("focus review window reanchor skipped during redock", exc_info=True)
        opacity_dock_owner = getattr(taken_tile, "_opacity_dock_owner", None)
        if opacity_dock_owner is not None:
            accept = getattr(opacity_dock_owner, "accept_redocked_tile", None)
            if callable(accept):
                try:
                    if accept(taken_tile):
                        window.hide()
                        window.deleteLater()
                        self._notify_playlist_changed()
                        return
                except Exception:
                    logger.debug("opacity dock tile accept skipped during redock", exc_info=True)
        taken_tile.setParent(self)
        taken_tile.show()
        if target_tile is not None and target_tile in self.tiles and target_tile is not taken_tile:
            self.move_tile_to_index(taken_tile, self.tiles.index(target_tile))
        self.relayout()
        taken_tile.bind_hwnd(force=True)
        self.refresh_tile_surfaces(self.docked_tiles())
        window.hide()
        window.deleteLater()
        self._notify_playlist_changed()

    def _restore_main_window_if_minimized(self):
        mw = self.window()
        if mw is None:
            return
        try:
            minimized = bool(mw.windowState() & QtCore.Qt.WindowState.WindowMinimized) or mw.isMinimized()
        except RuntimeError:
            logger.debug("main window minimized probe failed during restore", exc_info=True)
            minimized = False
        if not minimized:
            return
        try:
            was_fullscreen = bool(mw.windowState() & QtCore.Qt.WindowState.WindowFullScreen) or mw.isFullScreen()
        except RuntimeError:
            logger.debug("main window fullscreen probe failed during restore", exc_info=True)
            was_fullscreen = False
        try:
            was_maximized = bool(mw.windowState() & QtCore.Qt.WindowState.WindowMaximized)
        except RuntimeError:
            logger.debug("main window maximized probe failed during restore", exc_info=True)
            was_maximized = False
        try:
            if was_fullscreen:
                mw.showFullScreen()
            elif was_maximized:
                mw.showMaximized()
            else:
                mw.showNormal()
        except RuntimeError:
            logger.warning("main window state restore failed; falling back to showNormal()", exc_info=True)
            try:
                mw.showNormal()
            except RuntimeError:
                logger.warning("main window showNormal fallback failed", exc_info=True)
        try:
            mw.raise_()
        except RuntimeError:
            logger.debug("main window raise skipped during restore", exc_info=True)
        try:
            mw.activateWindow()
        except RuntimeError:
            logger.debug("main window activateWindow skipped during restore", exc_info=True)
        try:
            if hasattr(mw, "_restore_window_focus"):
                mw._restore_window_focus()
        except RuntimeError:
            logger.debug("main window focus restore callback skipped", exc_info=True)

    def _redock_from_window_request(self, tile: VideoTile):
        if self.overlay_group_id_for_tile(tile):
            self.clear_overlay_stack(tile)
            return
        self._restore_main_window_if_minimized()
        self.redock_tile(tile)

    def redock_all_detached(self):
        if self._closing_for_app_exit:
            return
        for tile in list(self.detached_windows.keys()):
            self.redock_tile(tile)

    def snapshot_state(self) -> Dict[str, Any]:
        self._capture_virtual_roller_active_states()
        tiles = []
        for tile in self.tiles:
            entry: Dict[str, Any] = {
                "state": tile.to_state(),
                "detached": self.is_detached(tile),
            }
            if bool(getattr(tile, "_virtual_roller_detached_clone", False)):
                entry["virtual_roller_detached_clone"] = True
            if entry["detached"]:
                window = self.detached_window_for_tile(tile)
                entry["geometry"] = rect_to_data(window.geometry() if window is not None else None)
                overlay_payload = window.overlay_state_payload() if window is not None else None
                if overlay_payload is not None:
                    entry["overlay"] = overlay_payload
            tiles.append(entry)
        spotlight_index = self.spotlight_index
        if spotlight_index is not None and not (0 <= spotlight_index < len(self.tiles)):
            spotlight_index = None
        spotlight_restore_playing_indices = [
            idx
            for idx, tile in enumerate(self.tiles)
            if tile in self._spotlight_restore_playing_tiles
        ]
        return {
            "tiles": tiles,
            "spotlight_index": spotlight_index,
            "spotlight_restore_playing_indices": spotlight_restore_playing_indices,
            "layout_mode": self.layout_mode(),
            "roller_visible_count": self.roller_visible_count(),
            "roller_speed": self.roller_speed_px_per_sec(),
            "roller_paused": self.roller_paused(),
            "virtual_roller_sources": self.infinite_roller_sources(),
            "virtual_roller_scroll_index": int(self._virtual_roller_scroll_index),
            "virtual_roller_saved_states": self.infinite_roller_saved_states(),
        }

    def restore_detached_state(self, entries: List[Dict[str, Any]]):
        overlay_restore_entries: list[tuple[VideoTile, DetachedTileWindow, Dict[str, Any]]] = []
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict) or not entry.get("detached", False):
                continue
            if not (0 <= idx < len(self.tiles)):
                continue
            tile = self.tiles[idx]
            if bool(entry.get("virtual_roller_detached_clone", False)):
                setattr(tile, "_virtual_roller_detached_clone", True)
            self.detach_tile(tile)
            window = self.detached_window_for_tile(tile)
            if window is None:
                continue
            geom = rect_from_data(entry.get("geometry"))
            if geom is not None:
                window.setGeometry(geom)
            try:
                window.raise_()
            except RuntimeError:
                logger.debug("detached window raise skipped during state restore", exc_info=True)
            overlay_payload = entry.get("overlay")
            if isinstance(overlay_payload, dict):
                overlay_restore_entries.append((tile, window, dict(overlay_payload)))
        for tile, window, overlay_payload in overlay_restore_entries:
            group_id = str(overlay_payload.get("group_id") or "").strip()
            if not group_id:
                continue
            try:
                order = max(0, int(overlay_payload.get("order", 0)))
            except (TypeError, ValueError):
                order = 0
            opacity = overlay_payload.get("opacity", 1.0)
            window.set_overlay_state(
                group_id,
                order=order,
                leader=bool(overlay_payload.get("leader", False)),
                opacity=opacity,
                emit_sync=False,
            )
            window.set_overlay_audio_mode(overlay_payload.get("audio_mode", "leader"))
        restored_groups = {
            window.overlay_group_id()
            for _tile, window, _overlay in overlay_restore_entries
            if window.overlay_group_id()
        }
        for group_id in restored_groups:
            group_tiles = self.overlay_group_tiles(group_id)
            if not group_tiles:
                continue
            leader_tile = next(
                (
                    tile for tile in group_tiles
                    if (self.detached_window_for_tile(tile) is not None and self.detached_window_for_tile(tile).overlay_is_leader())
                ),
                group_tiles[0],
            )
            leader_window = self.detached_window_for_tile(leader_tile)
            if leader_window is not None:
                self.set_overlay_audio_mode_for_tile(
                    leader_tile,
                    getattr(leader_window, "overlay_audio_mode", lambda: "leader")(),
                )
                self._sync_overlay_group_geometry(leader_tile, leader_window.geometry())
                self._restack_overlay_group(group_id)

    def _notify_playlist_changed(self):
        if self._closing_for_app_exit:
            return
        if self._virtual_roller_mode() is not None and not self._virtual_roller_pool_updating:
            source_count = len(self._virtual_roller_sources)
            desired_pool = self._virtual_roller_desired_docked_pool_size(source_count)
            if source_count > 0 and len(self.docked_tiles()) != desired_pool:
                try:
                    self._configure_virtual_roller_tiles()
                except RuntimeError:
                    logger.warning("virtual roller reconfiguration after playlist change failed", exc_info=True)
        if self._roller_mode() is not None:
            try:
                self.relayout()
            except RuntimeError:
                logger.warning("roller relayout after playlist change failed", exc_info=True)
        mw = self.window()
        if mw is not None and hasattr(mw, "update_playlist"):
            try:
                if hasattr(mw, "request_playlist_refresh"):
                    mw.request_playlist_refresh(delay_ms=0)
                else:
                    mw.update_playlist()
            except RuntimeError:
                logger.warning("playlist refresh notification failed", exc_info=True)

    def _keep_detached_tiles_for_focus_modes(self) -> bool:
        mw = self.window()
        try:
            return bool(mw.keep_detached_tiles_for_focus_modes())
        except (AttributeError, RuntimeError):
            logger.debug("keep_detached_tiles_for_focus_modes probe failed", exc_info=True)
            return False

    def prepare_for_app_close(self):
        self._closing_for_app_exit = True
        self._set_roller_running(False)
        for window in list(self.detached_windows.values()):
            try:
                window.prepare_for_app_close()
            except RuntimeError:
                logger.warning("detached window prepare_for_app_close failed", exc_info=True)

    def finalize_app_close(self):
        for window in list(self.detached_windows.values()):
            try:
                window.close()
            except RuntimeError:
                logger.warning("detached window close failed during app shutdown", exc_info=True)
            try:
                window.deleteLater()
            except RuntimeError:
                logger.debug("detached window deleteLater skipped during app shutdown", exc_info=True)

    def get_selected_tiles(self, for_delete: bool = False) -> List[VideoTile]:
        if for_delete:
            return [t for t in self.tiles if getattr(t, "selection_mode", "") == "delete"]
        return [t for t in self.tiles if t.is_selected and getattr(t, "selection_mode", "") != "delete"]

    def spotlight_tile(self) -> Optional[VideoTile]:
        idx = self.spotlight_index
        if isinstance(idx, int) and 0 <= idx < len(self.tiles):
            tile = self.tiles[idx]
            if tile in self.tiles and not self.is_detached(tile):
                return tile
        return None

    def get_controlled_tiles(self, require_selection: bool = False) -> List[VideoTile]:
        selected = self.get_selected_tiles()
        if selected:
            return selected
        if require_selection:
            return []
        spotlight_tile = self.spotlight_tile()
        if spotlight_tile is not None:
            return [spotlight_tile]
        return list(self.tiles)

    def clear_selections(self):
        for t in self.tiles:
            t.set_selection(False)

    def move_controlled_positions(self, delta_s: float):
        self.apply_to_controlled_tiles(lambda t: t.move_position(delta_s))

    def apply_to_controlled_tiles(self, action_func, require_selection=False):
        for t in self.get_controlled_tiles(require_selection=require_selection):
            action_func(t)

    def _sync_opacity_mode_owners(self):
        owners = []
        seen = set()
        for tile in list(getattr(self, "_opacity_dock_tiles", set())):
            owner = getattr(tile, "_opacity_dock_owner", None)
            if owner is None:
                continue
            marker = id(owner)
            if marker in seen:
                continue
            seen.add(marker)
            owners.append(owner)
        for owner in owners:
            sync = getattr(owner, "sync_from_canvas_state", None)
            if callable(sync):
                try:
                    sync()
                except Exception:
                    logger.debug("opacity mode owner sync skipped", exc_info=True)

    def _create_tile_widget(self) -> VideoTile:
        tile = VideoTile(self, vlc_instance=self.vlc_instance)
        tile.double_clicked.connect(self._on_tile_double_clicked)
        mw = self.window()
        if mw is not None:
            try:
                tile.set_border_visible(bool(getattr(mw, "border_action").isChecked()))
            except (AttributeError, RuntimeError):
                logger.debug("new tile border-visible sync skipped", exc_info=True)
            try:
                tile.set_compact_mode(bool(getattr(mw, "_is_compact_mode")()))
            except (AttributeError, RuntimeError):
                logger.debug("new tile compact-mode sync skipped", exc_info=True)
        return tile

    def add_tile(self):
        playing_tiles = [t for t in self.tiles if t.mediaplayer.is_playing()]
        for t in playing_tiles:
            t.pause()
        tile = self._create_tile_widget()
        self.tiles.append(tile)
        tile.show()
        adopted_into_opacity_mode = False
        mw = self.window()
        if mw is not None:
            try:
                active_opacity_owner = getattr(mw, "active_opacity_mode_widget", lambda: None)()
            except Exception:
                active_opacity_owner = None
            if active_opacity_owner is not None:
                try:
                    adopted_into_opacity_mode = bool(active_opacity_owner.accept_redocked_tile(tile))
                except Exception:
                    logger.debug("new tile opacity-mode adopt failed", exc_info=True)
        if not adopted_into_opacity_mode:
            self.relayout()
        self._notify_playlist_changed()

        for t in playing_tiles:
            t.play()

    def remove_tile(self, tile: VideoTile):
        if tile in self.tiles:
            overlay_group_id = self.overlay_group_id_for_tile(tile)
            if overlay_group_id:
                self.clear_overlay_stack_for_group(overlay_group_id, restore_focus=False)
            detached_window = self.detached_windows.pop(tile, None)
            removed_idx = self.tiles.index(tile)
            playlist_to_move = tile.playlist.copy()
            subtitle_map_to_move = {
                path: tile.get_external_subtitle_for_path(path)
                for path in playlist_to_move
            }
            resume_tiles: List[VideoTile] = []
            leaving_spotlight = False
            if self.spotlight_index is not None:
                if self.spotlight_index == removed_idx:
                    leaving_spotlight = True
                    resume_tiles = [
                        t for t in self._spotlight_restore_playing_tiles
                        if t in self.tiles and t is not tile
                    ]
                    self.spotlight_index = None
                    self._spotlight_restore_playing_tiles = []
                    self._spotlight_restore_snapshot_seeded = False
                elif self.spotlight_index > removed_idx:
                    self.spotlight_index -= 1
                    self._spotlight_restore_playing_tiles = [
                        t for t in self._spotlight_restore_playing_tiles
                        if t is not tile
                    ]
                else:
                    self._spotlight_restore_playing_tiles = [
                        t for t in self._spotlight_restore_playing_tiles
                        if t is not tile
                    ]
            self.tiles.remove(tile)
            try:
                tile.shutdown()
            except Exception:
                logger.warning("tile shutdown failed during remove; falling back to stop()", exc_info=True)
                tile.stop()
            tile.setParent(None)
            tile.deleteLater() # 메모리 정리
            if detached_window is not None:
                detached_window.hide()
                detached_window.deleteLater()

            if self.tiles and playlist_to_move:
                for i, path in enumerate(playlist_to_move):
                    t = self.tiles[i % len(self.tiles)]
                    t.add_to_playlist(path)
                    t.set_external_subtitle_for_path(path, subtitle_map_to_move.get(path), overwrite=False)
            self.relayout()
            mw = self.window()
            if leaving_spotlight and mw is not None and hasattr(mw, "_is_compact_mode"):
                try:
                    if not mw._is_compact_mode():
                        for t in self.tiles:
                            t.show_controls(True)
                except RuntimeError:
                    logger.debug("spotlight control visibility restore skipped", exc_info=True)
            if resume_tiles:
                QtCore.QTimer.singleShot(0, lambda tiles=resume_tiles: self._restore_spotlight_tiles(tiles))
            self._notify_playlist_changed()

    def resizeEvent(self, e: QtGui.QResizeEvent):
        super().resizeEvent(e)
        self.relayout()

    def _set_tile_visible_if_needed(self, tile: VideoTile, visible: bool) -> bool:
        try:
            currently_hidden = tile.isHidden()
        except RuntimeError:
            logger.debug("tile hidden-state probe failed", exc_info=True)
            currently_hidden = not tile.isVisible()
        if visible:
            if currently_hidden:
                tile.show()
                return True
            return False
        if not currently_hidden:
            tile.hide()
            return True
        return False

    def _set_tile_geometry_if_needed(self, tile: VideoTile, rect: QtCore.QRect) -> bool:
        try:
            if tile.geometry() == rect:
                return False
        except RuntimeError:
            logger.debug("tile geometry comparison failed", exc_info=True)
        tile.setGeometry(rect)
        return True

    def relayout(self):
        if self._closing_for_app_exit:
            self._set_roller_running(False)
            self._sync_opacity_mode_owners()
            return
        W, H = self.width(), self.height()
        docked_tiles = self.docked_tiles()
        n = len(docked_tiles)
        if n == 0:
            self._set_roller_running(False)
            self._sync_opacity_mode_owners()
            return

        spotlighted_tile = None
        if self.spotlight_index is not None and 0 <= self.spotlight_index < len(self.tiles):
            candidate = self.tiles[self.spotlight_index]
            if candidate in docked_tiles:
                spotlighted_tile = candidate
            else:
                resume_tiles = [t for t in self._spotlight_restore_playing_tiles if t in self.tiles]
                self.spotlight_index = None
                self._spotlight_restore_playing_tiles = []
                self._spotlight_restore_snapshot_seeded = False
                if resume_tiles:
                    QtCore.QTimer.singleShot(0, lambda tiles=resume_tiles: self._restore_spotlight_tiles(tiles))

        if spotlighted_tile is not None:
            self._set_roller_running(False)
            # 스포트라이트 모드
            for t in docked_tiles:
                if t is spotlighted_tile:
                    rect = QtCore.QRect(0, 0, W, H)
                    geom_changed = self._set_tile_geometry_if_needed(t, rect)
                    vis_changed = self._set_tile_visible_if_needed(t, True)
                    if geom_changed or vis_changed:
                        t.bind_hwnd()
                else:
                    self._set_tile_visible_if_needed(t, False)
            self._sync_opacity_mode_owners()
            return

        if self._apply_roller_layout(docked_tiles, W, H):
            self._sync_opacity_mode_owners()
            return
        if self._apply_balanced_auto_layout(docked_tiles, W, H):
            self._set_roller_running(False)
            self._sync_opacity_mode_owners()
            return

        cols, rows = self._grid_dimensions_for_count(n)
        self._set_roller_running(False)
        w = W // cols if cols > 0 else W
        h = H // rows if rows > 0 else H

        for idx, t in enumerate(docked_tiles):
            r = idx // cols
            c = idx % cols
            x, y = c * w, r * h
            rect = QtCore.QRect(x, y, w, h)
            geom_changed = self._set_tile_geometry_if_needed(t, rect)
            vis_changed = self._set_tile_visible_if_needed(t, True)
            if geom_changed or vis_changed:
                t.bind_hwnd()
        self._sync_opacity_mode_owners()

    def play_all(self):
        for t in self.tiles:
            if t.playlist and t.mediaplayer.get_media() is None:
                if not t.set_media(t.playlist[0]):
                    continue
                t.current_index = 0
            t.play()

    def activate_roller_after_source_change(self):
        if self._roller_mode() is None:
            self.play_all()
            return
        docked_tiles = list(self.docked_tiles())
        if not docked_tiles:
            return
        for tile in docked_tiles:
            playlist = [str(path or "").strip() for path in list(getattr(tile, "playlist", []) or [])]
            if not playlist:
                continue
            try:
                current_index = int(getattr(tile, "current_index", -1))
            except (TypeError, ValueError):
                current_index = -1
            if not (0 <= current_index < len(playlist)):
                current_index = 0
                tile.current_index = 0
            try:
                player = getattr(tile, "mediaplayer", None)
                if player is None:
                    continue
                if player.get_media() is None:
                    if not tile.set_media(playlist[current_index], show_error_dialog=False):
                        continue
                tile._apply_current_playlist_start_position()
            except Exception:
                logger.debug("roller source-change activation failed for tile", exc_info=True)
        self._roller_playback_active = True
        self._roller_last_visible_tiles = set()
        viewport_rect = QtCore.QRect(0, 0, self.width(), self.height())
        self._sync_roller_playback(docked_tiles, viewport_rect)
        self._set_roller_running(not self.roller_paused() and self._roller_has_media(docked_tiles))


    def stop_all(self):
        for t in self.tiles:
            t.stop()

    def toggle_play_controlled(self):
        targets = self.get_controlled_tiles(require_selection=False)
        if not targets:
            return

        is_any_playing = any(t.mediaplayer.is_playing() for t in targets)
        for t in targets:
            if is_any_playing:
                t.pause()
            else:
                if t.mediaplayer.get_media() is None and t.playlist:
                    if not t.set_media(t.playlist[0]):
                        continue
                    t.current_index = 0
                t.play()

    def set_master_volume(self, value: int):
        value = max(0, min(100, int(round(value / 5) * 5)))
        mw = self.window()
        if mw:
            mw.master_volume = value
            mw.master_muted = (value == 0)
        for t in self.tiles:
            t._apply_tile_volume()

    def set_spotlight(self, index: Optional[int]):
        if index is not None and self.detached_windows and not self._keep_detached_tiles_for_focus_modes():
            self.redock_all_detached()
        if index is not None:
            if not (0 <= index < len(self.tiles)):
                return
            if self.is_detached(self.tiles[index]):
                logger.debug("spotlight request ignored for detached tile: %s", index)
                return
        resume_tiles: List[VideoTile] = []
        previous_index = self.spotlight_index
        self.spotlight_index = index
        if index is not None and 0 <= index < len(self.tiles):
            if previous_index is None:
                if not self._spotlight_restore_snapshot_seeded:
                    self._spotlight_restore_playing_tiles = [
                        t for t in self.tiles
                        if self._tile_is_playing(t)
                    ]
                self._spotlight_restore_snapshot_seeded = False
            for i, t in enumerate(self.tiles):
                if i != index and self._tile_is_playing(t):
                    t.pause()
        else:
            resume_tiles = [t for t in self._spotlight_restore_playing_tiles if t in self.tiles]
            self._spotlight_restore_playing_tiles = []
            self._spotlight_restore_snapshot_seeded = False
        self.relayout()

        mw = self.window()

        if index is None:
            is_fullscreen = False
            try:
                is_fullscreen = bool(mw is not None and hasattr(mw, "_is_fullscreen") and mw._is_fullscreen())
            except RuntimeError:
                logger.debug("main window fullscreen-state probe failed while clearing spotlight", exc_info=True)
                is_fullscreen = False
            if (not is_fullscreen) and hasattr(mw, "_is_compact_mode") and not mw._is_compact_mode():
                for t in self.tiles:
                    t.show_controls(True)
            if resume_tiles:
                QtCore.QTimer.singleShot(0, lambda tiles=resume_tiles: self._restore_spotlight_tiles(tiles))
            if is_fullscreen and mw is not None and hasattr(mw, "_schedule_fullscreen_hover_refresh_from_cursor"):
                try:
                    mw._schedule_fullscreen_hover_refresh_from_cursor()
                except RuntimeError:
                    logger.debug("fullscreen hover refresh schedule skipped after spotlight clear", exc_info=True)
        else:
            if mw is not None and hasattr(mw, "_schedule_fullscreen_hover_refresh_from_cursor"):
                try:
                    mw._schedule_fullscreen_hover_refresh_from_cursor()
                except RuntimeError:
                    logger.debug("fullscreen hover refresh schedule skipped after spotlight set", exc_info=True)

    def _tile_is_playing(self, tile: VideoTile) -> bool:
        player = getattr(tile, "mediaplayer", None)
        if player is None:
            return False
        try:
            return bool(player.is_playing())
        except Exception:
            logger.debug("spotlight play-state probe failed", exc_info=True)
            return False

    def _tile_has_loaded_media(self, tile: VideoTile) -> bool:
        player = getattr(tile, "mediaplayer", None)
        if player is None:
            return False
        try:
            return player.get_media() is not None
        except Exception:
            logger.debug("tile media probe failed", exc_info=True)
            return False

    def on_tile_playback_intent_changed(self, tile: VideoTile, playing: bool):
        if self._roller_mode() is None or tile not in self.docked_tiles():
            return
        if bool(playing):
            self._roller_playback_active = True
            return
        viewport_rect = QtCore.QRect(0, 0, self.width(), self.height())
        visible_tiles = {
            candidate
            for candidate in self.docked_tiles()
            if candidate is not None and candidate.geometry().intersects(viewport_rect)
        }
        if tile not in visible_tiles:
            return
        if any(candidate is not tile and self._tile_is_playing(candidate) for candidate in visible_tiles):
            self._roller_playback_active = True
            return
        self._roller_playback_active = False

    def _restore_spotlight_tiles(self, tiles: List[VideoTile]):
        restore_set = {t for t in tiles if t in self.tiles}
        for t in list(self.tiles):
            should_play = t in restore_set
            if t not in self.tiles:
                continue
            try:
                if should_play:
                    t.bind_hwnd()
                    self._invoke_tile_playback(t, "play")
                elif self._tile_is_playing(t):
                    self._invoke_tile_playback(t, "pause")
            except RuntimeError:
                logger.warning("spotlight playback restore failed for tile", exc_info=True)

    def _sync_roller_playback(self, docked_tiles: List[VideoTile], viewport_rect: QtCore.QRect):
        visible_tiles = {
            tile
            for tile in docked_tiles
            if tile is not None and tile.geometry().intersects(viewport_rect)
        }
        if any(self._tile_is_playing(tile) for tile in visible_tiles):
            self._roller_playback_active = True
        newly_visible_tiles = visible_tiles - self._roller_last_visible_tiles
        for tile in list(docked_tiles):
            if tile not in self.tiles:
                continue
            has_playlist = bool(getattr(tile, "playlist", None))
            should_keep_active = self._roller_playback_active and tile in visible_tiles
            try:
                if should_keep_active:
                    if not self._tile_has_loaded_media(tile) and has_playlist:
                        current_index = int(getattr(tile, "current_index", -1))
                        if not (0 <= current_index < len(tile.playlist)):
                            current_index = 0
                            tile.current_index = 0
                        if not tile.set_media(tile.playlist[current_index]):
                            continue
                    if tile in newly_visible_tiles and not self._tile_is_playing(tile):
                        self._invoke_tile_playback(tile, "play")
                elif self._tile_is_playing(tile):
                    self._invoke_tile_playback(tile, "pause")
            except Exception:
                logger.warning("roller playback sync failed for tile", exc_info=True)
        self._roller_last_visible_tiles = visible_tiles

    def _restore_roller_tiles(self, tiles: List[VideoTile]):
        restore_set = {t for t in tiles if t in self.tiles}
        for tile in list(self.tiles):
            if tile not in self.tiles:
                continue
            should_play = tile in restore_set
            try:
                if should_play:
                    if not self._tile_has_loaded_media(tile) and getattr(tile, "playlist", None):
                        current_index = int(getattr(tile, "current_index", -1))
                        if not (0 <= current_index < len(tile.playlist)):
                            current_index = 0
                            tile.current_index = 0
                        if not tile.set_media(tile.playlist[current_index]):
                            continue
                    if not self._tile_is_playing(tile):
                        self._invoke_tile_playback(tile, "play")
                elif self._tile_is_playing(tile):
                    self._invoke_tile_playback(tile, "pause")
            except Exception:
                logger.warning("roller playback restore failed for tile", exc_info=True)

    def _on_tile_double_clicked(self, tile: VideoTile):
        if self.is_detached(tile):
            if self._keep_detached_tiles_for_focus_modes():
                return
            self.redock_all_detached()
        try:
            idx = self.tiles.index(tile)
        except ValueError:
            return

        if self.spotlight_index == idx:
            self.set_spotlight(None)
        else:
            self.set_spotlight(idx)
            target = self.tiles[idx]
            if target.playlist:
                target.play()
        mw = self.window()
        if mw is not None and hasattr(mw, "_restore_window_focus"):
            try:
                mw._restore_window_focus()
            except RuntimeError:
                logger.debug("main window focus restore skipped after tile double click", exc_info=True)

    def set_borders_visible(self, visible: bool):
        for t in self.tiles:
            t.set_border_visible(visible)

    def set_compact_mode(self, enabled: bool):
        for t in self.tiles:
            t.set_compact_mode(enabled)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        # 이 이벤트 핸들러는 MainWin의 eventFilter로 대체되었으므로,
        # 혼선을 막기 위해 비워두거나 super()만 호출하는 것이 안전합니다.
        super().mousePressEvent(event)
