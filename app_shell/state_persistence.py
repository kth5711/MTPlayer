import copy
import os
import time
from typing import Any, Dict, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from i18n import default_ui_language, normalize_ui_language, tr
from .interaction_ui_state import compat_ui_visibility_mode_from_payload
from .theme import DEFAULT_LIGHT_THEME_BRIGHTNESS, normalize_light_theme_brightness, normalize_ui_theme


def load_config_and_restore(main):
    main.config = main.session_manager.load()
    main.ui_language = normalize_ui_language(
        main.config.get("language", getattr(main, "ui_language", default_ui_language()))
    )
    main.ui_theme = normalize_ui_theme(main.config.get("theme", getattr(main, "ui_theme", "black")))
    main.light_theme_brightness = normalize_light_theme_brightness(
        main.config.get(
            "light_theme_brightness",
            getattr(main, "light_theme_brightness", DEFAULT_LIGHT_THEME_BRIGHTNESS),
        )
    )
    main.vlc_hw_decode_enabled = bool(main.config.get("vlc_hw_decode", False))
    main.last_dir = main.config.get("last_dir", "")
    main._apply_view_state(_restored_view_state(main))
    _restore_bookmarks_from_active_profile(main)
    main._restore_window_state(main.config.get("window_state"))
    if _restore_session_now(main):
        main._restore_session_payload(main.config.get("last_session"))
    else:
        while len(main.canvas.tiles) < main._default_tile_count():
            main.canvas.add_tile()
    main._prune_recent_profiles()
    main._prune_recent_media()
    main.update_playlist()
    if hasattr(main, "_apply_ui_theme"):
        main._apply_ui_theme(save=False, announce=False)
    if hasattr(main, "_apply_ui_language"):
        main._apply_ui_language()


def _restored_view_state(main) -> Dict[str, Any]:
    ui_visibility_mode = compat_ui_visibility_mode_from_payload(
        main.config,
        fallback=main.current_ui_visibility_mode(),
    )
    return {
        "master_volume": int(main.config.get("master_volume", 100)),
        "border_visible": bool(main.config.get("border_visible", True)),
        "ui_visibility_mode": ui_visibility_mode,
        "ui_auto_hide_ms": main.config.get("ui_auto_hide_ms", main.current_windowed_ui_auto_hide_ms()),
        "compact_mode": ui_visibility_mode == "hidden",
        "always_on_top": bool(main.config.get("always_on_top", False)),
        "layout_mode": main.config.get("layout_mode", main.canvas.layout_mode()),
        "roller_visible_count": main.config.get("roller_visible_count", main.canvas.roller_visible_count()),
        "roller_speed": main.config.get("roller_speed", main.canvas.roller_speed_px_per_sec()),
        "roller_direction": main.config.get("roller_direction", main.canvas.roller_direction()),
        "roller_paused": bool(main.config.get("roller_paused", False)),
        "overlay_global_apply_percent": main.config.get(
            "overlay_global_apply_percent",
            main.config.get("overlay_opacity_step_percent", main.canvas.overlay_global_apply_percent()),
        ),
        "keep_detached_focus_mode": bool(main.config.get("keep_detached_focus_mode", False)),
        "playlist_dock_visible": bool(main.config.get("playlist_dock_visible", False)),
        "bookmark_dock_visible": bool(main.config.get("bookmark_dock_visible", False)),
        "bookmark_marks_visible": bool(main.config.get("bookmark_marks_visible", True)),
        "playlist_sort_mode": main.config.get("playlist_sort_mode", "none"),
        "playlist_sort_descending": bool(main.config.get("playlist_sort_descending", False)),
    }


def _restore_session_now(main) -> bool:
    return bool(main.config.get("restore_last_session", False)) and _has_restorable_session_payload(
        main.config.get("last_session")
    )


def _has_restorable_session_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    entries = payload.get("tiles", [])
    if not isinstance(entries, list) or not entries:
        return False
    return any(isinstance(entry, dict) for entry in entries)


