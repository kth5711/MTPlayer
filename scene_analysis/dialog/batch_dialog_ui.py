from PyQt6 import QtWidgets


def _create_scene_batch_dialog_widgets(dlg, option_text: str) -> dict:
    lay = QtWidgets.QVBoxLayout(dlg)
    lbl_opts = QtWidgets.QLabel(option_text)
    lbl_opts.setWordWrap(True)
    lay.addWidget(lbl_opts)

    chk_scene, chk_refilter = _add_scene_batch_mode_row(lay)
    top_buttons = _add_scene_batch_top_row(lay)
    tree = _create_scene_batch_tree(lay)
    _add_scene_batch_hint(lay)
    prog, prog_all = _add_scene_batch_progress_rows(lay)
    lbl_status, btn_close = _add_scene_batch_bottom_row(lay)

    return {
        "lbl_opts": lbl_opts,
        "chk_scene": chk_scene,
        "chk_refilter": chk_refilter,
        "btn_add_files": top_buttons["btn_add_files"],
        "btn_add_folder": top_buttons["btn_add_folder"],
        "btn_run": top_buttons["btn_run"],
        "btn_cancel": top_buttons["btn_cancel"],
        "btn_remove": top_buttons["btn_remove"],
        "btn_clear": top_buttons["btn_clear"],
        "tree": tree,
        "prog": prog,
        "prog_all": prog_all,
        "lbl_status": lbl_status,
        "btn_close": btn_close,
    }


def _add_scene_batch_mode_row(layout):
    row = QtWidgets.QHBoxLayout()
    chk_scene = QtWidgets.QCheckBox("씬변화")
    chk_scene.setChecked(True)
    chk_refilter = QtWidgets.QCheckBox("유사씬")
    chk_refilter.setChecked(False)
    row.addWidget(QtWidgets.QLabel("실행"))
    row.addWidget(chk_scene)
    row.addWidget(chk_refilter)
    row.addStretch(1)
    layout.addLayout(row)
    return chk_scene, chk_refilter


def _add_scene_batch_top_row(layout) -> dict:
    row = QtWidgets.QHBoxLayout()
    btn_add_files = QtWidgets.QPushButton("파일 추가")
    btn_add_folder = QtWidgets.QPushButton("폴더 추가")
    btn_run = QtWidgets.QPushButton("실행")
    btn_cancel = QtWidgets.QPushButton("취소")
    btn_cancel.setEnabled(False)
    btn_remove = QtWidgets.QPushButton("선택 제거")
    btn_clear = QtWidgets.QPushButton("전체 비우기")
    for btn in (btn_add_files, btn_add_folder, btn_run, btn_cancel):
        row.addWidget(btn)
    row.addStretch(1)
    row.addWidget(btn_remove)
    row.addWidget(btn_clear)
    layout.addLayout(row)
    return {
        "btn_add_files": btn_add_files,
        "btn_add_folder": btn_add_folder,
        "btn_run": btn_run,
        "btn_cancel": btn_cancel,
        "btn_remove": btn_remove,
        "btn_clear": btn_clear,
    }


def _create_scene_batch_tree(layout):
    tree = QtWidgets.QTreeWidget()
    tree.setRootIsDecorated(False)
    tree.setAlternatingRowColors(True)
    tree.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
    tree.setColumnCount(4)
    tree.setHeaderLabels(["상태", "파일", "경로", "결과수"])
    hdr = tree.header()
    if hdr is not None:
        try:
            hdr.setStretchLastSection(False)
        except Exception:
            pass
    tree.setColumnWidth(0, 120)
    tree.setColumnWidth(1, 220)
    tree.setColumnWidth(2, 420)
    tree.setColumnWidth(3, 70)
    layout.addWidget(tree, 1)
    return tree


def _add_scene_batch_hint(layout):
    layout.addWidget(QtWidgets.QLabel("현재 옵션으로 순차 처리하며, 썸네일/UI 목록은 만들지 않고 결과기록(JSON 캐시)만 저장합니다."))


def _add_scene_batch_progress_rows(layout):
    row_prog = QtWidgets.QHBoxLayout()
    row_prog.addWidget(QtWidgets.QLabel("현재 파일"))
    prog = QtWidgets.QProgressBar()
    prog.setRange(0, 100)
    row_prog.addWidget(prog, 1)
    layout.addLayout(row_prog)

    row_prog_all = QtWidgets.QHBoxLayout()
    row_prog_all.addWidget(QtWidgets.QLabel("전체 진행"))
    prog_all = QtWidgets.QProgressBar()
    prog_all.setRange(0, 100)
    row_prog_all.addWidget(prog_all, 1)
    layout.addLayout(row_prog_all)
    return prog, prog_all


def _add_scene_batch_bottom_row(layout):
    row_bottom = QtWidgets.QHBoxLayout()
    lbl_status = QtWidgets.QLabel("대기")
    btn_close = QtWidgets.QPushButton("닫기")
    row_bottom.addWidget(lbl_status, 1)
    row_bottom.addWidget(btn_close)
    layout.addLayout(row_bottom)
    return lbl_status, btn_close


def _assign_scene_batch_dialog_refs(dialog, dlg, widgets: dict) -> None:
    dialog._scene_batch_dialog = dlg
    dialog._scene_batch_tree = widgets["tree"]
    dialog._scene_batch_lbl_opts = widgets["lbl_opts"]
    dialog._scene_batch_chk_scene = widgets["chk_scene"]
    dialog._scene_batch_chk_refilter = widgets["chk_refilter"]
    dialog._scene_batch_progress = widgets["prog"]
    dialog._scene_batch_progress_all = widgets["prog_all"]
    dialog._scene_batch_status = widgets["lbl_status"]
    dialog._scene_batch_btn_add_files = widgets["btn_add_files"]
    dialog._scene_batch_btn_add_folder = widgets["btn_add_folder"]
    dialog._scene_batch_btn_remove = widgets["btn_remove"]
    dialog._scene_batch_btn_clear = widgets["btn_clear"]
    dialog._scene_batch_btn_run = widgets["btn_run"]
    dialog._scene_batch_btn_cancel = widgets["btn_cancel"]
    dialog._scene_batch_worker = None
