import os
from typing import Optional, Tuple

from PyQt6 import QtWidgets

from .export_common import _available_ffmpeg_bin, _existing_scene_path, _fmt_ms_tag, _show_scene_busy_message
from .export_controls import on_clip_worker_busy_changed
from .export_selection import _get_single_selected_scene_gif_range, selected_grouped_scene_clip_ranges


def _ask_scene_gif_options(dialog) -> Optional[Tuple[int, int]]:
    popup = QtWidgets.QDialog(dialog)
    popup.setWindowTitle("선택구간 GIF 옵션")
    layout = QtWidgets.QFormLayout(popup)
    fps_edit = QtWidgets.QLineEdit("0")
    scale_edit = QtWidgets.QLineEdit("0")
    layout.addRow("FPS (0=원본):", fps_edit)
    layout.addRow("너비 (0=원본):", scale_edit)
    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
    )
    layout.addWidget(buttons)
    buttons.accepted.connect(popup.accept)
    buttons.rejected.connect(popup.reject)
    if popup.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None
    try:
        fps = int(fps_edit.text()) if fps_edit.text().strip().isdigit() else 0
        scale = int(scale_edit.text()) if scale_edit.text().strip().isdigit() else 0
    except Exception:
        return 0, 0
    return max(0, fps), max(0, scale)


def _scene_gif_output_path(path: str, start_ms: int, end_ms: int) -> str:
    base_dir = os.path.dirname(path)
    base_name, _ = os.path.splitext(os.path.basename(path))
    save_dir = os.path.join(base_dir, f"{base_name}_scene_gifs")
    os.makedirs(save_dir, exist_ok=True)
    out_path = os.path.join(save_dir, f"{base_name}_scenegif_{_fmt_ms_tag(start_ms)}_{_fmt_ms_tag(end_ms)}.gif")
    if not os.path.exists(out_path):
        return out_path
    root, ext = os.path.splitext(out_path)
    idx = 2
    while True:
        cand = f"{root}_{idx}{ext}"
        if not os.path.exists(cand):
            return cand
        idx += 1


def _warn_invalid_scene_gif_selection(dialog) -> None:
    if len(selected_grouped_scene_clip_ranges(dialog)) >= 2:
        msg = "GIF는 현재 1개 구간만 저장할 수 있습니다.\n구간묶음은 1개만 선택하거나, 씬/프레임셋에서 서로 다른 2개 시점을 선택하세요."
    else:
        msg = "GIF 저장 대상을 선택하세요.\n- 구간묶음 씬 1개 선택\n- 또는 프레임셋/씬 결과에서 서로 다른 2개 시점 선택"
    QtWidgets.QMessageBox.information(dialog, "알림", msg)


def _enqueue_scene_gif_job(dialog, path: str, start_ms: int, end_ms: int, fps: int, scale: int, ffbin: str) -> None:
    worker = getattr(dialog, "clip_worker", None)
    if worker is None or (not worker.isRunning()):
        QtWidgets.QMessageBox.warning(dialog, "실패", "GIF 워커가 실행 중이 아닙니다.")
        return
    payload = {
        "kind": "gif",
        "source": "manual",
        "mode_label": "선택구간 GIF",
        "current_path": path,
        "ffbin": ffbin,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "fps": fps,
        "scale": scale,
        "out_path": _scene_gif_output_path(path, start_ms, end_ms),
    }
    job_id = int(worker.enqueue(payload))
    dialog._clip_job_meta[job_id] = {
        "source": payload["source"],
        "kind": payload["kind"],
        "mode_label": payload["mode_label"],
    }
    on_clip_worker_busy_changed(dialog, True)
    dialog.lbl_status.setText("선택구간 GIF 작업 큐 등록")


def save_selected_scene_range_gif(dialog) -> None:
    if _show_scene_busy_message(dialog, include_clip_busy=True):
        return
    path = _existing_scene_path(dialog)
    if not path:
        QtWidgets.QMessageBox.warning(dialog, "오류", "현재 영상 경로를 찾을 수 없습니다.")
        return
    clip_range = _get_single_selected_scene_gif_range(dialog)
    if clip_range is None:
        _warn_invalid_scene_gif_selection(dialog)
        return
    options = _ask_scene_gif_options(dialog)
    if options is None:
        return
    ffbin = _available_ffmpeg_bin(dialog)
    if not ffbin:
        QtWidgets.QMessageBox.warning(dialog, "실패", "ffmpeg를 찾을 수 없습니다.")
        return
    start_ms, end_ms = int(clip_range[0]), int(clip_range[1])
    if end_ms <= start_ms:
        QtWidgets.QMessageBox.warning(dialog, "오류", "구간 길이가 0초 이하입니다.")
        return
    _enqueue_scene_gif_job(dialog, path, start_ms, end_ms, options[0], options[1], ffbin)
