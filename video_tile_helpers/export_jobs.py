from typing import Optional, Tuple

from PyQt6 import QtWidgets

from scene_analysis.core.media import ffmpeg_available

from .export_common import (
    _resolve_audio_export_range,
    _tile_ffmpeg_bin,
    _tile_media_source_path,
    _tile_status_message,
    get_export_path,
)
from .export_worker import _tile_export_busy_changed, _tile_job_meta, ensure_export_worker
from .support import is_image_file_path


def _ensure_export_idle(tile) -> bool:
    if bool(getattr(tile, "_export_worker_busy", False)):
        QtWidgets.QMessageBox.information(tile, "알림", "다른 내보내기 작업이 실행 중입니다.")
        return False
    return True


def _ab_export_range_ms(tile) -> Optional[Tuple[int, int]]:
    if tile.posA is None or tile.posB is None:
        QtWidgets.QMessageBox.warning(tile, "오류", "A와 B 구간을 먼저 지정하세요!")
        return None
    length_ms = int(tile.mediaplayer.get_length() or 0)
    start_ms = max(0, int(round(tile.posA * length_ms)))
    end_ms = max(start_ms + 1, int(round(tile.posB * length_ms)))
    if end_ms <= start_ms:
        QtWidgets.QMessageBox.warning(tile, "오류", "구간 길이가 0초 이하입니다. A/B 구간을 다시 지정하세요.")
        return None
    return start_ms, end_ms


def _ask_gif_options(tile) -> Optional[Tuple[int, int]]:
    dialog = QtWidgets.QDialog(tile)
    dialog.setWindowTitle("GIF 옵션")
    layout = QtWidgets.QFormLayout(dialog)
    fps_edit = QtWidgets.QLineEdit("0")
    scale_edit = QtWidgets.QLineEdit("0")
    layout.addRow("FPS (0=원본):", fps_edit)
    layout.addRow("너비 (0=원본):", scale_edit)
    buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    layout.addWidget(buttons)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None
    try:
        return (
            int(fps_edit.text()) if fps_edit.text().isdigit() else 0,
            int(scale_edit.text()) if scale_edit.text().isdigit() else 0,
        )
    except Exception:
        return 0, 0


def _ask_clip_options(tile) -> Optional[Tuple[bool, int, int, str]]:
    dialog = QtWidgets.QDialog(tile)
    dialog.setWindowTitle("Clip 옵션")
    layout = QtWidgets.QFormLayout(dialog)
    chk_encode = QtWidgets.QCheckBox("인코딩 모드 (체크시 재인코딩)")
    fps_edit = QtWidgets.QLineEdit("0")
    scale_edit = QtWidgets.QLineEdit("0")
    br_edit = QtWidgets.QLineEdit("")
    layout.addRow(chk_encode)
    layout.addRow("FPS (0=원본):", fps_edit)
    layout.addRow("너비 (0=원본):", scale_edit)
    layout.addRow("비트레이트 (kbps, 비우면 원본):", br_edit)
    buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    layout.addWidget(buttons)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None
    return chk_encode.isChecked(), int(fps_edit.text()) if fps_edit.text().isdigit() else 0, int(scale_edit.text()) if scale_edit.text().isdigit() else 0, br_edit.text().strip()


def _ask_audio_format(tile) -> Optional[str]:
    dialog = QtWidgets.QDialog(tile)
    dialog.setWindowTitle("오디오 클립 저장")
    layout = QtWidgets.QFormLayout(dialog)
    fmt_combo = QtWidgets.QComboBox(dialog)
    fmt_combo.addItem("M4A (AAC, 권장)", "m4a")
    fmt_combo.addItem("MP3", "mp3")
    fmt_combo.addItem("WAV (무손실)", "wav")
    layout.addRow("포맷:", fmt_combo)
    buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    layout.addWidget(buttons)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None
    return str(fmt_combo.currentData() or "m4a").strip().lower() or "m4a"