def _light_config_payload(main) -> Dict[str, Any]:
    return {
        "vlc_hw_decode": bool(getattr(main, "vlc_hw_decode_enabled", False)),
        "master_volume": int(main.sld_master.value()),
        "last_dir": main.config.get("last_dir", ""),
        "subtitle_asr_python": main.config.get("subtitle_asr_python", ""),
        "subtitle_asr_model": main.config.get("subtitle_asr_model", ""),
        "subtitle_translate_llama_bin": main.config.get("subtitle_translate_llama_bin", ""),
        "subtitle_translate_model_path": main.config.get("subtitle_translate_model_path", ""),
        "subtitle_translate_source_lang": main.config.get("subtitle_translate_source_lang", "auto"),
        "subtitle_translate_target_lang": main.config.get("subtitle_translate_target_lang", "ko"),
        "subtitle_translate_last_subtitle": main.config.get("subtitle_translate_last_subtitle", ""),
        "last_profile_dir": main.config.get("last_profile_dir", ""),
        "recent_profiles": main._recent_profile_paths(),
        "recent_media": main._recent_media_entries(),
        "sample_last_dir": main.config.get("sample_last_dir", ""),
        "shortcuts": main.config.get("shortcuts", main.current_shortcuts_or_defaults()),
        "restore_last_session": bool(main.config.get("restore_last_session", False)),
        "active_profile_path": _active_profile_path(main),
        "language": normalize_ui_language(
            getattr(main, "ui_language", main.config.get("language", default_ui_language()))
        ),
        "theme": normalize_ui_theme(getattr(main, "ui_theme", main.config.get("theme", "black"))),
        "light_theme_brightness": normalize_light_theme_brightness(
            getattr(
                main,
                "light_theme_brightness",
                main.config.get("light_theme_brightness", DEFAULT_LIGHT_THEME_BRIGHTNESS),
            )
        ),
        "border_visible": bool(main.border_action.isChecked()),
        "ui_visibility_mode": main.current_ui_visibility_mode(),
        "ui_auto_hide_ms": main.current_windowed_ui_auto_hide_ms(),
        "compact_mode": main.current_ui_visibility_mode() == "hidden",
        "always_on_top": main.always_on_top_action.isChecked(),
        "layout_mode": main.canvas.layout_mode(),
        "roller_visible_count": main.canvas.roller_visible_count(),
        "roller_speed": main.canvas.roller_speed_px_per_sec(),
        "roller_direction": main.canvas.roller_direction(),
        "roller_paused": main.canvas.roller_paused(),
        "overlay_global_apply_percent": main.canvas.overlay_global_apply_percent(),
        "keep_detached_focus_mode": bool(
            getattr(main, "keep_detached_focus_mode_action", None)
            and main.keep_detached_focus_mode_action.isChecked()
        ),
        "playlist_dock_visible": bool(getattr(getattr(main, "playlist_dock", None), "isVisible", lambda: False)()),
        "bookmark_dock_visible": bool(getattr(getattr(main, "bookmark_dock", None), "isVisible", lambda: False)()),
        "bookmark_marks_visible": bool(main.bookmark_marks_visible()),
        "playlist_sort_mode": main._playlist_sort_mode(),
        "playlist_sort_descending": main._playlist_sort_descending(),
        "window_state": main._window_state_payload(),
    }


def _include_session_for_save(main, auto: bool) -> bool:
    if not auto:
        return True
    tick = int(getattr(main, "_autosave_tick", 0)) + 1
    main._autosave_tick = tick
    return (tick % 4) == 0


def _build_saved_config(main, light_payload: Dict[str, Any], include_session: bool, auto: bool) -> Dict[str, Any]:
    data = dict(light_payload)
    if include_session:
        data["last_session"] = main._build_session_payload()
        main._last_full_session_save_at = time.monotonic()
        if auto:
            main._autosave_tick = 0
    else:
        data["last_session"] = main.config.get("last_session")
    return data


def save_config(main, *, auto: bool = False):
    try:
        light_payload = _light_config_payload(main)
        include_session = _include_session_for_save(main, auto)
        if auto and getattr(main, "_last_saved_light_payload", None) == light_payload and not include_session:
            return
        data = _build_saved_config(main, light_payload, include_session, auto)
        if data == getattr(main, "_last_saved_config_payload", None):
            main.config = data
            main._last_saved_light_payload = copy.deepcopy(light_payload)
            _sync_bookmarks_to_active_profile(main)
            return
        main.session_manager.save(data, pretty=not auto)
        main.config = data
        main._last_saved_light_payload = copy.deepcopy(light_payload)
        main._last_saved_config_payload = copy.deepcopy(data)
        _sync_bookmarks_to_active_profile(main)
    except Exception as exc:
        print("설정 저장 실패:", exc)


