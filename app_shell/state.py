import os
from typing import Any, Dict, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from .interaction_ui_state import (
    UI_VISIBILITY_ALWAYS,
    UI_VISIBILITY_HIDDEN,
    compat_ui_visibility_mode_from_payload,
)
from .session import rect_from_data, rect_to_data
from i18n import default_ui_language, normalize_ui_language, tr
from .state_persistence import load_config_and_restore, load_profile, save_config, save_profile


def default_tile_count(main) -> int:
    return 4


def window_state_payload(main) -> Dict[str, Any]:
    try:
        geom = main.normalGeometry()
    except Exception:
        geom = main.geometry()
    if geom is None or geom.width() <= 0 or geom.height() <= 0:
        geom = main.geometry()
    return {
        "geometry": rect_to_data(geom),
        "maximized": bool(main.windowState() & QtCore.Qt.WindowState.WindowMaximized),
    }


def build_session_payload(main) -> Dict[str, Any]:
    return main.canvas.snapshot_state()


def _restore_last_session_enabled(main) -> bool:
    return bool(main.config.get("restore_last_session", False))


def _has_restorable_session_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    entries = payload.get("tiles", [])
    if not isinstance(entries, list) or not entries:
        return False
    return any(isinstance(entry, dict) for entry in entries)


def build_profile_payload(main) -> Dict[str, Any]:
    return {
        "profile_type": "multi_play_profile",
        "version": 1,
        "language": normalize_ui_language(getattr(main, "ui_language", default_ui_language())),
        "window_state": main._window_state_payload(),
        "view_state": {
            "master_volume": int(main.sld_master.value()),
            "border_visible": bool(main.border_action.isChecked()),
            "ui_visibility_mode": main.current_ui_visibility_mode(),
            "ui_auto_hide_ms": main.current_windowed_ui_auto_hide_ms(),
            "compact_mode": main.current_ui_visibility_mode() == UI_VISIBILITY_HIDDEN,
            "always_on_top": bool(main.always_on_top_action.isChecked()),
            "layout_mode": main.canvas.layout_mode(),
            "roller_visible_count": main.canvas.roller_visible_count(),
            "roller_speed": main.canvas.roller_speed_px_per_sec(),
            "roller_direction": main.canvas.roller_direction(),
            "roller_paused": main.canvas.roller_paused(),
            "overlay_global_apply_percent": main.canvas.overlay_global_apply_percent(),
            "keep_detached_focus_mode": bool(main.keep_detached_focus_mode_action.isChecked()),
            "playlist_dock_visible": bool(
                getattr(getattr(main, "playlist_dock", None), "isVisible", lambda: False)()
            ),
            "bookmark_dock_visible": bool(
                getattr(getattr(main, "bookmark_dock", None), "isVisible", lambda: False)()
            ),
            "bookmark_marks_visible": bool(main.bookmark_marks_visible()),
            "playlist_sort_mode": main._playlist_sort_mode(),
            "playlist_sort_descending": main._playlist_sort_descending(),
        },
        "session": main._build_session_payload(),
        "bookmark_categories": main._bookmark_categories_payload(),
        "bookmarks": main._bookmark_payload(),
    }


def profile_start_dir(main) -> str:
    return (
        main.config.get("last_profile_dir", "")
        or os.path.dirname(main.config_path)
        or os.path.expanduser("~")
    )


def remember_profile_dir(main, path: str):
    folder = path
    if os.path.splitext(path)[1]:
        folder = os.path.dirname(path)
    if folder:
        main.config["last_profile_dir"] = folder


