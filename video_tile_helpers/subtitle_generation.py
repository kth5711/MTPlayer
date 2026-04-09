from __future__ import annotations

import os
import json
import subprocess
import sys
import time
import weakref
import shutil
from pathlib import Path
from typing import Optional

from PyQt6 import QtCore, QtWidgets

from i18n import tr
from process_utils import hidden_subprocess_kwargs

from .export_common import _tile_status_message
from .export_worker import _tile_export_busy_changed
from .playlist import set_external_subtitle_for_path


_DEFAULT_SUBTITLE_MODEL = "Systran/faster-whisper-large-v3"
_SUBTITLE_MODEL_CONFIG = "subtitle_asr_model"
_SUBTITLE_MODEL_PRESETS = (
    ("품질 우선", "Systran/faster-whisper-large-v3"),
    ("빠름 (turbo)", "mobiuslabsgmbh/faster-whisper-large-v3-turbo"),
)


class SubtitleGenerationWorker(QtCore.QThread):
    jobFinished = QtCore.pyqtSignal(object)
    jobFailed = QtCore.pyqtSignal(object)
    jobProgress = QtCore.pyqtSignal(object)

    def __init__(self, job: dict, parent=None):
        super().__init__(parent)
        self._job = dict(job or {})
        self._proc: Optional[subprocess.Popen] = None
        self._stop_requested = False
        self._started_at: Optional[float] = None
        self._last_progress: dict = {}

    def stop(self) -> None:
        self._stop_requested = True
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
        except Exception:
            pass

    def run(self) -> None:
        self._started_at = time.monotonic()
        try:
            payload = _run_subtitle_job(self._job, self)
        except Exception as exc:
            elapsed = max(0.0, time.monotonic() - float(self._started_at or time.monotonic()))
            self.jobFailed.emit(
                {
                    "error": str(exc or "알 수 없는 오류"),
                    "media_path": str(self._job.get("media_path") or ""),
                    "out_path": str(self._job.get("out_path") or ""),
                    "elapsed_seconds": elapsed,
                    **dict(self._last_progress or {}),
                }
            )
            return
        self.jobFinished.emit(payload)

    def report_progress(
        self,
        *,
        stage: str,
        percent: Optional[float] = None,
        note: str = "",
        started_at: Optional[float] = None,
    ) -> None:
        if started_at is not None and self._started_at is None:
            self._started_at = float(started_at)
        if self._started_at is None:
            self._started_at = time.monotonic()
        elapsed = max(0.0, time.monotonic() - float(self._started_at))
        payload = {
            "stage": str(stage or "").strip() or "자막 생성 중",
            "percent": None if percent is None else max(0.0, min(100.0, float(percent))),
            "note": str(note or "").strip(),
            "elapsed_seconds": elapsed,
        }
        self._last_progress = dict(payload)
        self.jobProgress.emit(payload)


def _save_main_config(mainwin) -> None:
    if mainwin is None or not hasattr(mainwin, "save_config"):
        return
    try:
        mainwin.save_config()
    except Exception:
        pass


def generate_subtitle_from_context(tile) -> None:
    media_path = _current_local_media_path(tile)
    if not media_path:
        QtWidgets.QMessageBox.information(
            tile,
            tr(tile, "자막 생성"),
            tr(tile, "현재 로컬 미디어 파일을 찾을 수 없습니다."),
        )
        return
    if bool(getattr(tile, "_export_worker_busy", False)):
        QtWidgets.QMessageBox.information(
            tile,
            tr(tile, "자막 생성"),
            tr(tile, "다른 저장 작업이 실행 중입니다."),
        )
        return
    python_path = _subtitle_python_path(tile)
    if not os.path.isfile(python_path):
        QtWidgets.QMessageBox.warning(
            tile,
            tr(tile, "자막 생성"),
            tr(tile, "자막 AI env를 찾지 못했습니다.\n{path}", path=python_path),
        )
        return
    out_path = _default_subtitle_output_path(media_path)
    start_dir = os.path.dirname(out_path) or tile._dialog_start_dir()
    try:
        os.makedirs(start_dir, exist_ok=True)
    except OSError as exc:
        QtWidgets.QMessageBox.warning(
            tile,
            tr(tile, "자막 생성"),
            tr(tile, "저장 폴더를 만들 수 없습니다.\n\n{error}", error=str(exc)),
        )
        return
    model_name = _ask_subtitle_model(tile)
    if not model_name:
        return
    stop_subtitle_generation_worker(tile)
    job = {
        "media_path": media_path,
        "out_path": out_path,
        "python_path": python_path,
        "model": model_name,
    }
    worker = SubtitleGenerationWorker(job, parent=tile)
    tile_ref = weakref.ref(tile)
    worker.jobFinished.connect(lambda payload, ref=tile_ref: _dispatch_subtitle_finished(ref, payload))
    worker.jobFailed.connect(lambda payload, ref=tile_ref: _dispatch_subtitle_failed(ref, payload))
    worker.jobProgress.connect(lambda payload, ref=tile_ref: _dispatch_subtitle_progress(ref, payload))
    tile._subtitle_generation_worker = worker
    _tile_export_busy_changed(tile, True)
    _tile_status_message(tile, tr(tile, "자막 생성 시작: {name}", name=os.path.basename(media_path)), 4000)
    worker.start()