def save_profile(main):
    start_dir = main._profile_start_dir()
    path, _ = QtWidgets.QFileDialog.getSaveFileName(
        main,
        tr(main, "프로필 저장"),
        os.path.join(start_dir, "profile.mpprofile.json"),
        "Multi-Play Profile (*.mpprofile.json *.json)",
    )
    if not path:
        return
    if not path.lower().endswith((".mpprofile.json", ".json")):
        path = f"{path}.mpprofile.json"
    path = os.path.abspath(path)
    main._remember_profile_dir(path)
    main.config["active_profile_path"] = path
    main.session_manager.save(main._build_profile_payload(), path=path)
    main._push_recent_profile(path)
    main.save_config()
    main.statusBar().showMessage(tr(main, "프로필 저장: {path}", path=path), 3000)


def load_profile(main, path: Optional[str] = None):
    if not path:
        path = _choose_profile_path(main)
        if not path:
            return
    path = os.path.abspath(path)
    payload = main.session_manager.load(path=path)
    if not payload:
        _warn_profile(main, tr(main, "프로필 파일을 읽지 못했습니다."))
        main._prune_recent_profiles()
        return
    if payload.get("profile_type") not in (None, "multi_play_profile"):
        _warn_profile(main, tr(main, "지원하지 않는 프로필 형식입니다."))
        return
    try:
        main._apply_profile_payload(payload)
    except Exception as exc:
        _warn_profile(main, tr(main, "프로필 적용 실패:\n{error}", error=exc))
        return
    main._remember_profile_dir(path)
    main.config["active_profile_path"] = path
    main._push_recent_profile(path)
    main.save_config()
    main.statusBar().showMessage(tr(main, "프로필 불러오기: {path}", path=path), 3000)


def _choose_profile_path(main) -> Optional[str]:
    chosen = _choose_profile_path_from_dialog(main)
    if chosen == "__browse__":
        start_dir = main._profile_start_dir()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            main,
            tr(main, "프로필 불러오기"),
            start_dir,
            "Multi-Play Profile (*.mpprofile.json *.json)",
        )
        return path or None
    return chosen or None


def _warn_profile(main, message: str) -> None:
    QtWidgets.QMessageBox.warning(main, tr(main, "프로필 불러오기"), message)


def _default_profile_path(main) -> str:
    base_dir = os.path.dirname(str(getattr(main, "config_path", "") or "")) or os.path.expanduser("~")
    return os.path.abspath(os.path.join(base_dir, "default_profile.mpprofile.json"))


def _active_profile_path(main) -> str:
    default_path = _default_profile_path(main)
    raw = str(getattr(main, "config", {}).get("active_profile_path", "") or "").strip()
    if not raw:
        return default_path
    path = os.path.abspath(raw)
    if path != default_path and not os.path.exists(path):
        return default_path
    return path


def _minimal_profile_payload(main) -> Dict[str, Any]:
    return {
        "profile_type": "multi_play_profile",
        "version": 1,
        "language": normalize_ui_language(getattr(main, "ui_language", default_ui_language())),
        "bookmark_categories": [],
        "bookmarks": [],
    }


def _legacy_bookmark_payload_from_config(main) -> Dict[str, Any]:
    config = getattr(main, "config", {}) or {}
    categories = config.get("bookmark_categories", [])
    bookmarks = config.get("bookmarks", [])
    return {
        "bookmark_categories": categories if isinstance(categories, list) else [],
        "bookmarks": bookmarks if isinstance(bookmarks, list) else [],
    }


def _ensure_profile_exists(main, path: str) -> None:
    if os.path.exists(path):
        return
    payload = _minimal_profile_payload(main)
    if os.path.abspath(path) == _default_profile_path(main):
        payload.update(_legacy_bookmark_payload_from_config(main))
    main.session_manager.save(payload, path=path)