def recent_profile_paths(main) -> list[str]:
    items = main.config.get("recent_profiles", [])
    if not isinstance(items, list):
        items = []
    out: list[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text:
            continue
        normalized = os.path.abspath(text)
        if normalized not in out:
            out.append(normalized)
    return out[:10]


def push_recent_profile(main, path: str):
    if not path:
        return
    normalized = os.path.abspath(path)
    items = [p for p in main._recent_profile_paths() if p != normalized]
    items.insert(0, normalized)
    main.config["recent_profiles"] = items[:10]
    main._refresh_recent_profiles_menu()


def _normalize_recent_media_entry(entry: Any) -> Optional[Dict[str, str]]:
    kind = "path"
    value = ""
    if isinstance(entry, dict):
        kind = str(entry.get("kind", "path") or "path").strip().lower()
        value = str(entry.get("value", "") or "").strip()
    elif isinstance(entry, str):
        value = str(entry or "").strip()
        try:
            qurl = QtCore.QUrl(value)
            if qurl.isValid() and qurl.scheme() and not qurl.isLocalFile():
                kind = "url"
        except Exception:
            kind = "path"
    if kind not in {"path", "url"}:
        kind = "path"
    if not value:
        return None
    if kind == "path":
        value = os.path.abspath(os.path.normpath(value))
    return {"kind": kind, "value": value}


def recent_media_entries(main) -> list[dict[str, str]]:
    items = main.config.get("recent_media", [])
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw in items:
        entry = _normalize_recent_media_entry(raw)
        if not entry:
            continue
        key = (entry["kind"], entry["value"])
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out[:20]


def push_recent_media(main, source: str, kind: str = "path"):
    push_recent_media_many(main, [source], kind=kind)


def push_recent_media_many(main, sources, kind: str = "path"):
    fresh: list[dict[str, str]] = []
    fresh_keys: set[tuple[str, str]] = set()
    for source in sources or []:
        entry = _normalize_recent_media_entry({"kind": kind, "value": source})
        if not entry:
            continue
        key = (entry["kind"], entry["value"])
        if key in fresh_keys:
            continue
        fresh_keys.add(key)
        fresh.append(entry)
    if not fresh:
        return
    items = [entry for entry in main._recent_media_entries() if (entry["kind"], entry["value"]) not in fresh_keys]
    main.config["recent_media"] = (fresh + items)[:20]
    main._refresh_recent_media_menu()


def _recent_media_menu_text(entry: Dict[str, str]) -> str:
    kind = str(entry.get("kind", "path") or "path")
    value = str(entry.get("value", "") or "")
    if kind == "url":
        try:
            qurl = QtCore.QUrl(value)
            host = qurl.host().strip()
            name = qurl.fileName().strip()
            return f"[URL] {name or host or value}"
        except Exception:
            return f"[URL] {value}"
    return os.path.basename(value) or value


def _elide_recent_media_menu_text(menu, label: str) -> str:
    text = str(label or "").strip()
    if not text:
        return ""
    try:
        fm = menu.fontMetrics()
        return fm.elidedText(text, QtCore.Qt.TextElideMode.ElideMiddle, 420)
    except Exception:
        if len(text) <= 48:
            return text
        return text[:28] + "..." + text[-17:]


def refresh_recent_media_menu(main):
    menu = getattr(main, "recent_media_menu", None)
    if menu is None:
        return
    menu.clear()
    entries = main._recent_media_entries()
    if not entries:
        action = menu.addAction(tr(main, "최근 미디어 없음"))
        action.setEnabled(False)
        return
    for entry in entries:
        label = _elide_recent_media_menu_text(menu, _recent_media_menu_text(entry))
        action = menu.addAction(label)
        action.setToolTip(str(entry.get("value", "")))
        action.triggered.connect(lambda _checked=False, e=dict(entry): main.open_recent_media(entry=e))
    menu.addSeparator()
    clear_action = menu.addAction(tr(main, "최근 미디어 비우기"))
    clear_action.triggered.connect(main.clear_recent_media_history)


def prune_recent_media(main):
    changed = False
    kept: list[dict[str, str]] = []
    for entry in main._recent_media_entries():
        kind = str(entry.get("kind", "path") or "path")
        value = str(entry.get("value", "") or "")
        if kind == "path" and not os.path.exists(value):
            changed = True
            continue
        kept.append(entry)
    if changed:
        main.config["recent_media"] = kept
    main._refresh_recent_media_menu()


def replace_recent_media_path(main, old_path: str, new_path: str) -> int:
    old_norm = os.path.abspath(os.path.normpath(str(old_path or "").strip()))
    new_norm = os.path.abspath(os.path.normpath(str(new_path or "").strip()))
    if not old_norm or not new_norm:
        return 0
    old_cmp = os.path.normcase(old_norm)
    changed = 0
    updated: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in main._recent_media_entries():
        item = dict(entry)
        if str(item.get("kind", "path") or "path") == "path":
            value = os.path.abspath(os.path.normpath(str(item.get("value", "") or "").strip()))
            if os.path.normcase(value) == old_cmp:
                item["value"] = new_norm
                changed += 1
        key = (str(item.get("kind", "path") or "path"), str(item.get("value", "") or ""))
        if key in seen:
            continue
        seen.add(key)
        updated.append(item)
    if changed <= 0:
        return 0
    main.config["recent_media"] = updated[:20]
    main._refresh_recent_media_menu()
    return changed


def refresh_recent_profiles_menu(main):
    menu = getattr(main, "recent_profiles_menu", None)
    if menu is None:
        return
    menu.clear()
    paths = main._recent_profile_paths()
    if not paths:
        action = menu.addAction(tr(main, "최근 프로필 없음"))
        action.setEnabled(False)
        return
    active_path = _active_profile_path(main)
    for path in paths:
        label = _profile_menu_label(main, path)
        action = menu.addAction(label)
        action.setToolTip(path)
        if os.path.abspath(path) == active_path:
            font = action.font()
            font.setBold(True)
            action.setFont(font)
        action.triggered.connect(lambda _checked=False, p=path: main.load_profile(path=p))
    menu.addSeparator()
    clear_action = menu.addAction(tr(main, "최근 프로필 비우기"))
    clear_action.triggered.connect(main.clear_recent_profiles_history)


def prune_recent_profiles(main):
    changed = False
    kept: list[str] = []
    for path in main._recent_profile_paths():
        if os.path.exists(path):
            kept.append(path)
        else:
            changed = True
    if changed:
        main.config["recent_profiles"] = kept
    main._refresh_recent_profiles_menu()


def _confirm_recent_history_clear(main, title: str, message: str) -> bool:
    return (
        QtWidgets.QMessageBox.question(
            main,
            title,
            message,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        == QtWidgets.QMessageBox.StandardButton.Yes
    )


def clear_recent_media_history(main):
    entries = list(main._recent_media_entries() or [])
    if not entries:
        QtWidgets.QMessageBox.information(main, tr(main, "최근 미디어"), tr(main, "최근 미디어가 비어 있습니다."))
        return False
    if not _confirm_recent_history_clear(
        main,
        tr(main, "최근 미디어 비우기"),
        tr(main, "최근 미디어 {count}개를 비우시겠습니까?", count=len(entries)),
    ):
        return False
    main.config["recent_media"] = []
    main._refresh_recent_media_menu()
    try:
        main.save_config()
    except Exception:
        pass
    try:
        main.statusBar().showMessage(tr(main, "최근 미디어 비우기: {count}개", count=len(entries)), 3000)
    except Exception:
        pass
    return True


def clear_recent_profiles_history(main):
    paths = list(main._recent_profile_paths() or [])
    if not paths:
        QtWidgets.QMessageBox.information(main, tr(main, "최근 프로필"), tr(main, "최근 프로필이 비어 있습니다."))
        return False
    if not _confirm_recent_history_clear(
        main,
        tr(main, "최근 프로필 비우기"),
        tr(main, "최근 프로필 {count}개를 비우시겠습니까?", count=len(paths)),
    ):
        return False
    main.config["recent_profiles"] = []
    main._refresh_recent_profiles_menu()
    try:
        main.save_config()
    except Exception:
        pass
    try:
        main.statusBar().showMessage(tr(main, "최근 프로필 비우기: {count}개", count=len(paths)), 3000)
    except Exception:
        pass
    return True


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


def _profile_menu_label(main, path: str) -> str:
    normalized = os.path.abspath(path)
    if normalized == _default_profile_path(main):
        return tr(main, "기본 프로필")
    return os.path.basename(path) or path


def restore_window_state(main, payload: Any):
    if not isinstance(payload, dict):
        return
    geom = rect_from_data(payload.get("geometry"))
    if geom is not None:
        main.setGeometry(geom)
        main.normal_geometry = QtCore.QRect(geom)
    state = main.windowState() & ~QtCore.Qt.WindowState.WindowMaximized
    if bool(payload.get("maximized", False)):
        state |= QtCore.Qt.WindowState.WindowMaximized
    main.setWindowState(state)


def apply_view_state(main, payload: Any):
    if not isinstance(payload, dict):
        return
    ui_visibility_mode = compat_ui_visibility_mode_from_payload(
        payload,
        fallback=main.current_ui_visibility_mode(),
    )
    if "master_volume" in payload:
        mv = int(payload.get("master_volume", 100))
        main.sld_master.setValue(mv)
        main.on_master_volume(mv)
    main.border_action.setChecked(bool(payload.get("border_visible", main.border_action.isChecked())))
    main.set_windowed_ui_auto_hide_ms(
        payload.get("ui_auto_hide_ms", main.current_windowed_ui_auto_hide_ms()),
        save=False,
        announce=False,
    )
    with QtCore.QSignalBlocker(main.compact_action):
        main.compact_action.setChecked(ui_visibility_mode != UI_VISIBILITY_ALWAYS)
    main.always_on_top_action.setChecked(
        bool(payload.get("always_on_top", main.always_on_top_action.isChecked()))
    )
    main.set_roller_reversed(
        str(payload.get("roller_direction", main.canvas.roller_direction()) or "").strip().lower() == "reverse"
    )
    main.set_roller_visible_count(payload.get("roller_visible_count", main.canvas.roller_visible_count()))
    main.set_roller_speed(payload.get("roller_speed", main.canvas.roller_speed_px_per_sec()))
    main.set_layout_mode(payload.get("layout_mode", main.canvas.layout_mode()))
    main.set_roller_paused(payload.get("roller_paused", main.canvas.roller_paused()))
    overlay_global_apply = payload.get(
        "overlay_global_apply_percent",
        payload.get("overlay_opacity_step_percent", main.canvas.overlay_global_apply_percent()),
    )
    main.canvas.set_overlay_global_apply_percent(overlay_global_apply)
    main.keep_detached_focus_mode_action.setChecked(
        bool(payload.get("keep_detached_focus_mode", main.keep_detached_focus_mode_action.isChecked()))
    )
    vis = bool(payload.get("playlist_dock_visible", getattr(main.playlist_dock, "isVisible", lambda: False)()))
    if hasattr(main, "playlist_dock"):
        main.playlist_dock.setVisible(vis)
    if hasattr(main, "act_toggle_playlist_dock"):
        main.act_toggle_playlist_dock.setChecked(vis)
    bookmark_vis = bool(
        payload.get("bookmark_dock_visible", getattr(getattr(main, "bookmark_dock", None), "isVisible", lambda: False)())
    )
    if hasattr(main, "bookmark_dock"):
        main.bookmark_dock.setVisible(bookmark_vis)
    if hasattr(main, "act_toggle_bookmark_dock"):
        main.act_toggle_bookmark_dock.setChecked(bookmark_vis)
    main.set_bookmark_marks_visible(bool(payload.get("bookmark_marks_visible", main.bookmark_marks_visible())))
    main._set_playlist_sort_controls(
        payload.get("playlist_sort_mode", main._playlist_sort_mode()),
        bool(payload.get("playlist_sort_descending", main._playlist_sort_descending())),
    )
    main.toggle_borders(main.border_action.isChecked())
    main.set_ui_visibility_mode(ui_visibility_mode, save=False, announce=False)
    main._apply_always_on_top(main.always_on_top_action.isChecked())


def reset_session_before_restore(main):
    if getattr(main.canvas, "spotlight_index", None) is not None:
        main.canvas.set_spotlight(None)
    main.canvas.redock_all_detached()


def restore_session_payload(main, payload: Any):
    main._reset_session_before_restore()
    if not isinstance(payload, dict):
        while len(main.canvas.tiles) < main._default_tile_count():
            main.canvas.add_tile()
        return

    entries = payload.get("tiles", [])
    if not isinstance(entries, list):
        entries = []
    spotlight_index = payload.get("spotlight_index", None)
    spotlight_restore_playing_indices = payload.get("spotlight_restore_playing_indices", [])
    virtual_roller_sources = payload.get("virtual_roller_sources", [])
    virtual_roller_scroll_index = payload.get("virtual_roller_scroll_index", 0)
    virtual_roller_saved_states = payload.get("virtual_roller_saved_states", [])
    if not isinstance(spotlight_restore_playing_indices, list):
        spotlight_restore_playing_indices = []
    restore_spotlight = (
        isinstance(spotlight_index, int)
        and 0 <= spotlight_index < len(entries)
        and not bool(
            isinstance(entries[spotlight_index], dict) and entries[spotlight_index].get("detached", False)
        )
    )

    while len(main.canvas.tiles) < len(entries):
        main.canvas.add_tile()
    while len(main.canvas.tiles) > len(entries):
        main.canvas.remove_tile(main.canvas.tiles[-1])

    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict) or not (0 <= idx < len(main.canvas.tiles)):
            continue
        state = dict(entry.get("state", {})) if isinstance(entry.get("state", {}), dict) else {}
        if restore_spotlight and idx != spotlight_index:
            state["playing"] = False
        if isinstance(state, dict):
            main.canvas.tiles[idx].from_state(state)

    main.canvas.restore_detached_state(entries)

    if restore_spotlight and isinstance(spotlight_index, int) and 0 <= spotlight_index < len(main.canvas.tiles):
        main.canvas._spotlight_restore_playing_tiles = [
            main.canvas.tiles[idx]
            for idx in spotlight_restore_playing_indices
            if isinstance(idx, int) and 0 <= idx < len(main.canvas.tiles)
        ]
        main.canvas._spotlight_restore_snapshot_seeded = True
        tile = main.canvas.tiles[spotlight_index]
        if not main.canvas.is_detached(tile):
            main.canvas.set_spotlight(spotlight_index)
    main.canvas.set_roller_visible_count(
        payload.get("roller_visible_count", main.canvas.roller_visible_count())
    )
    main.set_roller_speed(payload.get("roller_speed", main.canvas.roller_speed_px_per_sec()))
    main.set_roller_reversed(
        str(payload.get("roller_direction", main.canvas.roller_direction()) or "").strip().lower() == "reverse"
    )
    main.canvas.set_layout_mode(payload.get("layout_mode", main.canvas.layout_mode()))
    main.canvas.set_roller_paused(payload.get("roller_paused", main.canvas.roller_paused()))
    if main.canvas.infinite_roller_active():
        main.canvas.restore_infinite_roller_saved_states(virtual_roller_saved_states)
        main.canvas.restore_infinite_roller_sources(
            virtual_roller_sources,
            scroll_index=virtual_roller_scroll_index,
        )


def apply_profile_payload(main, payload: Any):
    if not isinstance(payload, dict):
        raise ValueError(tr(main, "프로필 형식이 아닙니다."))
    if "language" in payload and hasattr(main, "set_ui_language"):
        main.set_ui_language(payload.get("language"), save=False)
    main._apply_view_state(payload.get("view_state", {}))
    main._load_bookmark_categories(payload.get("bookmark_categories", []))
    main._load_bookmarks(payload.get("bookmarks", []))
    main._restore_window_state(payload.get("window_state"))
    main._restore_session_payload(payload.get("session"))
    main.update_playlist()


def close_event(main, event: QtGui.QCloseEvent):
    print("[종료] VLC 플레이어 정리 중...")
    try:
        main._clear_tile_drag_state()
    except Exception:
        pass
    try:
        worker = getattr(main, "_playlist_duration_worker", None)
        if worker is not None:
            worker.stop()
    except Exception:
        pass
    try:
        if hasattr(main, "auto_save_timer") and main.auto_save_timer is not None:
            main.auto_save_timer.stop()
    except Exception:
        pass

    try:
        if hasattr(main, "canvas") and main.canvas is not None:
            main.canvas.prepare_for_app_close()
    except Exception:
        pass

    try:
        main.save_config()
    except Exception:
        pass

    try:
        for tile in list(getattr(main.canvas, "tiles", [])):
            try:
                tile.shutdown()
            except Exception as ex:
                print("타일 종료 중 오류:", ex)
    except Exception as e2:
        print("Canvas 정리 중 오류:", e2)

    try:
        if hasattr(main, "vlc_instance") and main.vlc_instance is not None:
            try:
                main.vlc_instance.release()
            except Exception:
                pass
    except Exception as e3:
        print("VLC 인스턴스 해제 오류:", e3)

    try:
        if hasattr(main, "canvas") and main.canvas is not None:
            main.canvas.finalize_app_close()
    except Exception:
        pass

    print("[종료 완료] 모든 VLC 리소스 정리됨. 안전 종료.")
    event.accept()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        QtCore.QTimer.singleShot(0, app.quit)
    if not bool(getattr(main, "_force_exit_scheduled", False)):
        main._force_exit_scheduled = True
        QtCore.QTimer.singleShot(5000, lambda: os._exit(0))