def _enqueue_export_job(tile, payload: dict, meta: dict, status_text: str) -> None:
    worker = ensure_export_worker(tile)
    job_id = int(worker.enqueue(payload))
    _tile_job_meta(tile)[job_id] = dict(meta)
    _tile_export_busy_changed(tile, True)
    _tile_status_message(tile, status_text, 2500)


def _require_export_source(tile, image_message: str) -> Optional[str]:
    path = tile._current_media_path()
    if is_image_file_path(path):
        QtWidgets.QMessageBox.information(tile, "알림", image_message)
        return None
    src = _tile_media_source_path(tile)
    if not src:
        QtWidgets.QMessageBox.critical(tile, "실패", "유효한 미디어 파일 경로를 찾을 수 없습니다.")
        return None
    return src


def _require_export_ffmpeg(tile) -> Optional[str]:
    ffbin = _tile_ffmpeg_bin(tile)
    if ffmpeg_available(ffbin):
        return ffbin
    QtWidgets.QMessageBox.critical(tile, "실패", f"ffmpeg를 찾을 수 없습니다.\n{ffbin}")
    return None


def export_gif(tile):
    src = _require_export_source(tile, "이미지에서는 GIF 구간 내보내기를 지원하지 않습니다.")
    if src is None or (not _ensure_export_idle(tile)):
        return
    clip_range = _ab_export_range_ms(tile)
    options = _ask_gif_options(tile) if clip_range is not None else None
    save_path = get_export_path(tile, "gif") if options is not None else None
    if clip_range is None or options is None or not save_path:
        return
    _enqueue_export_job(
        tile,
        {"kind": "gif", "source": "manual", "mode_label": "타일 GIF", "current_path": src, "ffbin": _tile_ffmpeg_bin(tile), "start_ms": clip_range[0], "end_ms": clip_range[1], "fps": options[0], "scale": options[1], "out_path": save_path},
        {"kind": "gif"},
        "GIF 저장 작업 큐 등록",
    )


def export_clip(tile):
    src = _require_export_source(tile, "이미지에서는 클립 내보내기를 지원하지 않습니다.")
    if src is None or (not _ensure_export_idle(tile)):
        return
    clip_range = _ab_export_range_ms(tile)
    options = _ask_clip_options(tile) if clip_range is not None else None
    save_path = get_export_path(tile, "mp4") if options is not None else None
    ffbin = _require_export_ffmpeg(tile) if save_path is not None else None
    if clip_range is None or options is None or not save_path or not ffbin:
        return
    _enqueue_export_job(
        tile,
        {"kind": "tile_clip", "source": "manual", "mode_label": "타일 Clip", "current_path": src, "ffbin": ffbin, "start_ms": clip_range[0], "end_ms": clip_range[1], "encode": bool(options[0]), "fps": options[1], "scale": options[2], "bitrate": options[3], "out_path": save_path},
        {"kind": "tile_clip"},
        "클립 저장 작업 큐 등록",
    )


def export_audio_clip(tile):
    src = _require_export_source(tile, "이미지에서는 오디오 클립 내보내기를 지원하지 않습니다.")
    if src is None or (not _ensure_export_idle(tile)):
        return
    audio_format = _ask_audio_format(tile)
    range_info = _resolve_audio_export_range(tile) if audio_format is not None else None
    if audio_format is None or range_info is None:
        if audio_format is not None:
            QtWidgets.QMessageBox.warning(tile, "오류", "영상 길이를 확인할 수 없습니다. 잠시 후 다시 시도하세요.")
        return
    ffbin = _require_export_ffmpeg(tile)
    save_path = get_export_path(tile, audio_format, start_pos=range_info[2], end_pos=range_info[3]) if ffbin else None
    if not ffbin or not save_path:
        return
    _enqueue_export_job(
        tile,
        {"kind": "tile_audio_clip", "source": "manual", "mode_label": "오디오 클립", "current_path": src, "ffbin": ffbin, "start_ms": range_info[0], "end_ms": range_info[1], "audio_only": True, "audio_format": audio_format, "out_path": save_path},
        {"kind": "tile_audio_clip", "audio_format": audio_format},
        "오디오 클립 저장 작업 큐 등록",
    )