def stop_subtitle_generation_worker(tile) -> None:
    worker = getattr(tile, "_subtitle_generation_worker", None)
    tile._subtitle_generation_worker = None
    if worker is None:
        return
    try:
        worker.stop()
    except Exception:
        pass
    try:
        worker.wait(3000)
    except Exception:
        pass
    _tile_export_busy_changed(tile, False)


def _dispatch_subtitle_finished(tile_ref, payload: dict) -> None:
    tile = tile_ref()
    if tile is None:
        return
    tile._subtitle_generation_worker = None
    _tile_export_busy_changed(tile, False)
    media_path = str(payload.get("media_path") or "").strip()
    out_path = str(payload.get("out_path") or "").strip()
    if media_path and out_path:
        set_external_subtitle_for_path(tile, media_path, out_path, overwrite=True)
    applied = False
    if out_path:
        applied = bool(tile._apply_external_subtitle_to_player(out_path))
        tile.refresh_track_menus()
        try:
            tile._remember_dialog_dir(os.path.dirname(out_path))
        except Exception:
            pass
    elapsed_text = _format_duration_seconds(float(payload.get("elapsed_seconds") or 0.0))
    label = tr(tile, "자막 생성 완료: {path}", path=out_path)
    if elapsed_text != "00:00":
        label += tr(tile, " | {elapsed}", elapsed=elapsed_text)
    _tile_status_message(tile, label, 5000)
    if _prompt_translate_after_generation(tile, out_path, applied):
        try:
            from .subtitle_translation import translate_subtitle_from_context

            translate_subtitle_from_context(tile, subtitle_path=out_path)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                tile,
                tr(tile, "자막 번역"),
                tr(tile, "번역 dialog를 열지 못했습니다.\n{error}", error=str(exc)),
            )


def _dispatch_subtitle_failed(tile_ref, payload: dict) -> None:
    tile = tile_ref()
    if tile is None:
        return
    tile._subtitle_generation_worker = None
    _tile_export_busy_changed(tile, False)
    error = str((payload or {}).get("error") or "알 수 없는 오류").strip()
    if error == "사용자 취소":
        _tile_status_message(tile, tr(tile, "자막 생성 취소"), 3000)
        return
    elapsed_seconds = float((payload or {}).get("elapsed_seconds") or 0.0)
    stage = str((payload or {}).get("stage") or "").strip()
    percent = (payload or {}).get("percent")
    note = str((payload or {}).get("note") or "").strip()
    if stage or elapsed_seconds > 0.0:
        detail = []
        if stage:
            detail.append(stage)
        if percent is not None:
            detail.append(f"{float(percent):.1f}%")
        if elapsed_seconds > 0.0:
            detail.append(_format_duration_seconds(elapsed_seconds))
        if note:
            detail.append(note)
        if detail:
            error += "\n\n" + " | ".join(detail)
    QtWidgets.QMessageBox.critical(tile, tr(tile, "실패"), tr(tile, "자막 생성 실패:\n{error}", error=error))
    _tile_status_message(tile, tr(tile, "자막 생성 실패"), 4000)


def _dispatch_subtitle_progress(tile_ref, payload: dict) -> None:
    tile = tile_ref()
    if tile is None:
        return
    stage = str((payload or {}).get("stage") or "자막 생성 중").strip() or "자막 생성 중"
    percent = (payload or {}).get("percent")
    note = str((payload or {}).get("note") or "").strip()
    elapsed_seconds = float((payload or {}).get("elapsed_seconds") or 0.0)
    parts = [stage]
    if percent is not None:
        parts.append(f"{float(percent):.1f}%")
    if elapsed_seconds > 0.0:
        parts.append(f"경과 {_format_duration_seconds(elapsed_seconds)}")
    if note:
        parts.append(note)
    _tile_status_message(tile, " | ".join(parts), 0)


