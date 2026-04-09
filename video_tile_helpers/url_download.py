from __future__ import annotations

import glob
import importlib.util
import os
import shutil
import subprocess
import sys
import weakref
from typing import Optional

from PyQt6 import QtCore, QtWidgets

from i18n import tr
from process_utils import hidden_subprocess_kwargs
from .url_download_dialog import ask_url_save_options, remember_url_save_options
from .export_worker import _tile_export_busy_changed
from .url_download_languages import DEFAULT_URL_SUBTITLE_LANGUAGE, normalize_url_subtitle_language
from .url_download_switch import switch_tile_to_saved_media
from url_media_resolver import has_yt_dlp_support, is_probably_url, media_source_display_name


_MEDIA_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".avi",
    ".ts",
    ".flv",
    ".m4a",
    ".aac",
    ".mp3",
    ".wav",
    ".ogg",
    ".opus",
    ".flac",
}
_SUBTITLE_EXTENSIONS = {".srt", ".vtt", ".ass", ".ssa", ".ttml", ".srv3", ".json3"}


class UrlDownloadWorker(QtCore.QThread):
    jobFinished = QtCore.pyqtSignal(object)
    jobFailed = QtCore.pyqtSignal(object)

    def __init__(self, job: dict, parent=None):
        super().__init__(parent)
        self._job = dict(job or {})
        self._proc: Optional[subprocess.Popen] = None
        self._stop_requested = False

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
        try:
            payload = _run_download_job(self._job, self)
        except Exception as exc:
            self.jobFailed.emit(
                {
                    "error": str(exc or "알 수 없는 오류"),
                    "out_path": str(self._job.get("save_dir") or ""),
                }
            )
            return
        self.jobFinished.emit(payload)


def save_url_from_context(tile) -> None:
    source = _current_url_source(tile)
    if not source:
        QtWidgets.QMessageBox.information(
            tile,
            tr(tile, "URL 저장"),
            tr(tile, "현재 URL/스트림 소스를 찾을 수 없습니다."),
        )
        return
    if bool(getattr(tile, "_export_worker_busy", False)):
        QtWidgets.QMessageBox.information(
            tile,
            tr(tile, "URL 저장"),
            tr(tile, "다른 저장 작업이 실행 중입니다."),
        )
        return
    if not has_yt_dlp_support():
        QtWidgets.QMessageBox.warning(
            tile,
            tr(tile, "URL 저장"),
            tr(tile, "yt-dlp가 필요합니다.\n\npip install yt-dlp"),
        )
        return
    options = ask_url_save_options(tile, source)
    if options is None:
        return
    remember_url_save_options(tile, options)
    _start_url_download(tile, source, options)


def stop_url_download_worker(tile) -> None:
    worker = getattr(tile, "_url_download_worker", None)
    tile._url_download_worker = None
    if worker is None:
        return
    try:
        worker.stop()
    except Exception:
        pass
    try:
        worker.wait(2000)
    except Exception:
        pass
    _tile_export_busy_changed(tile, False)


def _current_url_source(tile) -> str:
    try:
        if tile.playlist and 0 <= tile.current_index < len(tile.playlist):
            source = str(tile.playlist[tile.current_index] or "").strip()
            if is_probably_url(source):
                return source
    except Exception:
        return ""
    return ""


def _start_url_download(tile, source: str, options: dict) -> None:
    stop_url_download_worker(tile)
    job = dict(options or {})
    job["source"] = str(source or "").strip()
    worker = UrlDownloadWorker(job, parent=tile)
    tile_ref = weakref.ref(tile)
    worker.jobFinished.connect(lambda payload, ref=tile_ref: _dispatch_url_download_finished(ref, payload))
    worker.jobFailed.connect(lambda payload, ref=tile_ref: _dispatch_url_download_failed(ref, payload))
    tile._url_download_worker = worker
    _tile_export_busy_changed(tile, True)
    _status_text = tr(tile, "URL 저장 시작: {name}", name=media_source_display_name(source) or source)
    _show_status(tile, _status_text)
    worker.start()


