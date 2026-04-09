import logging
import re
from typing import Dict, List, Optional

from PyQt6 import QtCore, QtGui

from .shortcut_dialog import ShortcutDialog

logger = logging.getLogger(__name__)


def current_shortcuts_or_defaults(main) -> Dict[str, str]:
    return main._normalize_shortcut_mapping(main.config.get("shortcuts"))


def normalize_shortcut_mapping(main, mapping: Optional[Dict[str, str]]) -> Dict[str, str]:
    normalized = dict(ShortcutDialog.DEFAULTS)
    if isinstance(mapping, dict):
        for name, key in mapping.items():
            if name in normalized and isinstance(key, str):
                normalized[name] = key
        legacy_ab_key = mapping.get("구간 A~B 토글")
        if not isinstance(legacy_ab_key, str):
            legacy_ab_key = mapping.get("구간 A 지정")
        if isinstance(legacy_ab_key, str) and legacy_ab_key.strip():
            normalized["구간 A~B 토글"] = legacy_ab_key.strip()
        legacy_repeat_key = mapping.get("반복 재생 토글")
        if not isinstance(legacy_repeat_key, str) or not legacy_repeat_key.strip():
            legacy_repeat_key = mapping.get("현재 영상 반복")
        if not isinstance(legacy_repeat_key, str) or not legacy_repeat_key.strip():
            legacy_repeat_key = mapping.get("플레이리스트 반복")
        if isinstance(legacy_repeat_key, str) and legacy_repeat_key.strip():
            normalized["반복 재생 토글"] = legacy_repeat_key.strip()
    return normalized


def set_action_shortcut(main, action: Optional[QtGui.QAction], key_str: str):
    if action is None:
        return
    try:
        seq = QtGui.QKeySequence(key_str) if key_str else QtGui.QKeySequence()
        action.setShortcut(seq)
        action.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
    except (TypeError, RuntimeError):
        logger.warning("action shortcut binding failed: %s", key_str, exc_info=True)


def rebuild_seek_hotkeys(main, mapping: Dict[str, str]):
    main.seek_hotkey_steps = {}
    for name, step in (
        ("10초 앞으로", 10),
        ("10초 뒤로", -10),
        ("1초 앞으로", 1),
        ("1초 뒤로", -1),
    ):
        token = main._normalize_shortcut_token(mapping.get(name, ""))
        if not token:
            continue
        prev = main.seek_hotkey_steps.get(token)
        if prev is not None and prev != step:
            logger.warning("seek hotkey conflict ignored: %s -> %s (existing %s)", token, step, prev)
            continue
        main.seek_hotkey_steps[token] = step


def _clear_dynamic_shortcuts(main) -> None:
    for shortcut in main.dynamic_shortcuts:
        shortcut.setParent(None)
    main.dynamic_shortcuts.clear()


def _bind_dynamic_shortcut(main, key_str: str, func) -> None:
    if not key_str:
        return
    try:
        seq = QtGui.QKeySequence(key_str)
        shortcut = QtGui.QShortcut(seq, main)
        shortcut.setContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        shortcut.activated.connect(func)
        main.dynamic_shortcuts.append(shortcut)
    except (TypeError, RuntimeError):
        logger.warning("shortcut binding failed: %s", key_str, exc_info=True)


def _queued_tile_invoker(method_name: str):
    return lambda tile: QtCore.QMetaObject.invokeMethod(
        tile, method_name, QtCore.Qt.ConnectionType.QueuedConnection
    )


