from PyQt6 import QtWidgets

from .batch_options import _scene_batch_option_snapshot, _scene_batch_option_text
from .batch_dialog_actions import _bind_scene_batch_dialog_actions
from .batch_dialog_ui import (
    _assign_scene_batch_dialog_refs,
    _create_scene_batch_dialog_widgets,
)


def _reuse_scene_batch_dialog(dialog) -> bool:
    dlg = getattr(dialog, "_scene_batch_dialog", None)
    if dlg is None:
        return False
    try:
        dialog._scene_batch_lbl_opts.setText(_scene_batch_option_text(_scene_batch_option_snapshot(dialog)))
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        return True
    except Exception:
        dialog._scene_batch_dialog = None
        return False


def open_scene_batch_dialog(dialog) -> None:
    if _reuse_scene_batch_dialog(dialog):
        return
    dlg = QtWidgets.QDialog(dialog)
    dlg.setWindowTitle("씬변화/유사씬 순차 작업")
    dlg.setModal(False)
    dlg.resize(860, 520)
    widgets = _create_scene_batch_dialog_widgets(
        dlg, _scene_batch_option_text(_scene_batch_option_snapshot(dialog))
    )
    _assign_scene_batch_dialog_refs(dialog, dlg, widgets)
    _bind_scene_batch_dialog_actions(dialog, dlg, widgets, dlg.close)
    dlg.finished.connect(lambda _r: close_scene_batch_dialog(dialog, close_widget=False))
    dlg.show()


def _stop_scene_batch_worker(dialog) -> None:
    worker = getattr(dialog, "_scene_batch_worker", None)
    if worker is None or not worker.isRunning():
        return
    try:
        worker.cancel()
    except Exception:
        pass
    try:
        worker.wait(5000)
    except Exception:
        pass


def _reset_scene_batch_dialog_refs(dialog) -> None:
    for name in (
        "_scene_batch_worker",
        "_scene_batch_dialog",
        "_scene_batch_tree",
        "_scene_batch_lbl_opts",
        "_scene_batch_chk_scene",
        "_scene_batch_chk_refilter",
        "_scene_batch_progress",
        "_scene_batch_progress_all",
        "_scene_batch_status",
        "_scene_batch_btn_add_files",
        "_scene_batch_btn_add_folder",
        "_scene_batch_btn_remove",
        "_scene_batch_btn_clear",
        "_scene_batch_btn_run",
        "_scene_batch_btn_cancel",
    ):
        setattr(dialog, name, None)


def close_scene_batch_dialog(dialog, close_widget: bool = True) -> None:
    _stop_scene_batch_worker(dialog)
    dlg = getattr(dialog, "_scene_batch_dialog", None)
    if close_widget and dlg is not None:
        try:
            dlg.close()
        except Exception:
            pass
    _reset_scene_batch_dialog_refs(dialog)
