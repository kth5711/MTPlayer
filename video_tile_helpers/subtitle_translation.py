from __future__ import annotations

import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt6 import QtCore, QtWidgets

from i18n import tr
from process_utils import hidden_subprocess_kwargs

from .export_common import _tile_status_message
from .export_worker import _tile_export_busy_changed
from .playlist import set_external_subtitle_for_path


_DEFAULT_TRANSLATE_TARGET = "ko"
_DEFAULT_SERVER_PORT = 8137
_LLAMA_CONFIG_BIN = "subtitle_translate_llama_bin"
_LLAMA_CONFIG_MODEL = "subtitle_translate_model_path"
_LLAMA_CONFIG_SOURCE = "subtitle_translate_source_lang"
_LLAMA_CONFIG_TARGET = "subtitle_translate_target_lang"
_LLAMA_CONFIG_LAST_SUBTITLE = "subtitle_translate_last_subtitle"
_TRANSLATE_CHUNK_LADDER = (1,)
_TRANSLATE_REQUEST_TIMEOUT = 600.0
_LLAMA_SERVER_CONTEXT = 12800
_LLAMA_SLOT_ID = 0
_GENERIC_TRANSLATE_SEED = 42
_GENERIC_INPUT_TOKEN_BUDGET_CAP = 3200
_GENERIC_OUTPUT_TOKEN_RESERVE = 2400
_GENERIC_TOKEN_HEADROOM = 1000
_GENERIC_MAX_CHUNK_CUES = 192
_GENERIC_TOKENIZE_SAMPLE_LIMIT = 8
_GENERIC_TOKEN_ESTIMATE_SAFETY_MARGIN = 0.88
_GENERIC_TOKEN_ESTIMATE_MAX_SCALE = 3.0
_GENERIC_TSV_FALLBACK_MAX_BATCH = 12

_TOKENIZE_BODY_KEYS = ("content", "prompt", "text")
_SUPPORTED_TRANSLATE_SUBTITLE_EXTENSIONS = {".srt"}
_TRANSLATE_SUBTITLE_FILE_FILTER = "SRT Files (*.srt);;All Files (*)"
_LANGUAGE_NAME_EN = {"ko": "Korean", "en": "English", "ja": "Japanese", "zh": "Chinese"}
_LANGUAGE_NAME_LOCALIZED = {"ko": "한국어", "en": "영어", "ja": "일본어", "zh": "중국어"}
_tokenize_body_key_hint: Optional[str] = None


@dataclass
class SubtitleCue:
    index: int
    start: str
    end: str
    text: str


@dataclass(frozen=True)
class _GenericTokenEstimator:
    prefix_tokens: int
    separator_tokens: int
    scale: float
    sampled_item_tokens: dict[int, int]

    def item_tokens(self, cue: SubtitleCue) -> int:
        cached = self.sampled_item_tokens.get(cue.index)
        if cached is not None:
            return max(1, int(cached))
        return max(1, int(math.ceil(_rough_token_estimate(_generic_structured_item_text(cue)) * self.scale)))


def _save_main_config(mainwin) -> None:
    if mainwin is None or not hasattr(mainwin, "save_config"):
        return
    try:
        mainwin.save_config()
    except Exception:
        pass