def _bind_control_shortcuts(main, mapping: Dict[str, str]) -> None:
    bind = lambda key_str, func: _bind_dynamic_shortcut(main, key_str, func)
    bind(mapping.get("재생/일시정지"), lambda: main.canvas.toggle_play_controlled())
    bind(
        mapping.get("다음 영상"),
        lambda: main.canvas.apply_to_controlled_tiles(_queued_tile_invoker("play_next")),
    )
    bind(
        mapping.get("이전 영상"),
        lambda: main.canvas.apply_to_controlled_tiles(_queued_tile_invoker("play_previous")),
    )
    bind(
        mapping.get("구간 A~B 토글"),
        lambda: main.canvas.apply_to_controlled_tiles(lambda tile: tile.cycle_ab_loop(), require_selection=False),
    )
    bind(mapping.get("반복 재생 토글"), main._cycle_repeat_mode_all_or_selected)
    bind(mapping.get("영상 출력 비율 토글"), main._cycle_display_mode_all_or_selected)
    bind(
        mapping.get("클립 생성"),
        lambda: main.canvas.apply_to_controlled_tiles(lambda tile: tile.export_clip(), require_selection=True),
    )
    bind(
        mapping.get("GIF 생성"),
        lambda: main.canvas.apply_to_controlled_tiles(lambda tile: tile.export_gif(), require_selection=True),
    )
    bind(mapping.get("볼륨 증가"), lambda: main._vol_step(1))
    bind(mapping.get("볼륨 감소"), lambda: main._vol_step(-1))
    bind(mapping.get("음소거"), main._toggle_mute)
    bind(mapping.get("선택 타일 음소거"), main._toggle_tile_mute_selected)
    bind(mapping.get("타일 전체선택/해제"), main._toggle_select_all_tiles)
    bind(
        mapping.get("배속 증가"),
        lambda: main.canvas.apply_to_controlled_tiles(lambda tile: tile.adjust_rate(+0.1), require_selection=False),
    )
    bind(
        mapping.get("배속 감소"),
        lambda: main.canvas.apply_to_controlled_tiles(lambda tile: tile.adjust_rate(-0.1), require_selection=False),
    )


def _bind_action_shortcuts(main, mapping: Dict[str, str]) -> None:
    main._set_action_shortcut(getattr(main, "act_open", None), mapping.get("영상 열기", ""))
    main._set_action_shortcut(getattr(main, "act_open_multi", None), mapping.get("영상 새 타일로 열기", ""))
    main._set_action_shortcut(getattr(main, "act_open_folder", None), mapping.get("폴더 열기", ""))
    main._set_action_shortcut(
        getattr(main, "act_toggle_playlist_dock", None),
        mapping.get("플레이리스트 창 토글", ""),
    )
    main._set_action_shortcut(
        getattr(main, "act_toggle_bookmark_dock", None),
        mapping.get("책갈피 창 토글", ""),
    )
    main._set_action_shortcut(getattr(main, "compact_action", None), mapping.get("영상만 보기", ""))


def rebind_shortcuts(main, mapping: Optional[Dict[str, str]]):
    _clear_dynamic_shortcuts(main)
    normalized = main._normalize_shortcut_mapping(mapping)
    _bind_control_shortcuts(main, normalized)
    _bind_action_shortcuts(main, normalized)
    main._rebuild_seek_hotkeys(normalized)
    main._rebuild_tile_hotkeys(normalized)
    main.config["shortcuts"] = normalized


def should_bypass_global_key_handling(main) -> bool:
    return main._focused_text_input_widget() is not None


def normalize_shortcut_token(main, raw: str) -> str:
    if not raw:
        return ""
    text = raw.strip().replace(" ", "")
    if not text:
        return ""
    text = re.sub(r"(?i)numpad", "Num", text)
    text = re.sub(r"(?i)keypad", "Num", text)
    text = re.sub(r"(?i)Num\+([0-9])", r"Num\1", text)

    mods: List[str] = []
    key_name = ""
    for part in [piece for piece in text.split("+") if piece]:
        low = part.lower()
        if low in {"ctrl", "control"}:
            if "Ctrl" not in mods:
                mods.append("Ctrl")
        elif low == "shift":
            if "Shift" not in mods:
                mods.append("Shift")
        elif low == "alt":
            if "Alt" not in mods:
                mods.append("Alt")
        elif low in {"meta", "win", "windows", "cmd", "command"}:
            if "Meta" not in mods:
                mods.append("Meta")
        elif re.fullmatch(r"num[0-9]", part, flags=re.IGNORECASE):
            key_name = f"Num{part[-1]}"
        elif len(part) == 1 and part.isdigit():
            key_name = part
        else:
            key_name = part

    ordered_mods = [name for name in ["Ctrl", "Shift", "Alt", "Meta"] if name in mods]
    return "+".join(ordered_mods + ([key_name] if key_name else []))