def _dispatch_url_download_finished(tile_ref, payload: dict) -> None:
    tile = tile_ref()
    if tile is None:
        return
    tile._url_download_worker = None
    _tile_export_busy_changed(tile, False)
    out_path = str(payload.get("out_path") or "").strip()
    subtitle_paths = list(payload.get("subtitle_paths") or [])
    if out_path and subtitle_paths:
        try:
            from .playlist import set_external_subtitle_for_path

            set_external_subtitle_for_path(tile, out_path, subtitle_paths[0], overwrite=True)
        except Exception:
            pass
    switch_tile_to_saved_media(tile, payload)
    if out_path:
        try:
            tile._remember_dialog_dir(os.path.dirname(out_path))
        except Exception:
            pass
    subtitle_line = ""
    if subtitle_paths:
        subtitle_line = tr(tile, "\n자막 {count}개 함께 저장", count=len(subtitle_paths))
    subtitle_error = str(payload.get("subtitle_error") or "").strip()
    subtitle_warning = ""
    if subtitle_error and not subtitle_paths:
        subtitle_warning = tr(tile, "\n자막 저장은 건너뜀:\n{error}", error=subtitle_error)
    _show_status(tile, tr(tile, "URL 저장 완료: {path}", path=out_path or payload.get("save_dir", "")), timeout_ms=4000)
    QtWidgets.QMessageBox.information(
        tile,
        tr(tile, "완료"),
        tr(tile, "저장 완료:\n{path}", path=out_path or payload.get("save_dir", "")) + subtitle_line + subtitle_warning,
    )


def _dispatch_url_download_failed(tile_ref, payload: dict) -> None:
    tile = tile_ref()
    if tile is None:
        return
    tile._url_download_worker = None
    _tile_export_busy_changed(tile, False)
    error = str((payload or {}).get("error") or "알 수 없는 오류").strip()
    if error == "사용자 취소":
        _show_status(tile, tr(tile, "URL 저장 취소"), timeout_ms=3000)
        return
    QtWidgets.QMessageBox.critical(tile, tr(tile, "실패"), tr(tile, "URL 저장 실패:\n{error}", error=error))
    _show_status(tile, tr(tile, "URL 저장 실패"), timeout_ms=4000)


def _show_status(tile, text: str, timeout_ms: int = 2500) -> None:
    main = tile._main_window() if hasattr(tile, "_main_window") else None
    if main is None or not hasattr(main, "statusBar"):
        return
    try:
        main.statusBar().showMessage(str(text or ""), int(timeout_ms))
    except Exception:
        pass


def _run_download_job(job: dict, worker: UrlDownloadWorker) -> dict:
    source = str(job.get("source") or "").strip()
    if not source or not is_probably_url(source):
        raise RuntimeError("유효한 URL/스트림 소스가 없습니다.")
    save_dir = str(job.get("save_dir") or "").strip()
    if not save_dir:
        raise RuntimeError("저장 위치가 비어 있습니다.")
    os.makedirs(save_dir, exist_ok=True)
    started_at = float(QtCore.QDateTime.currentSecsSinceEpoch())
    command = _build_yt_dlp_command(job, include_subtitles=False, skip_download=False)
    stdout, stderr, return_code = _run_yt_dlp_command(command, worker)
    if int(return_code or 0) != 0:
        raise RuntimeError(_download_error_text(stdout, stderr, return_code))
    out_path = _detect_downloaded_media_path(stdout, save_dir, started_at)
    if not out_path:
        raise RuntimeError("저장된 파일 경로를 찾지 못했습니다.")
    subtitle_paths = _subtitle_paths_for_media(out_path)
    subtitle_error = ""
    if bool(job.get("download_subtitles", False)):
        subtitle_paths, subtitle_error = _download_subtitles_for_saved_media(job, out_path, worker)
    return {
        "out_path": out_path,
        "subtitle_paths": subtitle_paths,
        "subtitle_error": subtitle_error,
        "save_dir": save_dir,
        "source": source,
        "audio_only": bool(job.get("audio_only", False)),
    }


def _run_yt_dlp_command(command: list[str], worker: UrlDownloadWorker) -> tuple[str, str, int]:
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **hidden_subprocess_kwargs(),
    )
    worker._proc = proc
    try:
        stdout, stderr = proc.communicate()
    finally:
        worker._proc = None
    if worker._stop_requested:
        raise RuntimeError("사용자 취소")
    return stdout, stderr, int(proc.returncode or 0)


