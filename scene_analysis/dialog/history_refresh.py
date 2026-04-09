from PyQt6 import QtWidgets, QtCore

from scene_analysis.core.cache import cache_history_entries

from .history_shared import _CACHE_HISTORY_TABS


def refresh_cache_history_dialog(dialog) -> None:
    ctx = _history_context(dialog)
    if ctx is None:
        return
    rows = cache_history_entries(ctx["cur_path"], current_only=ctx["cur_only"])
    buckets = _bucket_rows(rows)
    if ctx["tabs"] is not None and isinstance(ctx["trees"], dict):
        active_count = _refresh_tabbed_history(ctx["tabs"], ctx["trees"], buckets)
    else:
        active_count = _refresh_single_tree(ctx["tree"], rows)
    _update_history_label(ctx["label"], rows, active_count, ctx["cur_only"], ctx["cur_path"])


def _history_context(dialog):
    dlg = getattr(dialog, "_cache_hist_dialog", None)
    if dlg is None:
        return None
    chk = getattr(dialog, "_cache_hist_chk_current", None)
    return {
        "cur_only": bool(chk.isChecked()) if chk is not None else True,
        "cur_path": dialog._history_current_video_path(),
        "tabs": getattr(dialog, "_cache_hist_tabs", None),
        "trees": getattr(dialog, "_cache_hist_trees", None),
        "tree": getattr(dialog, "_cache_hist_tree", None),
        "label": getattr(dialog, "_cache_hist_lbl", None),
    }


def _bucket_rows(rows):
    buckets = {key: [] for key, _label in _CACHE_HISTORY_TABS}
    for entry in rows:
        ent_type = str(entry.get("type") or "")
        if ent_type in buckets:
            buckets[ent_type].append(entry)
    return buckets


def _refresh_tabbed_history(tabs, trees, buckets) -> int:
    for idx, (ent_type, label) in enumerate(_CACHE_HISTORY_TABS):
        _populate_history_tree(trees.get(ent_type), buckets.get(ent_type, []))
        try:
            tabs.setTabText(int(idx), f"{label} ({len(buckets.get(ent_type, []))})")
        except Exception:
            pass
    active_idx = _active_tab_index(tabs)
    active_type = _CACHE_HISTORY_TABS[active_idx][0] if active_idx < len(_CACHE_HISTORY_TABS) else "scene"
    return len(buckets.get(active_type, []))


def _refresh_single_tree(tree, rows) -> int:
    _populate_history_tree(tree, rows)
    return len(rows)


def _populate_history_tree(tree, rows) -> None:
    if tree is None:
        return
    tree.clear()
    for entry in rows:
        tree.addTopLevelItem(_history_item(entry))


def _history_item(entry):
    item = QtWidgets.QTreeWidgetItem([
        str(entry.get("video_name") or "(알 수 없음)"),
        str(entry.get("detail") or "-"),
        str(int(entry.get("count") or 0)),
        str(entry.get("saved_text") or "-"),
    ])
    item.setData(0, QtCore.Qt.ItemDataRole.UserRole, entry)
    item.setToolTip(0, str(entry.get("video_path") or ""))
    item.setToolTip(1, str(entry.get("file_name") or ""))
    return item


def _active_tab_index(tabs) -> int:
    try:
        return max(0, int(tabs.currentIndex()))
    except Exception:
        return 0


def _update_history_label(label, rows, active_count: int, cur_only: bool, cur_path: str) -> None:
    if label is None:
        return
    if cur_only and cur_path:
        label.setText(f"결과기록 총 {len(rows)}개 / 현재 탭 {active_count}개 (현재 영상)")
        return
    label.setText(f"결과기록 총 {len(rows)}개 / 현재 탭 {active_count}개")
