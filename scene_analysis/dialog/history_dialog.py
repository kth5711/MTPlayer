from PyQt6 import QtWidgets

from app_shell.dock_chrome import (
    make_aux_dock_top_bar,
    style_aux_dock_button,
    style_aux_dock_check,
    style_aux_dock_container,
    style_aux_dock_label,
    style_aux_dock_tabs,
)

from .history_actions import delete_selected_cache_history_entries, load_selected_cache_history_entry
from .history_refresh import refresh_cache_history_dialog
from .history_shared import _CACHE_HISTORY_TABS, make_cache_history_tree


def open_cache_history_dialog(dialog) -> None:
    if _reuse_cache_history_dialog(dialog):
        return
    dlg, chk_cur, chk_close_after_load, tabs, trees, lbl, btn_refresh, btn_load, btn_delete, btn_close = _build_cache_history_dialog(dialog)
    _store_cache_history_dialog_refs(dialog, dlg, chk_cur, chk_close_after_load, tabs, trees, lbl)
    _connect_cache_history_dialog(dialog, dlg, chk_cur, tabs, trees, btn_refresh, btn_load, btn_delete, btn_close)
    refresh_cache_history_dialog(dialog)
    dlg.show()


def _reuse_cache_history_dialog(dialog) -> bool:
    dlg = getattr(dialog, "_cache_hist_dialog", None)
    if dlg is None:
        return False
    try:
        _refresh_cache_history_dialog_chrome(dialog)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        refresh_cache_history_dialog(dialog)
        return True
    except Exception:
        cache_history_dialog_closed(dialog)
        return False


def _build_cache_history_dialog(dialog):
    dlg = QtWidgets.QDialog(dialog)
    dlg.setWindowTitle("결과기록")
    dlg.setModal(False)
    dlg.resize(900, 460)
    layout = QtWidgets.QVBoxLayout(dlg)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    container = QtWidgets.QWidget(dlg)
    style_aux_dock_container(container)
    layout.addWidget(container)
    content = QtWidgets.QVBoxLayout(container)
    content.setContentsMargins(8, 8, 8, 8)
    content.setSpacing(8)
    chk_cur, chk_close_after_load, btn_refresh, btn_load, btn_delete = _top_row(content)
    tabs, trees = _tabs_widget(dialog, content)
    lbl, btn_close = _bottom_row(content)
    return dlg, chk_cur, chk_close_after_load, tabs, trees, lbl, btn_refresh, btn_load, btn_delete, btn_close


def _top_row(layout):
    bar = make_aux_dock_top_bar()
    row = QtWidgets.QHBoxLayout(bar)
    row.setContentsMargins(8, 8, 8, 8)
    row.setSpacing(8)
    chk_cur = QtWidgets.QCheckBox("현재 영상만")
    chk_cur.setChecked(False)
    style_aux_dock_check(chk_cur)
    chk_close_after_load = QtWidgets.QCheckBox("로드 후 닫기")
    chk_close_after_load.setChecked(True)
    chk_close_after_load.setToolTip("결과기록을 로드하면 이 창을 자동으로 닫습니다.")
    style_aux_dock_check(chk_close_after_load)
    btn_refresh = QtWidgets.QPushButton("새로고침")
    btn_load = QtWidgets.QPushButton("선택 로드")
    btn_delete = QtWidgets.QPushButton("선택 삭제")
    for button in (btn_refresh, btn_load, btn_delete):
        button.setMinimumHeight(30)
        style_aux_dock_button(button)
    row.addWidget(chk_cur)
    row.addWidget(chk_close_after_load)
    row.addStretch(1)
    for button in (btn_refresh, btn_load, btn_delete):
        row.addWidget(button)
    layout.addWidget(bar)
    return chk_cur, chk_close_after_load, btn_refresh, btn_load, btn_delete


def _tabs_widget(dialog, layout):
    tabs = QtWidgets.QTabWidget()
    style_aux_dock_tabs(tabs)
    trees = {}
    for ent_type, label in _CACHE_HISTORY_TABS:
        tree = make_cache_history_tree()
        tree.itemDoubleClicked.connect(lambda _it, _col, d=dialog: load_selected_cache_history_entry(d))
        trees[ent_type] = tree
        tabs.addTab(tree, label)
    layout.addWidget(tabs, 1)
    return tabs, trees


def _bottom_row(layout):
    bar = make_aux_dock_top_bar()
    row = QtWidgets.QHBoxLayout(bar)
    row.setContentsMargins(8, 8, 8, 8)
    row.setSpacing(8)
    lbl = QtWidgets.QLabel("")
    style_aux_dock_label(lbl)
    btn_close = QtWidgets.QPushButton("닫기")
    btn_close.setMinimumHeight(30)
    style_aux_dock_button(btn_close)
    row.addWidget(lbl)
    row.addStretch(1)
    row.addWidget(btn_close)
    layout.addWidget(bar)
    return lbl, btn_close


def _store_cache_history_dialog_refs(dialog, dlg, chk_cur, chk_close_after_load, tabs, trees, lbl):
    dialog._cache_hist_dialog = dlg
    dialog._cache_hist_tree = trees.get("scene")
    dialog._cache_hist_tabs = tabs
    dialog._cache_hist_trees = trees
    dialog._cache_hist_lbl = lbl
    dialog._cache_hist_chk_current = chk_cur
    dialog._cache_hist_chk_close_after_load = chk_close_after_load


def _connect_cache_history_dialog(dialog, dlg, chk_cur, tabs, trees, btn_refresh, btn_load, btn_delete, btn_close):
    chk_cur.stateChanged.connect(lambda _v: refresh_cache_history_dialog(dialog))
    btn_refresh.clicked.connect(lambda: refresh_cache_history_dialog(dialog))
    btn_load.clicked.connect(lambda: load_selected_cache_history_entry(dialog))
    btn_delete.clicked.connect(lambda: delete_selected_cache_history_entries(dialog))
    tabs.currentChanged.connect(lambda _idx: refresh_cache_history_dialog(dialog))
    btn_close.clicked.connect(dlg.close)
    dlg.finished.connect(lambda _r: cache_history_dialog_closed(dialog))


def _refresh_cache_history_dialog_chrome(dialog) -> None:
    dlg = getattr(dialog, "_cache_hist_dialog", None)
    if dlg is None:
        return
    container = dlg.findChild(QtWidgets.QWidget, "AuxDockContainer")
    if container is not None:
        style_aux_dock_container(container)


def cache_history_dialog_closed(dialog) -> None:
    dialog._cache_hist_loading = False
    dialog._cache_hist_pending_entry = None
    dialog._cache_hist_refresh_scheduled = False
    for attr in (
        "_cache_hist_dialog",
        "_cache_hist_tree",
        "_cache_hist_tabs",
        "_cache_hist_trees",
        "_cache_hist_lbl",
        "_cache_hist_chk_current",
        "_cache_hist_chk_close_after_load",
    ):
        setattr(dialog, attr, None)
