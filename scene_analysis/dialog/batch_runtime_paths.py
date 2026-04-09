import os
from typing import List

from PyQt6 import QtWidgets, QtCore

from .batch_paths import _expand_batch_inputs, _norm_path


def _scene_batch_item(dialog, path: str):
    tw = getattr(dialog, "_scene_batch_tree", None)
    if tw is None:
        return None
    for row in range(tw.topLevelItemCount()):
        it = tw.topLevelItem(row)
        if _norm_path(str(it.data(0, QtCore.Qt.ItemDataRole.UserRole) or "")) == _norm_path(path):
            return it
    return None


def _scene_batch_start_dir(dialog) -> str:
    host = getattr(dialog, "host", None)
    getter = getattr(host, "_dialog_start_dir", None)
    if callable(getter):
        try:
            start_dir = str(getter() or "").strip()
            if start_dir:
                return start_dir
        except Exception:
            pass
    main = None
    main_getter = getattr(host, "_main_window", None)
    if callable(main_getter):
        try:
            main = main_getter()
        except Exception:
            main = None
    if main is not None:
        try:
            start_dir = str(getattr(main, "config", {}).get("last_dir", "") or "").strip()
            if start_dir:
                return start_dir
        except Exception:
            pass
    return os.path.expanduser("~")


def _remember_scene_batch_dir(dialog, path: str) -> None:
    target = str(path or "").strip()
    if not target:
        return
    host = getattr(dialog, "host", None)
    setter = getattr(host, "_remember_dialog_dir", None)
    if callable(setter):
        try:
            setter(target)
            return
        except Exception:
            pass
    main = None
    main_getter = getattr(host, "_main_window", None)
    if callable(main_getter):
        try:
            main = main_getter()
        except Exception:
            main = None
    if main is None:
        return
    try:
        main.config["last_dir"] = target
        if hasattr(main, "last_dir"):
            main.last_dir = target
    except Exception:
        pass


def _scene_batch_add_paths(dialog, raw_paths: List[str]) -> int:
    tw = getattr(dialog, "_scene_batch_tree", None)
    if tw is None:
        return 0
    files = _expand_batch_inputs(raw_paths)
    if not files:
        return 0
    existing = set()
    for row in range(tw.topLevelItemCount()):
        it = tw.topLevelItem(row)
        existing.add(_norm_path(str(it.data(0, QtCore.Qt.ItemDataRole.UserRole) or "")))
    added = 0
    for path in files:
        key = _norm_path(path)
        if key in existing:
            continue
        existing.add(key)
        it = QtWidgets.QTreeWidgetItem([
            "대기",
            os.path.basename(path) or path,
            path,
            "-",
        ])
        it.setData(0, QtCore.Qt.ItemDataRole.UserRole, path)
        it.setToolTip(1, path)
        it.setToolTip(2, path)
        tw.addTopLevelItem(it)
        added += 1
    return added