def _restore_bookmarks_from_active_profile(main) -> None:
    configured = str(getattr(main, "config", {}).get("active_profile_path", "") or "").strip()
    path = _active_profile_path(main)
    if configured:
        configured_path = os.path.abspath(configured)
        if configured_path != path and not os.path.exists(configured_path):
            print(f"활성 프로필을 찾지 못해 기본 프로필로 전환: {configured_path}")
    main.config["active_profile_path"] = path
    _ensure_profile_exists(main, path)
    payload = main.session_manager.load(path=path)
    if payload.get("profile_type") not in (None, "multi_play_profile"):
        fallback = _default_profile_path(main)
        main.config["active_profile_path"] = fallback
        _ensure_profile_exists(main, fallback)
        payload = main.session_manager.load(path=fallback)
    if os.path.abspath(path) == _default_profile_path(main):
        legacy = _legacy_bookmark_payload_from_config(main)
        if legacy["bookmarks"] and not payload.get("bookmarks"):
            payload["bookmark_categories"] = legacy["bookmark_categories"]
            payload["bookmarks"] = legacy["bookmarks"]
            main.session_manager.save(payload, path=path)
    main._load_bookmark_categories(payload.get("bookmark_categories", []))
    main._load_bookmarks(payload.get("bookmarks", []))


def _sync_bookmarks_to_active_profile(main) -> None:
    path = _active_profile_path(main)
    main.config["active_profile_path"] = path
    payload = main.session_manager.load(path=path)
    if not isinstance(payload, dict) or payload.get("profile_type") not in (None, "multi_play_profile"):
        payload = _minimal_profile_payload(main)
    payload["profile_type"] = "multi_play_profile"
    payload["version"] = int(payload.get("version", 1) or 1)
    payload["language"] = normalize_ui_language(
        getattr(main, "ui_language", payload.get("language", default_ui_language()))
    )
    payload["bookmark_categories"] = main._bookmark_categories_payload()
    payload["bookmarks"] = main._bookmark_payload()
    main.session_manager.save(payload, path=path)


def _known_profile_paths(main) -> list[str]:
    active_path = _active_profile_path(main)
    default_path = _default_profile_path(main)
    paths: list[str] = []
    for candidate in (active_path, default_path, *list(getattr(main, "_recent_profile_paths", lambda: [])() or [])):
        text = str(candidate or "").strip()
        if not text:
            continue
        normalized = os.path.abspath(text)
        if normalized in paths:
            continue
        if os.path.exists(normalized) or normalized == default_path:
            paths.append(normalized)
    return paths


def _profile_display_name(main, path: str) -> str:
    normalized = os.path.abspath(path)
    return tr(main, "기본 프로필") if normalized == _default_profile_path(main) else (os.path.basename(path) or path)


def _choose_profile_path_from_dialog(main) -> Optional[str]:
    paths = _known_profile_paths(main)
    if not paths:
        return "__browse__"
    dlg = QtWidgets.QDialog(main)
    dlg.setWindowTitle(tr(main, "프로필 선택"))
    dlg.setModal(True)
    dlg.resize(520, 360)
    layout = QtWidgets.QVBoxLayout(dlg)
    list_widget = QtWidgets.QListWidget(dlg)
    list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
    active_path = _active_profile_path(main)
    for path in paths:
        item = QtWidgets.QListWidgetItem(_profile_display_name(main, path))
        item.setData(QtCore.Qt.ItemDataRole.UserRole, path)
        item.setToolTip(path)
        if os.path.abspath(path) == active_path:
            item.setBackground(QtGui.QColor("#111111"))
            item.setForeground(QtGui.QColor("#ffffff"))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
        list_widget.addItem(item)
    current_row = 0
    for idx in range(list_widget.count()):
        item = list_widget.item(idx)
        if str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "") == active_path:
            current_row = idx
            break
    list_widget.setCurrentRow(current_row)
    layout.addWidget(list_widget)
    buttons = QtWidgets.QDialogButtonBox(dlg)
    btn_open = buttons.addButton(tr(main, "프로필 불러오기"), QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
    btn_browse = buttons.addButton(tr(main, "찾아보기..."), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
    buttons.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    layout.addWidget(buttons)

    result = {"path": None}

    def accept_current():
        item = list_widget.currentItem()
        if item is None:
            return
        result["path"] = str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "").strip() or None
        dlg.accept()

    def browse_external():
        result["path"] = "__browse__"
        dlg.accept()

    btn_open.clicked.connect(accept_current)
    btn_browse.clicked.connect(browse_external)
    buttons.rejected.connect(dlg.reject)
    list_widget.itemDoubleClicked.connect(lambda _item: accept_current())

    if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None
    return result["path"]