class SubtitleTranslationWorker(QtCore.QThread):
    jobFinished = QtCore.pyqtSignal(object)
    jobFailed = QtCore.pyqtSignal(object)
    jobProgress = QtCore.pyqtSignal(object)

    def __init__(self, job: dict, parent=None):
        super().__init__(parent)
        self._job = dict(job or {})
        self._server_proc: Optional[subprocess.Popen] = None
        self._server_log_path: str = ""
        self._server_log_handle = None
        self._stop_requested = False
        self._started_at: Optional[float] = None
        self._last_progress: dict = {}

    def stop(self) -> None:
        self._stop_requested = True
        proc = self._server_proc
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
            payload = _run_translation_job(self._job, self)
        except Exception as exc:
            elapsed = max(0.0, time.monotonic() - float(self._started_at or time.monotonic()))
            self.jobFailed.emit(
                {
                    "error": str(exc or "알 수 없는 오류"),
                    "subtitle_path": str(self._job.get("subtitle_path") or ""),
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
        processed: int,
        total: int,
        chunk_size: int,
        stage: str,
        started_at: Optional[float] = None,
        note: str = "",
    ) -> None:
        if started_at is not None and self._started_at is None:
            self._started_at = float(started_at)
        if self._started_at is None:
            self._started_at = time.monotonic()
        elapsed = max(0.0, time.monotonic() - float(self._started_at))
        eta = None
        if total > 0 and processed > 0 and processed < total:
            eta = elapsed * float(total - processed) / float(processed)
        payload = {
            "processed": max(0, int(processed)),
            "total": max(0, int(total)),
            "chunk_size": max(1, int(chunk_size)),
            "stage": str(stage or "").strip() or "번역 중",
            "note": str(note or "").strip(),
            "elapsed_seconds": elapsed,
            "eta_seconds": eta,
        }
        self._last_progress = dict(payload)
        self.jobProgress.emit(payload)


def translate_subtitle_from_context(tile, *, subtitle_path: str = "") -> None:
    if bool(getattr(tile, "_export_worker_busy", False)):
        QtWidgets.QMessageBox.information(
            tile,
            tr(tile, "자막 번역"),
            tr(tile, "다른 저장 작업이 실행 중입니다."),
        )
        return
    opts = _ask_subtitle_translate_options(tile, subtitle_path=subtitle_path)
    if not opts:
        return
    stop_subtitle_translation_worker(tile)
    worker = SubtitleTranslationWorker(opts, parent=tile)
    tile_ref = weakref.ref(tile)
    worker.jobFinished.connect(lambda payload, ref=tile_ref: _dispatch_translation_finished(ref, payload))
    worker.jobFailed.connect(lambda payload, ref=tile_ref: _dispatch_translation_failed(ref, payload))
    worker.jobProgress.connect(lambda payload, ref=tile_ref: _dispatch_translation_progress(ref, payload))
    tile._subtitle_translation_worker = worker
    _tile_export_busy_changed(tile, True)
    _tile_status_message(
        tile,
        tr(tile, "자막 번역 시작: {name}", name=os.path.basename(str(opts.get("subtitle_path") or ""))),
        4000,
    )
    worker.start()


def stop_subtitle_translation_worker(tile) -> None:
    worker = getattr(tile, "_subtitle_translation_worker", None)
    tile._subtitle_translation_worker = None
    if worker is None:
        return
    try:
        worker.stop()
    except Exception:
        pass
    try:
        worker.wait(4000)
    except Exception:
        pass
    _tile_export_busy_changed(tile, False)


def _dispatch_translation_finished(tile_ref, payload: dict) -> None:
    tile = tile_ref()
    if tile is None:
        return
    tile._subtitle_translation_worker = None
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
    _tile_status_message(tile, tr(tile, "자막 번역 완료: {path} | {elapsed}", path=out_path, elapsed=elapsed_text), 5000)
    message = tr(tile, "자막 번역 완료:\n{path}", path=out_path)
    if elapsed_text != "00:00":
        message += tr(tile, "\n소요시간: {elapsed}", elapsed=elapsed_text)
    if applied:
        message += tr(tile, "\n현재 영상에 바로 적용했습니다.")
    QtWidgets.QMessageBox.information(tile, tr(tile, "완료"), message)


def _dispatch_translation_failed(tile_ref, payload: dict) -> None:
    tile = tile_ref()
    if tile is None:
        return
    tile._subtitle_translation_worker = None
    _tile_export_busy_changed(tile, False)
    error = str((payload or {}).get("error") or "알 수 없는 오류").strip()
    if error == "사용자 취소":
        _tile_status_message(tile, tr(tile, "자막 번역 취소"), 3000)
        return
    message = tr(tile, "자막 번역 실패:\n{error}", error=error)
    processed = int((payload or {}).get("processed") or 0)
    total = int((payload or {}).get("total") or 0)
    elapsed_seconds = float((payload or {}).get("elapsed_seconds") or 0.0)
    note = str((payload or {}).get("note") or "").strip()
    if total > 0:
        message += tr(tile, "\n\n진행: {processed}/{total}", processed=processed, total=total)
    if elapsed_seconds > 0.0:
        message += tr(tile, "\n경과: {elapsed}", elapsed=_format_duration_seconds(elapsed_seconds))
    if note:
        message += tr(tile, "\n사유: {note}", note=note)
    _show_copyable_error_dialog(tile, tr(tile, "실패"), tr(tile, "자막 번역 실패"), message)
    _tile_status_message(tile, tr(tile, "자막 번역 실패"), 4000)


def _show_copyable_error_dialog(parent, title: str, header: str, detail: str) -> None:
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(str(title or "").strip() or "실패")
    dialog.resize(760, 420)
    layout = QtWidgets.QVBoxLayout(dialog)

    lbl = QtWidgets.QLabel(str(header or "").strip() or "오류", dialog)
    lbl.setWordWrap(True)
    layout.addWidget(lbl)

    text_edit = QtWidgets.QPlainTextEdit(dialog)
    text_edit.setReadOnly(True)
    text_edit.setPlainText(str(detail or "").strip())
    layout.addWidget(text_edit, 1)

    buttons = QtWidgets.QDialogButtonBox(dialog)
    btn_copy = buttons.addButton(tr(parent, "복사"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
    btn_close = buttons.addButton(QtWidgets.QDialogButtonBox.StandardButton.Close)
    layout.addWidget(buttons)

    def _copy_detail() -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text_edit.toPlainText())

    btn_copy.clicked.connect(_copy_detail)
    btn_close.clicked.connect(dialog.accept)
    dialog.exec()


def _dispatch_translation_progress(tile_ref, payload: dict) -> None:
    tile = tile_ref()
    if tile is None:
        return
    processed = max(0, int((payload or {}).get("processed") or 0))
    total = max(0, int((payload or {}).get("total") or 0))
    chunk_size = max(1, int((payload or {}).get("chunk_size") or 1))
    stage = str((payload or {}).get("stage") or "번역 중").strip() or "번역 중"
    note = str((payload or {}).get("note") or "").strip()
    elapsed_seconds = float((payload or {}).get("elapsed_seconds") or 0.0)
    eta_seconds = (payload or {}).get("eta_seconds")
    percent = (100.0 * float(processed) / float(total)) if total > 0 else 0.0
    parts = [
        f"{stage} {processed}/{total}",
        f"({percent:.1f}%)",
        f"경과 {_format_duration_seconds(elapsed_seconds)}",
        f"배치 {chunk_size} cue",
    ]
    if note:
        parts.append(f"사유 {note}")
    if eta_seconds is not None:
        parts.append(f"예상 {_format_duration_seconds(float(eta_seconds))}")
    _tile_status_message(tile, " | ".join(parts), 0)


def _format_duration_seconds(seconds: float) -> str:
    total = max(0, int(round(float(seconds or 0.0))))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _ask_subtitle_translate_options(tile, *, subtitle_path: str = "") -> Optional[dict]:
    mainwin = tile._main_window() if hasattr(tile, "_main_window") else None
    config = getattr(mainwin, "config", {}) if mainwin is not None else {}
    media_path = _current_local_media_path(tile)
    override_subtitle = str(subtitle_path or "").strip()
    if override_subtitle and os.path.isfile(override_subtitle):
        default_subtitle = os.path.abspath(override_subtitle)
    else:
        default_subtitle = _default_source_subtitle_path(tile, media_path, config)
    llama_bin = _resolve_default_llama_bin(config)
    model_path = _resolve_default_model_path(config)
    source_lang = str(config.get(_LLAMA_CONFIG_SOURCE, "auto") or "auto")
    target_lang = str(config.get(_LLAMA_CONFIG_TARGET, _DEFAULT_TRANSLATE_TARGET) or _DEFAULT_TRANSLATE_TARGET)

    dialog = QtWidgets.QDialog(tile)
    dialog.setWindowTitle(tr(tile, "자막 번역"))
    dialog.resize(680, 0)
    layout = QtWidgets.QVBoxLayout(dialog)
    form = QtWidgets.QFormLayout()
    layout.addLayout(form)

    edt_sub = QtWidgets.QLineEdit(default_subtitle, dialog)
    btn_sub = QtWidgets.QPushButton(tr(tile, "찾기"), dialog)
    sub_row = _line_with_button(dialog, edt_sub, btn_sub)
    form.addRow(tr(tile, "원본 자막"), sub_row)

    cmb_lang = QtWidgets.QComboBox(dialog)
    for code, label in _translation_language_items(tile, include_auto=False):
        cmb_lang.addItem(label, code)
    idx = max(0, cmb_lang.findData(target_lang))
    cmb_lang.setCurrentIndex(idx)
    form.addRow(tr(tile, "번역 언어"), cmb_lang)

    cmb_source = QtWidgets.QComboBox(dialog)
    for code, label in _translation_language_items(tile, include_auto=True):
        cmb_source.addItem(label, code)
    src_idx = max(0, cmb_source.findData(source_lang))
    cmb_source.setCurrentIndex(src_idx)
    form.addRow(tr(tile, "원문 언어"), cmb_source)

    edt_llama = QtWidgets.QLineEdit(llama_bin, dialog)
    btn_llama = QtWidgets.QPushButton(tr(tile, "찾기"), dialog)
    llama_row = _line_with_button(dialog, edt_llama, btn_llama)
    form.addRow(tr(tile, "llama 실행 파일"), llama_row)

    edt_model = QtWidgets.QLineEdit(model_path, dialog)
    btn_model = QtWidgets.QPushButton(tr(tile, "찾기"), dialog)
    model_row = _line_with_button(dialog, edt_model, btn_model)
    form.addRow(tr(tile, "번역 모델 / ID"), model_row)

    hint = QtWidgets.QLabel(
        tr(tile, "로컬 GGUF 모델을 llama-server로 번역합니다. 원문/번역 언어와 모델 경로는 기억됩니다."),
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

    start_dir = tile._dialog_start_dir()

    def _pick_subtitle() -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            dialog,
            tr(tile, "자막 파일 선택"),
            os.path.dirname(str(edt_sub.text() or "").strip()) or start_dir,
            _TRANSLATE_SUBTITLE_FILE_FILTER,
        )
        if path:
            edt_sub.setText(path)

    def _pick_llama() -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            dialog,
            tr(tile, "llama 실행 파일 선택"),
            os.path.dirname(str(edt_llama.text() or "").strip()) or start_dir,
            "Executable Files (*.exe);;All Files (*)",
        )
        if path:
            edt_llama.setText(path)

    def _pick_model() -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            dialog,
            tr(tile, "번역 모델 선택"),
            os.path.dirname(str(edt_model.text() or "").strip()) or start_dir,
            "GGUF Files (*.gguf);;All Files (*)",
        )
        if path:
            edt_model.setText(path)

    btn_sub.clicked.connect(_pick_subtitle)
    btn_llama.clicked.connect(_pick_llama)
    btn_model.clicked.connect(_pick_model)

    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None

    subtitle_path = os.path.abspath(str(edt_sub.text() or "").strip())
    llama_path = os.path.abspath(str(edt_llama.text() or "").strip())
    model_path = _normalize_model_reference(str(edt_model.text() or "").strip())
    source_lang = str(cmb_source.currentData() or "auto").strip() or "auto"
    target_lang = str(cmb_lang.currentData() or _DEFAULT_TRANSLATE_TARGET).strip() or _DEFAULT_TRANSLATE_TARGET
    if not subtitle_path or not os.path.isfile(subtitle_path):
        QtWidgets.QMessageBox.warning(tile, tr(tile, "자막 번역"), tr(tile, "원본 자막 파일을 찾을 수 없습니다."))
        return None
    if not _is_supported_subtitle_path(subtitle_path):
        QtWidgets.QMessageBox.warning(
            tile,
            tr(tile, "자막 번역"),
            tr(tile, "현재 자막 번역은 SRT 파일만 지원합니다."),
        )
        return None
    if not llama_path or not os.path.isfile(llama_path):
        QtWidgets.QMessageBox.warning(tile, tr(tile, "자막 번역"), tr(tile, "llama 실행 파일을 찾을 수 없습니다."))
        return None
    if not model_path or not os.path.isfile(model_path):
        QtWidgets.QMessageBox.warning(tile, tr(tile, "자막 번역"), tr(tile, "번역 모델 GGUF를 찾을 수 없습니다."))
        return None

    out_path = _default_translated_output_path(subtitle_path, target_lang)
    if mainwin is not None:
        mainwin.config[_LLAMA_CONFIG_BIN] = llama_path
        mainwin.config[_LLAMA_CONFIG_MODEL] = model_path
        mainwin.config[_LLAMA_CONFIG_SOURCE] = source_lang
        mainwin.config[_LLAMA_CONFIG_TARGET] = target_lang
        mainwin.config[_LLAMA_CONFIG_LAST_SUBTITLE] = subtitle_path
        _save_main_config(mainwin)
    return {
        "media_path": media_path,
        "subtitle_path": subtitle_path,
        "out_path": out_path,
        "llama_path": llama_path,
        "model_path": model_path,
        "source_lang": source_lang,
        "target_lang": target_lang,
    }