def event_to_shortcut_token(main, event: QtGui.QKeyEvent) -> str:
    mods = event.modifiers()
    mod_parts: List[str] = []
    if mods & QtCore.Qt.KeyboardModifier.ControlModifier:
        mod_parts.append("Ctrl")
    if mods & QtCore.Qt.KeyboardModifier.ShiftModifier:
        mod_parts.append("Shift")
    if mods & QtCore.Qt.KeyboardModifier.AltModifier:
        mod_parts.append("Alt")
    if mods & QtCore.Qt.KeyboardModifier.MetaModifier:
        mod_parts.append("Meta")

    key = event.key()
    if key in (
        QtCore.Qt.Key.Key_Control,
        QtCore.Qt.Key.Key_Shift,
        QtCore.Qt.Key.Key_Alt,
        QtCore.Qt.Key.Key_Meta,
    ):
        return main._normalize_shortcut_token("+".join(mod_parts))

    is_keypad = bool(mods & QtCore.Qt.KeyboardModifier.KeypadModifier)
    kmin = int(QtCore.Qt.Key.Key_0)
    kmax = int(QtCore.Qt.Key.Key_9)
    ikey = int(key)
    if kmin <= ikey <= kmax:
        digit = str(ikey - kmin)
        key_name = f"Num{digit}" if is_keypad else digit
    else:
        key_name = QtGui.QKeySequence(key).toString()
        if is_keypad and len(key_name) == 1 and key_name.isdigit():
            key_name = f"Num{key_name}"
    combo = "+".join(mod_parts + ([key_name] if key_name else []))
    return main._normalize_shortcut_token(combo)


def register_tile_hotkey(main, key_str: str, action: tuple[str, int]):
    token = main._normalize_shortcut_token(key_str)
    if not token:
        return
    prev = main.tile_hotkey_actions.get(token)
    if prev is not None and prev != action:
        logger.warning("tile hotkey conflict ignored: %s -> %s (existing %s)", token, action, prev)
        return
    main.tile_hotkey_actions[token] = action


def rebuild_tile_hotkeys(main, mapping: Dict[str, str]):
    main.tile_hotkey_actions = {}
    for index in range(1, 10):
        main._register_tile_hotkey(mapping.get(f"화면 전환 {index}", ""), ("spotlight", index))
        main._register_tile_hotkey(mapping.get(f"화면 선택 {index}", ""), ("select_single", index))
        main._register_tile_hotkey(mapping.get(f"화면 다중선택 {index}", ""), ("select_multi", index))


def hotkey_action_for_event(main, event: QtGui.QKeyEvent):
    token = main._event_to_shortcut_token(event)
    if not token:
        return None
    return main.tile_hotkey_actions.get(token)


def select_tile_by_index(main, n: int, multi: bool = False) -> bool:
    idx = n - 1
    tiles = getattr(main.canvas, "tiles", [])
    if idx < 0 or idx >= len(tiles):
        return False

    target = tiles[idx]
    if multi:
        selected_now = bool(getattr(target, "is_selected", False))
        normal_mode = getattr(target, "selection_mode", "off") == "normal"
        target.set_selection("off" if selected_now and normal_mode else "normal")
        main._last_sel_idx = None if (selected_now and normal_mode) else idx
        return True

    selected_tiles = [tile for tile in tiles if getattr(tile, "is_selected", False)]
    only_this_selected = (
        len(selected_tiles) == 1
        and selected_tiles[0] is target
        and getattr(target, "selection_mode", "off") == "normal"
    )
    if only_this_selected:
        target.set_selection("off")
        main._last_sel_idx = None
        return True
    for tile in tiles:
        tile.set_selection("normal" if tile is target else "off")
    main._last_sel_idx = idx
    return True


def apply_hotkey_action(main, action) -> bool:
    if not action:
        return False
    kind, n = action
    if kind == "spotlight":
        main._spotlight_hotkey(n)
        return True
    if kind == "select_single":
        return main._select_tile_by_index(n, multi=False)
    if kind == "select_multi":
        return main._select_tile_by_index(n, multi=True)
    return False


def seek_step_for_event(main, event: QtGui.QKeyEvent):
    token = main._event_to_shortcut_token(event)
    if not token:
        return None
    return main.seek_hotkey_steps.get(token)


def handle_seek_key_event(main, event: QtGui.QKeyEvent) -> bool:
    step = main._seek_step_for_event(event)
    if step is None:
        return False
    main.canvas.move_controlled_positions(step)
    return True


def handle_shortcut_override_event(main, event: QtGui.QKeyEvent) -> bool:
    try:
        if main._should_bypass_global_key_handling():
            return False
        if int(event.key()) == int(QtCore.Qt.Key.Key_Escape):
            main._handle_escape()
            return True
        if main._is_main_window_active():
            if main._seek_step_for_event(event) is not None:
                return True
            if main._hotkey_action_for_event(event) is not None:
                return True
    except RuntimeError:
        logger.warning("shortcut override handling failed", exc_info=True)
        return False
    return False