def _prompt_translate_after_generation(tile, out_path: str, applied: bool) -> bool:
    message = tr(tile, "자막 생성 완료:\n{path}", path=out_path)
    if applied:
        message += tr(tile, "\n현재 영상에 바로 적용했습니다.")
    message += tr(tile, "\n\n이어서 번역할까요?")
    box = QtWidgets.QMessageBox(tile)
    box.setIcon(QtWidgets.QMessageBox.Icon.Information)
    box.setWindowTitle(tr(tile, "완료"))
    box.setText(message)
    translate_btn = box.addButton(tr(tile, "바로 번역"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
    box.addButton(QtWidgets.QMessageBox.StandardButton.Close)
    box.exec()
    return box.clickedButton() is translate_btn


def _current_local_media_path(tile) -> str:
    for getter in (getattr(tile, "_current_playlist_path", None), getattr(tile, "_current_media_path", None)):
        if not callable(getter):
            continue
        try:
            path = str(getter() or "").strip()
        except Exception:
            path = ""
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    return ""


def _default_subtitle_output_path(media_path: str) -> str:
    base_dir = os.path.dirname(media_path)
    base_name, _ = os.path.splitext(os.path.basename(media_path))
    return os.path.join(base_dir, f"{base_name}.autogen.srt")


def _resolve_default_subtitle_model(tile) -> str:
    override = str(os.environ.get("MULTIPLAY_SUBTITLE_WHISPER_MODEL") or "").strip()
    if override:
        return override
    mainwin = tile.window() if tile is not None else None
    configured = str(getattr(mainwin, "config", {}).get(_SUBTITLE_MODEL_CONFIG, "") or "").strip()
    return configured or _DEFAULT_SUBTITLE_MODEL


def _ask_subtitle_model(tile) -> str:
    mainwin = tile.window() if tile is not None else None
    current_model = _resolve_default_subtitle_model(tile)
    dialog = QtWidgets.QDialog(tile)
    dialog.setWindowTitle(tr(tile, "자막 생성"))
    dialog.resize(420, 0)
    layout = QtWidgets.QVBoxLayout(dialog)
    form = QtWidgets.QFormLayout()
    layout.addLayout(form)

    combo = QtWidgets.QComboBox(dialog)
    combo.setEditable(True)
    for label, model_id in _SUBTITLE_MODEL_PRESETS:
        combo.addItem(f"{label} - {model_id}", model_id)
    idx = combo.findData(current_model)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    else:
        combo.setEditText(current_model)
    form.addRow(tr(tile, "자막 모델"), combo)

    hint = QtWidgets.QLabel(
        tr(tile, "품질 우선은 정확도가 높고, turbo는 더 빠릅니다. 직접 모델 ID를 입력해도 됩니다."),
        dialog,
    )
    hint.setWordWrap(True)
    layout.addWidget(hint)

    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
        dialog,
    )
    layout.addWidget(buttons)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return ""
    model_name = str(combo.currentData() or combo.currentText() or "").strip()
    if not model_name:
        return ""
    if mainwin is not None:
        mainwin.config[_SUBTITLE_MODEL_CONFIG] = model_name
        _save_main_config(mainwin)
    return model_name


def _subtitle_python_path(tile) -> str:
    override = str(os.environ.get("MULTIPLAY_SUBTITLE_PYTHON") or "").strip()
    if override:
        return override
    mainwin = tile._main_window() if hasattr(tile, "_main_window") else None
    if mainwin is not None:
        configured = str(getattr(mainwin, "config", {}).get("subtitle_asr_python", "") or "").strip()
        if configured and os.path.isfile(configured):
            return configured
    current_exe = str(sys.executable or "").strip()
    if _python_has_faster_whisper(current_exe):
        return current_exe
    for candidate in _candidate_python_paths():
        if _python_has_faster_whisper(candidate):
            if mainwin is not None:
                mainwin.config["subtitle_asr_python"] = candidate
                _save_main_config(mainwin)
            return candidate
    return ""


def _python_has_faster_whisper(python_path: str) -> bool:
    if not python_path or not os.path.isfile(python_path):
        return False
    try:
        return subprocess.run(
            [python_path, "-c", "import faster_whisper; print('ok')"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=6,
            **hidden_subprocess_kwargs(),
        ).returncode == 0
    except Exception:
        return False


def _candidate_python_paths() -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for raw in (sys.executable, shutil.which("python"), shutil.which("python.exe")):
        path = str(raw or "").strip()
        if not path:
            continue
        norm = os.path.abspath(path)
        if norm not in seen:
            seen.add(norm)
            candidates.append(norm)
    try:
        current = Path(sys.executable).resolve()
    except Exception:
        current = None
    env_root = current.parent if current is not None else None
    envs_dir = env_root.parent if env_root is not None else None
    if envs_dir is not None and envs_dir.is_dir():
        preferred_names = ("aivoice", "ocr", env_root.name if env_root is not None else "")
        preferred: list[Path] = []
        others: list[Path] = []
        for child in envs_dir.iterdir():
            candidate = child / "python.exe"
            if not candidate.is_file():
                continue
            if child.name in preferred_names:
                preferred.append(candidate)
            else:
                others.append(candidate)
        for candidate in preferred + others:
            norm = os.path.abspath(str(candidate))
            if norm not in seen:
                seen.add(norm)
                candidates.append(norm)
    return candidates


def _subtitle_helper_script() -> str:
    return os.path.join(os.path.dirname(__file__), "subtitle_asr_subprocess.py")


def _run_subtitle_job(job: dict, worker: SubtitleGenerationWorker) -> dict:
    media_path = str(job.get("media_path") or "").strip()
    out_path = str(job.get("out_path") or "").strip()
    python_path = str(job.get("python_path") or "").strip()
    model = str(job.get("model") or _DEFAULT_SUBTITLE_MODEL).strip() or _DEFAULT_SUBTITLE_MODEL
    if not media_path or not os.path.isfile(media_path):
        raise RuntimeError("현재 로컬 미디어 파일을 찾을 수 없습니다.")
    if not out_path:
        raise RuntimeError("자막 저장 경로가 비어 있습니다.")
    os.makedirs(os.path.dirname(out_path) or os.getcwd(), exist_ok=True)
    try:
        if os.path.isfile(out_path):
            os.remove(out_path)
    except OSError:
        pass
    helper = _subtitle_helper_script()
    if not os.path.isfile(helper):
        raise RuntimeError("자막 helper 스크립트를 찾지 못했습니다.")
    command = [
        python_path or sys.executable,
        helper,
        "--input",
        media_path,
        "--output",
        out_path,
        "--model",
        model,
    ]
    worker.report_progress(stage="모델 로드 중", percent=0.0)
    stdout, stderr, return_code = _run_subprocess(command, worker)
    if int(return_code or 0) != 0:
        detail = (stderr or stdout or "").strip()
        raise RuntimeError(detail or "자막 생성 subprocess 실행에 실패했습니다.")
    if not os.path.isfile(out_path) or int(os.path.getsize(out_path) or 0) <= 0:
        raise RuntimeError("자막 출력 파일 생성에 실패했습니다.")
    elapsed_seconds = max(0.0, time.monotonic() - float(worker._started_at or time.monotonic()))
    return {
        "media_path": media_path,
        "out_path": out_path,
        "stdout": stdout,
        "stderr": stderr,
        "elapsed_seconds": elapsed_seconds,
    }


def _run_subprocess(command: list[str], worker: SubtitleGenerationWorker) -> tuple[str, str, int]:
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **hidden_subprocess_kwargs(),
    )
    worker._proc = proc
    out_lines: list[str] = []
    try:
        stream = proc.stdout
        if stream is not None:
            for raw_line in iter(stream.readline, ""):
                if worker._stop_requested:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    break
                if _handle_subprocess_progress_line(raw_line, worker):
                    continue
                out_lines.append(raw_line)
            try:
                stream.close()
            except Exception:
                pass
        proc.wait()
    finally:
        worker._proc = None
    if worker._stop_requested:
        raise RuntimeError("사용자 취소")
    stdout = "".join(out_lines)
    return stdout, stdout, int(proc.returncode or 0)


def _handle_subprocess_progress_line(line: str, worker: SubtitleGenerationWorker) -> bool:
    raw = str(line or "").strip()
    if not raw.startswith("__MP_PROGRESS__"):
        return False
    payload_text = raw[len("__MP_PROGRESS__") :].strip()
    try:
        payload = json.loads(payload_text)
    except Exception:
        return True
    worker.report_progress(
        stage=str(payload.get("stage") or "자막 생성 중"),
        percent=payload.get("percent"),
        note=str(payload.get("note") or ""),
    )
    return True


def _format_duration_seconds(seconds: float) -> str:
    total = max(0, int(round(float(seconds or 0.0))))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