def _line_with_button(parent, line_edit, button):
    wrapper = QtWidgets.QWidget(parent)
    layout = QtWidgets.QHBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(line_edit, 1)
    layout.addWidget(button)
    return wrapper


def _language_name(code: str, *, localized: bool) -> str:
    mapping = _LANGUAGE_NAME_LOCALIZED if localized else _LANGUAGE_NAME_EN
    key = str(code or "").strip().lower()
    return mapping.get(key, str(code or "").strip() or "en")


def _subtitle_extension(path: str) -> str:
    return Path(str(path or "").strip()).suffix.lower()


def _is_supported_subtitle_path(path: str) -> bool:
    return _subtitle_extension(path) in _SUPPORTED_TRANSLATE_SUBTITLE_EXTENSIONS


def _ensure_supported_subtitle_path(path: str) -> None:
    if _is_supported_subtitle_path(path):
        return
    supported = ", ".join(sorted(ext.lstrip(".") for ext in _SUPPORTED_TRANSLATE_SUBTITLE_EXTENSIONS))
    raise RuntimeError(f"지원하지 않는 자막 형식입니다: {path} (지원: {supported})")


def _translation_language_items(tile, *, include_auto: bool) -> list[tuple[str, str]]:
    items = []
    if include_auto:
        items.append(("auto", tr(tile, "자동 감지")))
    items.extend([
        ("ko", tr(tile, "한국어")),
        ("en", tr(tile, "영어")),
        ("ja", tr(tile, "일본어")),
        ("zh", tr(tile, "중국어")),
    ])
    return items


def _default_source_subtitle_path(tile, media_path: str, config: dict) -> str:
    current = ""
    if media_path:
        try:
            current = str(tile.get_external_subtitle_for_path(media_path) or "").strip()
        except Exception:
            current = ""
    if current and os.path.isfile(current):
        return os.path.abspath(current)
    if media_path:
        candidate = os.path.splitext(media_path)[0] + ".autogen.srt"
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    remembered = str(config.get(_LLAMA_CONFIG_LAST_SUBTITLE, "") or "").strip()
    if remembered and os.path.isfile(remembered):
        return os.path.abspath(remembered)
    return ""


def _resolve_default_llama_bin(config: dict) -> str:
    override = str(os.environ.get("MULTIPLAY_LLAMA_BIN") or "").strip()
    if override and os.path.isfile(override):
        return os.path.abspath(override)
    configured = str(config.get(_LLAMA_CONFIG_BIN, "") or "").strip()
    if configured and os.path.isfile(configured):
        return os.path.abspath(configured)
    for raw in (shutil.which("llama-server"), shutil.which("llama-server.exe"), shutil.which("llama-cli.exe"), shutil.which("llama-cli")):
        if raw and os.path.isfile(raw):
            return os.path.abspath(raw)
    return ""


def _resolve_default_model_path(config: dict) -> str:
    override = str(os.environ.get("MULTIPLAY_TRANSLATE_MODEL") or os.environ.get("MULTIPLAY_TRANSLATE_GGUF") or "").strip()
    if override:
        normalized = _normalize_model_reference(override)
        if os.path.isfile(normalized) or normalized.lower().endswith(".gguf"):
            return normalized
    configured = str(config.get(_LLAMA_CONFIG_MODEL, "") or "").strip()
    if configured:
        normalized = _normalize_model_reference(configured)
        if os.path.isfile(normalized) or normalized.lower().endswith(".gguf"):
            return normalized
    return ""


