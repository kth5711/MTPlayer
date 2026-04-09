from typing import List

from PyQt6 import QtWidgets, QtCore

from app_shell.dock_chrome import style_aux_dock_tree


_CACHE_HISTORY_TABS = [
    ("scene", "씬변화"),
    ("refilter", "유사씬"),
    ("siglip_feature", "영상캐시"),
]


def sampling_mode_value(mode: str) -> str:
    text = str(mode or "").strip().lower()
    if text == "adaptive_window":
        return "scene_window"
    return text or "start_frame"


def sampling_mode_label(mode: str) -> str:
    value = sampling_mode_value(mode)
    if value == "scene_window":
        return "구간 샘플링"
    if value == "start_frame":
        return "패스트(씬시작 1샷)"
    return value or "-"


def cache_history_active_tree(dialog):
    tabs = getattr(dialog, "_cache_hist_tabs", None)
    trees = getattr(dialog, "_cache_hist_trees", None)
    if tabs is not None and isinstance(trees, dict):
        return _active_tab_tree(tabs, trees)
    return getattr(dialog, "_cache_hist_tree", None)


def _active_tab_tree(tabs, trees):
    idx = _safe_index(tabs)
    if 0 <= idx < len(_CACHE_HISTORY_TABS):
        ent_type = _CACHE_HISTORY_TABS[idx][0]
        tw = trees.get(ent_type)
        if tw is not None:
            return tw
    return None


def _safe_index(tabs) -> int:
    try:
        return max(0, int(tabs.currentIndex()))
    except Exception:
        return 0


def cache_history_selected_entries(dialog) -> List[dict]:
    tw = cache_history_active_tree(dialog)
    if tw is None:
        return []
    out: List[dict] = []
    for item in tw.selectedItems():
        value = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(value, dict):
            out.append(value)
    return out


def make_cache_history_tree() -> QtWidgets.QTreeWidget:
    tw = QtWidgets.QTreeWidget()
    tw.setRootIsDecorated(False)
    tw.setUniformRowHeights(True)
    tw.setAlternatingRowColors(True)
    tw.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
    tw.setColumnCount(4)
    tw.setHeaderLabels(["영상", "상세", "결과수", "저장시각"])
    _configure_header(tw.header())
    tw.setColumnWidth(0, 240)
    tw.setColumnWidth(1, 390)
    tw.setColumnWidth(2, 64)
    tw.setColumnWidth(3, 160)
    style_aux_dock_tree(tw)
    return tw


def _configure_header(header) -> None:
    if header is None:
        return
    try:
        header.setStretchLastSection(False)
    except Exception:
        pass


def set_scene_control_tab(dialog, tab_index: int) -> None:
    tabs = getattr(dialog, "tabs_scene_controls", None)
    if tabs is None:
        return
    try:
        tabs.setCurrentIndex(max(0, min(int(tab_index), int(tabs.count()) - 1)))
    except Exception:
        pass


def set_combo_data(dialog, combo_name: str, value) -> None:
    combo = getattr(dialog, combo_name, None)
    if combo is None:
        return
    try:
        idx = combo.findData(value)
    except Exception:
        idx = -1
    if int(idx) >= 0:
        try:
            combo.setCurrentIndex(int(idx))
        except Exception:
            pass