def _download_subtitles_for_saved_media(job: dict, out_path: str, worker: UrlDownloadWorker) -> tuple[list[str], str]:
    command = _build_yt_dlp_command(job, include_subtitles=True, skip_download=True)
    stdout, stderr, return_code = _run_yt_dlp_command(command, worker)
    subtitle_paths = _subtitle_paths_for_media(out_path)
    if subtitle_paths:
        return subtitle_paths, ""
    if int(return_code or 0) == 0:
        return [], ""
    return [], _download_error_text(stdout, stderr, return_code)


def _build_yt_dlp_command(
    job: dict,
    *,
    include_subtitles: bool,
    skip_download: bool,
) -> list[str]:
    source = str(job.get("source") or "").strip()
    save_dir = str(job.get("save_dir") or "").strip()
    audio_only = bool(job.get("audio_only", False))
    height = max(0, int(job.get("height", 0) or 0))
    subtitle_language = normalize_url_subtitle_language(str(job.get("subtitle_language") or ""))
    command = _yt_dlp_prefix()
    if not command:
        raise RuntimeError("yt-dlp 실행 경로를 찾지 못했습니다.")
    command.extend(
        [
            "--no-playlist",
            "--no-part",
            "--no-overwrites",
            "--newline",
            "-P",
            save_dir,
            "-o",
            "%(title).200B [%(id)s].%(ext)s",
            "--print",
            "after_move:filepath",
        ]
    )
    if skip_download:
        command.append("--skip-download")
    elif audio_only:
        command.extend(["-f", "bestaudio/best"])
    else:
        command.extend(["-f", _video_format_selector(height)])
        command.extend(["--merge-output-format", "mkv"])
    if include_subtitles:
        command.extend(
            [
                "--write-subs",
                "--write-auto-subs",
                "--sub-langs",
                subtitle_language,
                "--sub-format",
                "best",
            ]
        )
    command.append(source)
    return command


def _video_format_selector(height: int) -> str:
    if height <= 0:
        return "bestvideo*+bestaudio/best"
    return (
        f"bestvideo*[height<=?{int(height)}]+bestaudio/"
        f"best[height<=?{int(height)}]/best"
    )


def _yt_dlp_prefix() -> list[str]:
    executable = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    if executable:
        return [executable]
    if importlib.util.find_spec("yt_dlp") is not None:
        return [sys.executable, "-m", "yt_dlp"]
    return []


def _download_error_text(stdout: str, stderr: str, return_code: Optional[int]) -> str:
    for raw in reversed((stderr or "").splitlines()):
        text = str(raw or "").strip()
        if text:
            return text
    for raw in reversed((stdout or "").splitlines()):
        text = str(raw or "").strip()
        if text:
            return text
    return f"yt-dlp 실행이 실패했습니다. (exit code {int(return_code or 0)})"


def _detect_downloaded_media_path(stdout: str, save_dir: str, started_at: float) -> str:
    candidates = []
    for raw in (stdout or "").splitlines():
        text = str(raw or "").strip()
        if not text:
            continue
        if os.path.isfile(text) and _is_media_file(text):
            candidates.append(os.path.abspath(text))
    if candidates:
        return candidates[-1]
    recent_files = []
    try:
        for name in os.listdir(save_dir):
            path = os.path.join(save_dir, name)
            if not os.path.isfile(path) or not _is_media_file(path):
                continue
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if mtime >= float(started_at) - 5.0:
                recent_files.append((mtime, os.path.abspath(path)))
    except OSError:
        return ""
    recent_files.sort()
    return recent_files[-1][1] if recent_files else ""


def _is_media_file(path: str) -> bool:
    return os.path.splitext(str(path or "").lower())[1] in _MEDIA_EXTENSIONS


def _subtitle_paths_for_media(media_path: str) -> list[str]:
    if not media_path:
        return []
    base = os.path.splitext(media_path)[0]
    found: list[str] = []
    for path in glob.glob(base + ".*"):
        ext = os.path.splitext(str(path).lower())[1]
        if ext in _SUBTITLE_EXTENSIONS and os.path.isfile(path):
            found.append(os.path.abspath(path))
    found.sort()
    return found