def _normalize_model_reference(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if os.path.exists(raw):
        return os.path.abspath(raw)
    return raw


def _default_translated_output_path(subtitle_path: str, target_lang: str) -> str:
    base, ext = os.path.splitext(subtitle_path)
    suffix = str(target_lang or _DEFAULT_TRANSLATE_TARGET).strip().lower()
    return f"{base}.{suffix}{ext or '.srt'}"


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


def _run_translation_job(job: dict, worker: SubtitleTranslationWorker) -> dict:
    subtitle_path = str(job.get("subtitle_path") or "").strip()
    out_path = str(job.get("out_path") or "").strip()
    llama_path = str(job.get("llama_path") or "").strip()
    model_path = str(job.get("model_path") or "").strip()
    source_lang = str(job.get("source_lang") or "auto").strip() or "auto"
    target_lang = str(job.get("target_lang") or _DEFAULT_TRANSLATE_TARGET).strip() or _DEFAULT_TRANSLATE_TARGET
    started_at = time.monotonic()

    cues = _parse_srt(subtitle_path)
    if not cues:
        raise RuntimeError("번역할 자막 cue를 찾지 못했습니다.")
    progress_state = {
        "processed": 0,
        "total": len(cues),
        "started_at": started_at,
    }
    initial_chunk = _TRANSLATE_CHUNK_LADDER[0]
    worker._initial_chunk_size = initial_chunk
    worker.report_progress(
        processed=0,
        total=len(cues),
        chunk_size=initial_chunk,
        stage="모델 로드 중",
        started_at=started_at,
    )
    os.makedirs(os.path.dirname(out_path) or os.getcwd(), exist_ok=True)
    _ensure_supported_subtitle_path(subtitle_path)
    server_bin = _resolve_server_bin(llama_path)
    if not server_bin:
        raise RuntimeError("llama-server 실행 파일을 찾을 수 없습니다.")
    port = _pick_free_port()
    proc = _start_llama_server(server_bin, model_path, port, worker)
    worker._server_proc = proc
    try:
        try:
            _wait_for_server(port, worker, total_cues=len(cues))
            worker.report_progress(
                processed=0,
                total=len(cues),
                chunk_size=initial_chunk,
                stage="프롬프트 워밍업 중",
                started_at=started_at,
            )
            _warmup_generic_slot(port, target_lang)
            worker.report_progress(
                processed=0,
                total=len(cues),
                chunk_size=initial_chunk,
                stage="번역 중",
                started_at=started_at,
            )
            translated = _translate_cues_via_server(
                cues,
                port,
                target_lang,
                worker,
                progress_state,
                partial_out_path=out_path,
            )
        except Exception as exc:
            raise RuntimeError(_with_server_log_detail(str(exc or ""), worker))
    finally:
        _stop_server(proc)
        worker._server_proc = None
        _close_server_log(worker)
    out_path = _write_srt(out_path, translated)
    elapsed_seconds = max(0.0, time.monotonic() - started_at)
    return {
        "media_path": str(job.get("media_path") or ""),
        "subtitle_path": subtitle_path,
        "out_path": out_path,
        "target_lang": target_lang,
        "elapsed_seconds": elapsed_seconds,
        "total": len(cues),
        "processed": len(translated),
    }


def _resolve_server_bin(llama_path: str) -> str:
    if not llama_path:
        return ""
    path = Path(llama_path)
    if path.is_file() and path.name.lower() in {"llama-server", "llama-server.exe"}:
        return str(path)
    for candidate_name in ("llama-server.exe", "llama-server"):
        sibling = path.with_name(candidate_name)
        if sibling.is_file():
            return str(sibling)
    return ""


def _pick_free_port() -> int:
    for port in range(_DEFAULT_SERVER_PORT, _DEFAULT_SERVER_PORT + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("사용 가능한 llama-server 포트를 찾지 못했습니다.")


def _start_llama_server(
    server_bin: str,
    model_path: str,
    port: int,
    worker: SubtitleTranslationWorker,
) -> subprocess.Popen:
    env = os.environ.copy()
    env["PATH"] = _llama_runtime_path(server_bin, env.get("PATH", ""))
    handle, log_path = tempfile.mkstemp(prefix="multiplay-llama-", suffix=".log")
    os.close(handle)
    log_handle = open(log_path, "wb")
    worker._server_log_path = log_path
    worker._server_log_handle = log_handle
    command = [
        server_bin,
        "-m",
        model_path,
        "--port",
        str(port),
        "-ngl",
        "99",
        "-c",
        str(_LLAMA_SERVER_CONTEXT),
        "-np",
        "1",
        "--no-webui",
    ]
    return subprocess.Popen(
        command,
        stdout=log_handle,
        stderr=log_handle,
        env=env,
        **hidden_subprocess_kwargs(),
    )


def _llama_runtime_path(server_bin: str, current_path: str) -> str:
    parts = []
    server_dir = os.path.dirname(server_bin)
    if server_dir:
        parts.append(server_dir)
    for parent in Path(server_bin).resolve().parents:
        torch_lib = parent / "Lib" / "site-packages" / "torch" / "lib"
        if torch_lib.is_dir():
            parts.append(str(torch_lib))
            break
    existing = [part for part in str(current_path or "").split(os.pathsep) if part]
    merged: list[str] = []
    seen: set[str] = set()
    for part in parts + existing:
        norm = os.path.normcase(os.path.abspath(part))
        if norm in seen:
            continue
        seen.add(norm)
        merged.append(part)
    return os.pathsep.join(merged)


def _read_server_log_tail(worker: SubtitleTranslationWorker, limit_chars: int = 4000) -> str:
    path = str(getattr(worker, "_server_log_path", "") or "").strip()
    handle = getattr(worker, "_server_log_handle", None)
    if handle is not None:
        try:
            handle.flush()
        except Exception:
            pass
    if not path or not os.path.isfile(path):
        return ""
    try:
        raw = Path(path).read_bytes()
    except Exception:
        return ""
    text = raw.decode("utf-8", "replace").strip()
    if not text:
        return ""
    if len(text) <= int(limit_chars):
        return text
    return text[-int(limit_chars):].lstrip()


def _close_server_log(worker: SubtitleTranslationWorker) -> None:
    handle = getattr(worker, "_server_log_handle", None)
    path = str(getattr(worker, "_server_log_path", "") or "").strip()
    worker._server_log_handle = None
    worker._server_log_path = ""
    if handle is not None:
        try:
            handle.close()
        except Exception:
            pass
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


def _with_server_log_detail(message: str, worker: SubtitleTranslationWorker) -> str:
    base = str(message or "").strip() or "llama-server 실행 실패"
    tail = _read_server_log_tail(worker)
    if not tail:
        return base
    return f"{base}\n\nstderr tail:\n{tail}"


def _wait_for_server(port: int, worker: SubtitleTranslationWorker, *, total_cues: int = 0) -> None:
    deadline = time.time() + 30.0
    last_error = ""
    url = f"http://127.0.0.1:{port}/v1/models"
    last_progress_at = 0.0
    while time.time() < deadline:
        if worker._stop_requested:
            raise RuntimeError("사용자 취소")
        now = time.monotonic()
        if now - last_progress_at >= 0.75:
            worker.report_progress(
                processed=0,
                total=total_cues,
                chunk_size=int(getattr(worker, "_initial_chunk_size", _TRANSLATE_CHUNK_LADDER[0]) or _TRANSLATE_CHUNK_LADDER[0]),
                stage="모델 로드 중",
            )
            last_progress_at = now
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if int(getattr(response, "status", 200) or 200) < 500:
                    return
        except Exception as exc:
            proc = getattr(worker, "_server_proc", None)
            if proc is not None and proc.poll() is not None:
                exit_code = int(proc.returncode or 0)
                tail = _read_server_log_tail(worker)
                detail = f"llama-server 종료(code={exit_code})"
                if tail:
                    detail += f"\n\nstderr tail:\n{tail}"
                raise RuntimeError(detail)
            last_error = str(exc or "")
            time.sleep(0.35)
    raise RuntimeError(last_error or "llama-server가 준비되지 않았습니다.")


def _translate_cues_via_server(
    cues: list[SubtitleCue],
    port: int,
    target_lang: str,
    worker: SubtitleTranslationWorker,
    progress_state: dict,
    *,
    partial_out_path: str = "",
) -> list[SubtitleCue]:
    return _translate_cues_via_generic_server(
        cues,
        port,
        target_lang,
        worker,
        progress_state,
        partial_out_path=partial_out_path,
    )


def _translate_cues_via_generic_server(
    cues: list[SubtitleCue],
    port: int,
    target_lang: str,
    worker: SubtitleTranslationWorker,
    progress_state: dict,
    *,
    partial_out_path: str = "",
) -> list[SubtitleCue]:
    translated: list[SubtitleCue] = []
    worker.report_progress(
        processed=int(progress_state.get("processed") or 0),
        total=int(progress_state.get("total") or 0),
        chunk_size=1,
        stage="번역 중",
        started_at=float(progress_state.get("started_at") or time.monotonic()),
    )
    for cue in cues:
        if worker._stop_requested:
            raise RuntimeError("사용자 취소")
        item = _translate_single(cue, port, target_lang, slot_id=_LLAMA_SLOT_ID)
        translated.append(item)
        _report_translation_progress(worker, progress_state, 1, 1)
        if partial_out_path:
            _flush_partial_translation(partial_out_path, cues, translated)
    return translated

def _translate_generic_cue_range_adaptive(
    cues: list[SubtitleCue],
    port: int,
    target_lang: str,
    worker: SubtitleTranslationWorker,
    ladder_index: int,
    progress_state: dict,
    *,
    slot_id: Optional[int] = None,
) -> list[SubtitleCue]:
    if worker._stop_requested:
        raise RuntimeError("사용자 취소")
    if not cues:
        return []
    ladder = _TRANSLATE_CHUNK_LADDER
    if ladder_index >= len(ladder):
        ladder_index = len(ladder) - 1
    chunk_size = max(1, int(ladder[ladder_index]))
    if len(cues) <= chunk_size:
        items, failure_reason = _translate_preserve_srt_group(cues, port, target_lang, slot_id=slot_id)
        if items:
            _report_translation_progress(worker, progress_state, len(items), chunk_size)
            return items
        if chunk_size == 1:
            cue = cues[0]
            items = [_translate_single(cue, port, target_lang, slot_id=slot_id)]
            _report_translation_progress(worker, progress_state, len(items), 1)
            return items
        _report_retry_progress(worker, progress_state, chunk_size, failure_reason)
        next_index = min(ladder_index + 1, len(ladder) - 1)
        midpoint = max(1, len(cues) // 2)
        left = _translate_generic_cue_range_adaptive(
            cues[:midpoint],
            port,
            target_lang,
            worker,
            next_index,
            progress_state,
            slot_id=slot_id,
        )
        right = _translate_generic_cue_range_adaptive(
            cues[midpoint:],
            port,
            target_lang,
            worker,
            next_index,
            progress_state,
            slot_id=slot_id,
        )
        return left + right
    translated: list[SubtitleCue] = []
    for start in range(0, len(cues), chunk_size):
        if worker._stop_requested:
            raise RuntimeError("사용자 취소")
        batch = cues[start : start + chunk_size]
        translated.extend(
            _translate_generic_cue_range_adaptive(
                batch,
                port,
                target_lang,
                worker,
                ladder_index,
                progress_state,
                slot_id=slot_id,
            )
        )
    return translated


def _report_translation_progress(
    worker: SubtitleTranslationWorker,
    progress_state: dict,
    completed_count: int,
    chunk_size: int,
) -> None:
    progress_state["processed"] = int(progress_state.get("processed") or 0) + max(0, int(completed_count))
    processed = min(int(progress_state["processed"]), int(progress_state.get("total") or 0))
    progress_state["processed"] = processed
    worker.report_progress(
        processed=processed,
        total=int(progress_state.get("total") or 0),
        chunk_size=chunk_size,
        stage="번역 중",
        started_at=float(progress_state.get("started_at") or time.monotonic()),
    )


def _report_retry_progress(
    worker: SubtitleTranslationWorker,
    progress_state: dict,
    chunk_size: int,
    failure_reason: str,
) -> None:
    worker.report_progress(
        processed=int(progress_state.get("processed") or 0),
        total=int(progress_state.get("total") or 0),
        chunk_size=chunk_size,
        stage="재시도",
        started_at=float(progress_state.get("started_at") or time.monotonic()),
        note=str(failure_reason or "").strip() or "배치 실패",
    )


def _split_generic_cues_by_token_budget(
    cues: list[SubtitleCue],
    port: int,
    target_lang: str,
    *,
    token_budget: Optional[int] = None,
    max_chunk_cues: int = _GENERIC_MAX_CHUNK_CUES,
) -> list[list[SubtitleCue]]:
    if not cues:
        return []
    effective_budget = max(
        1200,
        int((token_budget or _generic_input_token_budget()) * float(_GENERIC_TOKEN_ESTIMATE_SAFETY_MARGIN)),
    )
    estimator = _build_generic_token_estimator(cues, port, target_lang)
    current: list[SubtitleCue] = []
    current_tokens = estimator.prefix_tokens
    chunks: list[list[SubtitleCue]] = []
    for cue in cues:
        cue_tokens = estimator.item_tokens(cue)
        tentative_tokens = current_tokens + cue_tokens + (estimator.separator_tokens if current else 0)
        if current and (tentative_tokens > effective_budget or len(current) >= int(max_chunk_cues)):
            chunks.append(current)
            current = [cue]
            current_tokens = estimator.prefix_tokens + cue_tokens
            continue
        if current:
            current_tokens += estimator.separator_tokens
        current.append(cue)
        current_tokens += cue_tokens
    if current:
        chunks.append(current)
    return chunks


def _generic_input_token_budget() -> int:
    return max(
        1200,
        min(
            int(_GENERIC_INPUT_TOKEN_BUDGET_CAP),
            int(_LLAMA_SERVER_CONTEXT) - int(_GENERIC_OUTPUT_TOKEN_RESERVE) - int(_GENERIC_TOKEN_HEADROOM),
        ),
    )


def _sample_cues_for_token_estimation(cues: list[SubtitleCue], limit: int) -> list[SubtitleCue]:
    count = max(0, int(limit))
    if count <= 0 or not cues:
        return []
    if len(cues) <= count:
        return list(cues)
    selected: list[SubtitleCue] = []
    seen: set[int] = set()

    def _append(cue: SubtitleCue) -> None:
        if cue.index in seen:
            return
        seen.add(cue.index)
        selected.append(cue)

    head_count = max(1, count // 2)
    for cue in cues[:head_count]:
        _append(cue)
        if len(selected) >= count:
            return selected
    ranked = sorted(cues, key=lambda cue: len(str(cue.text or '').encode('utf-8')), reverse=True)
    for cue in ranked:
        _append(cue)
        if len(selected) >= count:
            break
    return selected


def _rough_token_estimate(text: str) -> int:
    value = str(text or '')
    if not value:
        return 1
    ascii_count = 0
    non_ascii_count = 0
    punctuation_bonus = 0
    for char in value:
        if ord(char) < 128:
            ascii_count += 1
            if not (char.isalnum() or char.isspace()):
                punctuation_bonus += 1
        else:
            non_ascii_count += 1
    estimate = (ascii_count / 3.6) + (non_ascii_count * 1.15) + (punctuation_bonus * 0.15)
    return max(1, int(math.ceil(estimate)))


def _build_generic_token_estimator(cues: list[SubtitleCue], port: int, target_lang: str) -> _GenericTokenEstimator:
    prefix_text = _generic_completion_prefix(target_lang) + "Input JSON:\n[]"
    prefix_tokens = _rough_token_estimate(prefix_text)
    separator_tokens = 1
    sampled_item_tokens: dict[int, int] = {}
    scale = 1.25
    try:
        prefix_tokens = _tokenize_count(port, prefix_text)
        separator_tokens = max(1, _tokenize_count(port, ','))
        scale_candidates = [1.0]
        for cue in _sample_cues_for_token_estimation(cues, _GENERIC_TOKENIZE_SAMPLE_LIMIT):
            item_text = _generic_structured_item_text(cue)
            actual_tokens = _tokenize_count(port, item_text)
            sampled_item_tokens[cue.index] = actual_tokens
            rough_tokens = _rough_token_estimate(item_text)
            if rough_tokens > 0:
                scale_candidates.append(float(actual_tokens) / float(rough_tokens))
        scale = max(scale_candidates) * 1.10
    except Exception:
        pass
    scale = max(1.05, min(float(scale), float(_GENERIC_TOKEN_ESTIMATE_MAX_SCALE)))
    return _GenericTokenEstimator(
        prefix_tokens=max(1, int(prefix_tokens)),
        separator_tokens=max(1, int(separator_tokens)),
        scale=scale,
        sampled_item_tokens=sampled_item_tokens,
    )


def _response_text_token_budget(text: str) -> int:
    cleaned = str(text or "").replace("\n", " / ").strip()
    if not cleaned:
        return 12
    return max(12, _rough_token_estimate(cleaned) * 2)


def _batch_completion_max_tokens(batch: list[SubtitleCue], *, structured: bool) -> int:
    if not batch:
        return 256
    total = 32
    per_item_overhead = 16 if structured else 8
    lower_bound = 256 if len(batch) <= 2 else 384
    upper_bound = 6144 if structured else 4096
    for cue in batch:
        total += _response_text_token_budget(cue.text)
        total += per_item_overhead
    return max(lower_bound, min(upper_bound, int(total)))


def _single_completion_max_tokens(text: str) -> int:
    return max(96, min(384, _response_text_token_budget(text) + 32))


def _tokenize_count(port: int, text: str) -> int:
    payload = _tokenize_payload_request(port, text)
    if isinstance(payload, list):
        return max(1, len(payload))
    if isinstance(payload, dict):
        for key in ("tokens", "token_ids", "ids"):
            value = payload.get(key)
            if isinstance(value, list):
                return max(1, len(value))
        for key in ("n_tokens", "count", "length"):
            value = payload.get(key)
            if isinstance(value, int):
                return max(1, value)
    return max(1, len(str(text or "")) // 4)


def _post_json_request(url: str, body: dict, *, timeout: float):
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(detail or str(exc))


def _tokenize_payload_request(port: int, text: str):
    global _tokenize_body_key_hint
    candidate_keys = [_tokenize_body_key_hint] if _tokenize_body_key_hint else []
    candidate_keys += [key for key in _TOKENIZE_BODY_KEYS if key not in candidate_keys]
    last_error = None
    for key in candidate_keys:
        if not key:
            continue
        try:
            payload = _post_json_request(
                f"http://127.0.0.1:{port}/tokenize",
                {key: str(text or "")},
                timeout=10.0,
            )
            _tokenize_body_key_hint = key
            return payload
        except Exception as exc:
            last_error = exc
            continue
    raise RuntimeError(str(last_error or "tokenize 요청 실패"))


def _warmup_generic_slot(port: int, target_lang: str) -> None:
    try:
        _completion_payload_request(
            port,
            prompt=_generic_completion_prefix(target_lang),
            temperature=0.0,
            max_tokens=0,
            stop=[],
            id_slot=_LLAMA_SLOT_ID,
            cache_prompt=True,
            seed=_GENERIC_TRANSLATE_SEED,
        )
    except Exception:
        pass


def _translate_preserve_srt_group(
    batch: list[SubtitleCue],
    port: int,
    target_lang: str,
    *,
    slot_id: Optional[int] = None,
) -> tuple[list[SubtitleCue], str]:
    items, reason = _translate_batch_generic_json(batch, port, target_lang, slot_id=slot_id)
    if items:
        return items, ""
    if len(batch) > int(_GENERIC_TSV_FALLBACK_MAX_BATCH):
        return [], reason or "TSV fallback 제한"
    items, tsv_reason = _translate_batch_generic_tsv(batch, port, target_lang)
    if items:
        return items, ""
    return [], tsv_reason or reason or "배치 실패"


def _translate_batch_generic_json(
    batch: list[SubtitleCue],
    port: int,
    target_lang: str,
    *,
    slot_id: Optional[int] = None,
) -> tuple[list[SubtitleCue], str]:
    try:
        payload = _completion_payload_request(
            port,
            prompt=_generic_structured_prompt(batch, target_lang),
            temperature=0.1,
            max_tokens=_batch_completion_max_tokens(batch, structured=True),
            stop=["\n\n\n", "<end_of_turn>", "</s>"],
            json_schema=_generic_batch_json_schema(len(batch)),
            id_slot=slot_id,
            cache_prompt=True,
            seed=_GENERIC_TRANSLATE_SEED,
            top_k=20,
            top_p=0.9,
            timings_per_token=True,
        )
    except Exception:
        return [], "JSON 요청 실패"
    if bool(payload.get("truncated")):
        return [], "JSON 응답 잘림"
    rows = _parse_json_batch_response(payload.get("content"))
    if len(rows) != len(batch):
        return [], "JSON parse 실패"
    expected_ids = [cue.index for cue in batch]
    actual_ids = [row_id for row_id, _ in rows]
    if actual_ids != expected_ids:
        return [], "id 불일치"
    if _looks_untranslated_batch(batch, rows, target_lang):
        return [], "원문 잔존"
    out: list[SubtitleCue] = []
    for cue, (_row_id, text) in zip(batch, rows):
        out.append(SubtitleCue(index=cue.index, start=cue.start, end=cue.end, text=text or cue.text))
    return out, ""


def _translate_batch_generic_tsv(batch: list[SubtitleCue], port: int, target_lang: str) -> tuple[list[SubtitleCue], str]:
    try:
        response = _chat_completion(
            port,
            system_prompt=_system_translate_prompt(target_lang, preserve_srt=True),
            user_prompt=_generic_batch_prompt(batch, target_lang),
            temperature=0.1,
            max_tokens=_batch_completion_max_tokens(batch, structured=False),
        )
    except Exception:
        return [], "TSV 요청 실패"
    rows = _parse_batch_response(response)
    if len(rows) != len(batch):
        return [], "TSV parse 실패"
    expected_ids = [cue.index for cue in batch]
    actual_ids = [row_id for row_id, _ in rows]
    if actual_ids != expected_ids:
        return [], "id 불일치"
    if _looks_untranslated_batch(batch, rows, target_lang):
        return [], "원문 잔존"
    out: list[SubtitleCue] = []
    for cue, (_row_id, text) in zip(batch, rows):
        out.append(SubtitleCue(index=cue.index, start=cue.start, end=cue.end, text=text or cue.text))
    return out, ""


def _translate_single(
    cue: SubtitleCue,
    port: int,
    target_lang: str,
    *,
    slot_id: Optional[int] = None,
) -> SubtitleCue:
    text = ""
    try:
        text = _cleanup_model_text(
            _translate_single_generic_completion(cue.text, port, target_lang, slot_id=slot_id)
        )
        if _looks_untranslated_text(cue.text, text, target_lang):
            text = ""
    except Exception:
        text = ""
    if not text:
        try:
            response = _chat_completion(
                port,
                system_prompt=_system_translate_prompt(target_lang, preserve_srt=False),
                user_prompt=_single_prompt(cue.text, target_lang),
                temperature=0.1,
                max_tokens=_single_completion_max_tokens(cue.text),
            )
            text = _cleanup_model_text(response)
            if _looks_untranslated_text(cue.text, text, target_lang):
                text = ""
        except Exception:
            text = ""
    return SubtitleCue(index=cue.index, start=cue.start, end=cue.end, text=text or cue.text)



def _translate_single_generic_completion(
    text: str,
    port: int,
    target_lang: str,
    *,
    slot_id: Optional[int] = None,
) -> str:
    return _completion_request(
        port,
        prompt=_single_completion_prompt(text, target_lang),
        temperature=0.1,
        max_tokens=_single_completion_max_tokens(text),
        stop=["\n\n", "<end_of_turn>", "</s>"],
        id_slot=slot_id,
        cache_prompt=True,
        seed=_GENERIC_TRANSLATE_SEED,
        top_k=20,
        top_p=0.9,
    )


def _chat_completion(port: int, *, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int) -> str:
    payload = _post_json_request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        },
        timeout=_TRANSLATE_REQUEST_TIMEOUT,
    )
    choice = (((payload.get("choices") or [{}])[0]).get("message") or {}).get("content")
    return str(choice or "").strip()


def _completion_payload_request(
    port: int,
    *,
    prompt: str,
    temperature: float,
    max_tokens: int,
    stop: list[str],
    id_slot: Optional[int] = None,
    cache_prompt: Optional[bool] = None,
    seed: Optional[int] = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    json_schema: Optional[dict] = None,
    timings_per_token: Optional[bool] = None,
) -> dict:
    body = {
        "prompt": prompt,
        "temperature": float(temperature),
        "n_predict": int(max_tokens),
        "stop": list(stop or []),
    }
    if id_slot is not None:
        body["id_slot"] = int(id_slot)
    if cache_prompt is not None:
        body["cache_prompt"] = bool(cache_prompt)
    if seed is not None:
        body["seed"] = int(seed)
    if top_k is not None:
        body["top_k"] = int(top_k)
    if top_p is not None:
        body["top_p"] = float(top_p)
    if json_schema is not None:
        body["json_schema"] = dict(json_schema)
    if timings_per_token is not None:
        body["timings_per_token"] = bool(timings_per_token)
    payload = _post_json_request(
        f"http://127.0.0.1:{port}/completion",
        body,
        timeout=_TRANSLATE_REQUEST_TIMEOUT,
    )
    return dict(payload or {})


def _completion_request(
    port: int,
    *,
    prompt: str,
    temperature: float,
    max_tokens: int,
    stop: list[str],
    id_slot: Optional[int] = None,
    cache_prompt: Optional[bool] = None,
    seed: Optional[int] = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    json_schema: Optional[dict] = None,
    timings_per_token: Optional[bool] = None,
) -> str:
    payload = _completion_payload_request(
        port,
        prompt=prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        stop=stop,
        id_slot=id_slot,
        cache_prompt=cache_prompt,
        seed=seed,
        top_k=top_k,
        top_p=top_p,
        json_schema=json_schema,
        timings_per_token=timings_per_token,
    )
    return str(payload.get("content") or "").strip()


def _system_translate_prompt(target_lang: str, *, preserve_srt: bool) -> str:
    language_name = _language_name(target_lang, localized=False)
    if preserve_srt:
        return (
            f"Translate subtitle items into natural {language_name}. "
            "Do not think step by step. Do not show reasoning. "
            "Return ONLY one TSV line per item in the same order. "
            "Format: <id>\\t<translated text>. "
            "Do not add explanations."
        )
    return (
        f"Translate the subtitle line into natural {language_name}. "
        "Do not think step by step. Do not show reasoning. "
        "Return only the translated subtitle text. "
        "Do not add explanations."
    )


def _generic_completion_prefix(target_lang: str) -> str:
    language_name = _language_name(target_lang, localized=False)
    return (
        f"You are a subtitle translator. Translate each item's text into natural {language_name}. "
        "Do not think step by step. Do not expose reasoning or analysis. "
        "Return JSON only. Keep the same item count, ids, and order. "
        "Do not merge, split, summarize, omit, or explain. "
        "Keep subtitle wording concise and readable.\n\n"
    )


def _generic_batch_json_schema(item_count: int) -> dict:
    return {
        "type": "array",
        "minItems": int(item_count),
        "maxItems": int(item_count),
        "items": {
            "type": "object",
            "required": ["id", "translation"],
            "additionalProperties": False,
            "properties": {
                "id": {"type": "integer"},
                "translation": {"type": "string"},
            },
        },
    }


def _generic_structured_item_text(cue: SubtitleCue) -> str:
    return json.dumps(
        {
            "id": cue.index,
            "text": _flatten_subtitle_text(cue.text),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _generic_structured_prompt(batch: list[SubtitleCue], target_lang: str) -> str:
    payload = []
    for cue in batch:
        payload.append(json.loads(_generic_structured_item_text(cue)))
    return _generic_completion_prefix(target_lang) + "Input JSON:\n" + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    )


def _generic_batch_prompt(batch: list[SubtitleCue], target_lang: str) -> str:
    language_name = _language_name(target_lang, localized=True)
    lines = [
        f"다음 자막 문장들을 {language_name}로 자연스럽게 번역해.",
        "생각 과정이나 해설은 쓰지 마.",
        "각 항목에 대해 한 줄씩만 출력해.",
        "형식: <id>\\t<translated text>",
        "번호는 그대로 유지하고 설명은 쓰지 마.",
        "",
    ]
    for cue in batch:
        text = _flatten_subtitle_text(cue.text)
        lines.append(f"{cue.index}\t{text}")
    return "\n".join(lines)


def _single_prompt(text: str, target_lang: str) -> str:
    language_name = _language_name(target_lang, localized=True)
    return (
        f"다음 자막 문장을 {language_name}로 자연스럽게 번역해.\n"
        "생각 과정이나 해설은 쓰지 마.\n"
        "설명 없이 번역문만 출력해.\n\n"
        + _flatten_subtitle_text(text)
    )


def _single_completion_prompt(text: str, target_lang: str) -> str:
    payload = {"text": _flatten_subtitle_text(text)}
    return _generic_completion_prefix(target_lang) + "Input JSON:\n" + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ) + "\n\nReturn only the translated text. No reasoning. No commentary."

def _strip_json_block(text: str) -> str:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _parse_json_batch_response(text: str) -> list[tuple[int, str]]:
    cleaned = _strip_json_block(text)
    if not cleaned:
        return []
    try:
        data = json.loads(cleaned)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: list[tuple[int, str]] = []
    for item in data:
        if not isinstance(item, dict):
            return []
        try:
            row_id = int(item.get("id"))
        except Exception:
            return []
        text_value = item.get("translation")
        if text_value is None:
            return []
        out.append((row_id, _cleanup_model_text(str(text_value))))
    return out


def _parse_batch_response(text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        line = line.strip("`")
        match = re.match(r"^(\d+)\s*[\t:|-]\s*(.+)$", line)
        if not match:
            continue
        out.append((int(match.group(1)), _cleanup_model_text(match.group(2))))
    return out


def _cleanup_model_text(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = cleaned.strip("`").strip()
    cleaned = re.sub(r"^\s*(translation|translated text)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*[a-z]{2}\s*\[sprt\]\s*[a-z]{2}\s*\[sprt\]", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def _flatten_subtitle_text(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    parts = [line.strip() for line in value.splitlines() if line.strip()]
    return " ".join(parts).strip()


def _normalized_compare_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).strip().lower()
    value = value.replace("\n", " ").replace("/", " ")
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"[`'\".,!?~\-\u3000、。・…]+", "", value)
    return value


def _count_hangul_chars(text: str) -> int:
    return len(re.findall(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3]", str(text or "")))


def _count_kana_chars(text: str) -> int:
    return len(re.findall(r"[\u3040-\u309f\u30a0-\u30ff\u31f0-\u31ff]", str(text or "")))


def _count_cjk_chars(text: str) -> int:
    return len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", str(text or "")))


def _looks_source_script_retained(source_text: str, translated_text: str, target_lang: str) -> bool:
    if _normalize_lang_code(target_lang) != "ko":
        return False
    source = str(source_text or "")
    translated = str(translated_text or "")
    source_japanese = _count_kana_chars(source) + _count_cjk_chars(source)
    if source_japanese < 2:
        return False
    translated_hangul = _count_hangul_chars(translated)
    translated_japanese = _count_kana_chars(translated) + _count_cjk_chars(translated)
    if translated_japanese < 2:
        return False
    if translated_hangul <= 0:
        return True
    return translated_japanese >= max(3, translated_hangul)


def _looks_untranslated_text(source_text: str, translated_text: str, target_lang: str) -> bool:
    source_norm = _normalized_compare_text(source_text)
    translated_norm = _normalized_compare_text(translated_text)
    if not source_norm or not translated_norm:
        return False
    if source_norm == translated_norm:
        return True
    shorter = min(len(source_norm), len(translated_norm))
    if shorter >= 4 and (
        translated_norm in source_norm or source_norm in translated_norm
    ) and _looks_source_script_retained(source_text, translated_text, target_lang):
        return True
    return _looks_source_script_retained(source_text, translated_text, target_lang)


def _looks_untranslated_batch(
    batch: list[SubtitleCue],
    rows: list[tuple[int, str]],
    target_lang: str,
) -> bool:
    suspicious = 0
    comparable = 0
    for cue, (_row_id, text) in zip(batch, rows):
        cleaned = _cleanup_model_text(text)
        source_norm = _normalized_compare_text(cue.text)
        translated_norm = _normalized_compare_text(cleaned)
        if not source_norm or not translated_norm:
            continue
        comparable += 1
        if _looks_untranslated_text(cue.text, cleaned, target_lang):
            suspicious += 1
    if comparable <= 0:
        return False
    normalized_target = _normalize_lang_code(target_lang)
    if normalized_target == "ko":
        threshold = 1 if comparable <= 8 else max(2, math.ceil(comparable * 0.25))
    else:
        threshold = max(2, math.ceil(comparable * 0.5))
    return suspicious >= threshold




def _normalize_lang_code(code: str) -> str:
    value = str(code or "").strip().lower()
    mapping = {
        "ko": "ko",
        "en": "en",
        "ja": "ja",
        "jp": "ja",
        "zh": "zh",
        "zh-cn": "zh",
        "zh-tw": "zh",
    }
    return mapping.get(value, value or "en")


def _read_subtitle_text(path: str) -> str:
    source = Path(path)
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr", "utf-16"):
        try:
            return source.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return source.read_text(encoding="utf-8", errors="replace")


def _parse_srt(path: str) -> list[SubtitleCue]:
    return _parse_srt_text(_read_subtitle_text(path))


def _parse_srt_text(raw: str) -> list[SubtitleCue]:
    blocks = re.split(r"\r?\n\r?\n+", raw.strip())
    cues: list[SubtitleCue] = []
    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        try:
            index = int(lines[0].strip())
        except ValueError:
            continue
        match = re.match(r"^(.*?)\s*-->\s*(.*?)$", lines[1].strip())
        if not match:
            continue
        text = "\n".join(lines[2:]).strip()
        if not text:
            continue
        cues.append(SubtitleCue(index=index, start=match.group(1).strip(), end=match.group(2).strip(), text=text))
    return cues


def _compose_partial_translation(all_cues: list[SubtitleCue], translated_prefix: list[SubtitleCue]) -> list[SubtitleCue]:
    translated_count = max(0, min(len(translated_prefix), len(all_cues)))
    if translated_count <= 0:
        return list(all_cues)
    return list(translated_prefix[:translated_count]) + list(all_cues[translated_count:])


def _flush_partial_translation(path: str, all_cues: list[SubtitleCue], translated_prefix: list[SubtitleCue]) -> None:
    if not path:
        return
    try:
        _write_srt(path, _compose_partial_translation(all_cues, translated_prefix), allow_fallback=False)
    except PermissionError:
        pass


def _fallback_output_path(path: str) -> str:
    target = Path(path)
    stem = target.stem
    suffix = target.suffix or ".srt"
    parent = target.parent
    for idx in range(1, 1000):
        candidate = parent / f"{stem} ({idx}){suffix}"
        if not candidate.exists():
            return str(candidate)
    return str(parent / f"{stem} ({int(time.time())}){suffix}")


def _write_srt(path: str, cues: list[SubtitleCue], *, allow_fallback: bool = True) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_path = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.stem}.",
        suffix=target.suffix or ".srt",
    )
    os.close(handle)
    try:
        Path(temp_path).write_text(_render_srt_block(cues).rstrip() + "\n", encoding="utf-8-sig")
        try:
            os.replace(temp_path, target)
            return str(target)
        except PermissionError:
            if not allow_fallback:
                raise
            fallback_path = _fallback_output_path(str(target))
            fallback_target = Path(fallback_path)
            os.replace(temp_path, fallback_target)
            return str(fallback_target)
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise


def _render_srt_block(cues: list[SubtitleCue]) -> str:
    lines: list[str] = []
    for cue in cues:
        lines.extend(
            [
                str(cue.index),
                f"{cue.start} --> {cue.end}",
                str(cue.text or "").strip(),
                "",
            ]
        )
    return "\n".join(lines)


def _stop_server(proc: subprocess.Popen) -> None:
    try:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
