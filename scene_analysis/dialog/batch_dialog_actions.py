import os

from PyQt6 import QtWidgets

from .batch_options import _scene_batch_option_snapshot, _scene_batch_option_text
from .batch_runtime import _start_scene_batch
from .batch_runtime_paths import (
    _remember_scene_batch_dir,
    _scene_batch_add_paths,
    _scene_batch_start_dir,
)


def _pick_scene_batch_files(dialog, dlg, lbl_status) -> None:
    start_dir = _scene_batch_start_dir(dialog)
    files, _ = QtWidgets.QFileDialog.getOpenFileNames(
        dlg,
        "작업 파일 추가",
        start_dir,
        "Videos (*.mp4 *.mkv *.avi *.mov *.m4v *.webm *.ts *.flv *.wmv);;All Files (*)",
    )
    if files:
        _remember_scene_batch_dir(dialog, os.path.dirname(files[0]))
    added = _scene_batch_add_paths(dialog, [str(f) for f in files])
    if added > 0:
        lbl_status.setText(f"{added}개 파일 추가")


def _pick_scene_batch_folder(dialog, dlg, lbl_status) -> None:
    folder = QtWidgets.QFileDialog.getExistingDirectory(
        dlg,
        "작업 폴더 추가",
        _scene_batch_start_dir(dialog),
    )
    if not folder:
        return
    _remember_scene_batch_dir(dialog, folder)
    added = _scene_batch_add_paths(dialog, [folder])
    if added > 0:
        lbl_status.setText(f"{added}개 항목 추가")
    else:
        lbl_status.setText("추가할 영상 파일이 없습니다.")


def _remove_scene_batch_selected(tree, lbl_status) -> None:
    rows = tree.selectedItems()
    if not rows:
        return
    for it in rows:
        idx = tree.indexOfTopLevelItem(it)
        if idx >= 0:
            tree.takeTopLevelItem(idx)
    lbl_status.setText(f"{len(rows)}개 항목 제거")


def _clear_scene_batch_items(tree, lbl_status) -> None:
    if tree.topLevelItemCount() <= 0:
        return
    tree.clear()
    lbl_status.setText("목록 비움")


def _cancel_scene_batch(dialog, lbl_status, btn_cancel) -> None:
    worker = getattr(dialog, "_scene_batch_worker", None)
    if worker is None:
        return
    lbl_status.setText("취소 중…")
    worker.cancel()
    btn_cancel.setEnabled(False)


def _refresh_scene_batch_option_text(dialog, lbl_opts) -> None:
    try:
        lbl_opts.setText(_scene_batch_option_text(_scene_batch_option_snapshot(dialog)))
    except Exception:
        pass


def _close_scene_batch_dialog_with_confirm(dialog, dlg, on_close) -> None:
    worker = getattr(dialog, "_scene_batch_worker", None)
    if worker is not None and worker.isRunning():
        yes_btn = getattr(QtWidgets.QMessageBox, "Yes", QtWidgets.QMessageBox.StandardButton.Yes)
        no_btn = getattr(QtWidgets.QMessageBox, "No", QtWidgets.QMessageBox.StandardButton.No)
        ret = QtWidgets.QMessageBox.question(
            dlg,
            "순차 작업",
            "작업이 실행 중입니다. 취소하고 닫을까요?",
            yes_btn | no_btn,
            no_btn,
        )
        if ret != yes_btn:
            return
        worker.cancel()
        try:
            worker.wait(5000)
        except Exception:
            pass
    on_close()


def _bind_scene_batch_dialog_actions(dialog, dlg, widgets: dict, on_close) -> None:
    widgets["btn_add_files"].clicked.connect(
        lambda: _pick_scene_batch_files(dialog, dlg, widgets["lbl_status"])
    )
    widgets["btn_add_folder"].clicked.connect(
        lambda: _pick_scene_batch_folder(dialog, dlg, widgets["lbl_status"])
    )
    widgets["btn_remove"].clicked.connect(
        lambda: _remove_scene_batch_selected(widgets["tree"], widgets["lbl_status"])
    )
    widgets["btn_clear"].clicked.connect(
        lambda: _clear_scene_batch_items(widgets["tree"], widgets["lbl_status"])
    )
    widgets["btn_run"].clicked.connect(lambda: _start_scene_batch(dialog))
    widgets["btn_cancel"].clicked.connect(
        lambda: _cancel_scene_batch(dialog, widgets["lbl_status"], widgets["btn_cancel"])
    )
    widgets["btn_close"].clicked.connect(
        lambda: _close_scene_batch_dialog_with_confirm(dialog, dlg, on_close)
    )
    widgets["chk_scene"].toggled.connect(
        lambda _v: _refresh_scene_batch_option_text(dialog, widgets["lbl_opts"])
    )
    widgets["chk_refilter"].toggled.connect(
        lambda _v: _refresh_scene_batch_option_text(dialog, widgets["lbl_opts"])
    )
