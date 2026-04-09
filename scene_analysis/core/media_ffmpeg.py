from __future__ import annotations

from typing import List, Optional
import logging
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
from process_utils import hidden_subprocess_kwargs

from PyQt6 import QtGui

try:
    from ffscene import FFMPEG_BIN as _EXISTING_BIN  # type: ignore

    FFMPEG_BIN = _EXISTING_BIN
except Exception:
    FFMPEG_BIN = "ffmpeg"


logger = logging.getLogger(__name__)


def ffmpeg_available(bin_path: str = "") -> bool:
    probe_bin = str(bin_path or "").strip()
    if not probe_bin:
        probe_bin = resolve_ffmpeg_bin()
    try:
        proc = subprocess.run(
            [probe_bin, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **hidden_subprocess_kwargs(),
        )
        return "ffmpeg version" in (proc.stdout + proc.stderr)
    except (OSError, ValueError, subprocess.SubprocessError):
        logger.debug("ffmpeg availability probe failed for %s", probe_bin, exc_info=True)
        return False


def _ffmpeg_bin_candidates(preferred: str = "") -> List[str]:
    candidates: List[str] = []
    _append_base_candidates(candidates, preferred)
    _append_python_candidates(candidates)
    _append_path_candidates(candidates)
    return _resolved_ffmpeg_candidates(candidates)


def resolve_ffmpeg_bin(preferred: str = "") -> str:
    candidates = _ffmpeg_bin_candidates(preferred)
    if candidates:
        return str(candidates[0])
    return str(preferred or FFMPEG_BIN or "ffmpeg")


def spawn_ffmpeg_iter(cmd_list):
    proc = subprocess.Popen(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **hidden_subprocess_kwargs(),
    )
    q = queue.Queue(maxsize=1000)
    stop = object()

    def _reader(stream):
        for line in iter(stream.readline, ""):
            q.put(line)
        q.put(stop)

    threading.Thread(target=_reader, args=(proc.stderr,), daemon=True).start()
    try:
        while True:
            line = q.get()
            if line is stop:
                break
            yield line
    finally:
        try:
            proc.wait(timeout=1)
        except (OSError, ValueError, subprocess.SubprocessError):
            logger.debug("ffmpeg iterator process wait skipped", exc_info=True)


def _which_ffmpeg():
    return resolve_ffmpeg_bin()


def _append_base_candidates(candidates: List[str], preferred: str) -> None:
    for value in (
        os.path.join(".", "ffmpeg", "bin", "ffmpeg.exe"),
        os.path.join(".", "vendor", "ffmpeg", "bin", "ffmpeg.exe"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
        r"C:\Tools\ffmpeg\bin\ffmpeg.exe",
        preferred,
        FFMPEG_BIN,
    ):
        _push_candidate(candidates, value)


def _append_python_candidates(candidates: List[str]) -> None:
    try:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable or ""))
    except (OSError, TypeError, ValueError):
        logger.debug("python executable directory probe failed for ffmpeg candidates", exc_info=True)
        exe_dir = ""
    if not exe_dir:
        return
    for value in (
        os.path.join(exe_dir, "ffmpeg.exe"),
        os.path.join(exe_dir, "ffmpeg"),
        os.path.join(exe_dir, "Library", "bin", "ffmpeg.exe"),
        os.path.join(exe_dir, "Library", "bin", "ffmpeg"),
        os.path.join(os.path.dirname(exe_dir), "Library", "bin", "ffmpeg.exe"),
        os.path.join(os.path.dirname(exe_dir), "Library", "bin", "ffmpeg"),
    ):
        _push_candidate(candidates, value)


def _append_path_candidates(candidates: List[str]) -> None:
    try:
        _push_candidate(candidates, shutil.which("ffmpeg.exe") or "")
        _push_candidate(candidates, shutil.which("ffmpeg") or "")
    except (AttributeError, OSError, ValueError):
        logger.debug("PATH ffmpeg candidate lookup failed", exc_info=True)
    _push_candidate(candidates, "ffmpeg.exe")
    _push_candidate(candidates, "ffmpeg")


def _resolved_ffmpeg_candidates(candidates: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for candidate in candidates:
        key = os.path.normcase(str(candidate))
        if key in seen:
            continue
        seen.add(key)
        try:
            resolved = shutil.which(candidate) or candidate
        except (AttributeError, OSError, ValueError):
            logger.debug("ffmpeg candidate resolution failed for %s", candidate, exc_info=True)
            resolved = candidate
        if ffmpeg_available(resolved):
            return [str(resolved)]
    return out


def _push_candidate(candidates: List[str], value: str) -> None:
    candidate = str(value or "").strip()
    if candidate:
        candidates.append(candidate)


def _ffmpeg_frame_to_pixmap(path: str, ms: int, w=160, h=90, ffmpeg_bin: str = "") -> Optional[QtGui.QPixmap]:
    ffmpeg_bin = resolve_ffmpeg_bin(ffmpeg_bin)
    if not _frame_request_available(path, ffmpeg_bin):
        return None
    outjpg = _temp_jpeg_path()
    try:
        _run_ffmpeg_jpeg_command(_frame_file_command(path, ms, w, ffmpeg_bin, outjpg))
        if os.path.exists(outjpg) and os.path.getsize(outjpg) > 0:
            pixmap = QtGui.QPixmap(outjpg)
            return pixmap if not pixmap.isNull() else None
        return None
    finally:
        _cleanup_temp_file(outjpg)


def _ffmpeg_frame_to_qimage(path: str, ms: int, w=160, h=90, ffmpeg_bin: str = "") -> Optional[QtGui.QImage]:
    ffmpeg_bin = resolve_ffmpeg_bin(ffmpeg_bin)
    if not _frame_request_available(path, ffmpeg_bin):
        return None
    data = _run_ffmpeg_pipe_command(_frame_pipe_command(path, ms, w, ffmpeg_bin))
    if not data:
        return None
    qimg = QtGui.QImage()
    return qimg if qimg.loadFromData(data) else None


def _ffmpeg_frames_to_qimages(path: str, ms_list: List[int], w=160, h=90, ffmpeg_bin: str = "") -> dict[int, QtGui.QImage]:
    ffmpeg_bin = resolve_ffmpeg_bin(ffmpeg_bin)
    requested = [int(ms) for ms in ms_list if int(ms) >= 0]
    if not requested or not _frame_request_available(path, ffmpeg_bin):
        return {}
    with tempfile.TemporaryDirectory(prefix="mp-thumb-ffmpeg-") as tmpdir:
        outputs = [os.path.join(tmpdir, f"thumb_{idx:03d}.jpg") for idx in range(len(requested))]
        cmd = _frame_multi_file_command(path, requested, w, ffmpeg_bin, outputs)
        if not _run_ffmpeg_multi_jpeg_command(cmd):
            return {}
        images: dict[int, QtGui.QImage] = {}
        for ms, outjpg in zip(requested, outputs):
            if not os.path.exists(outjpg) or os.path.getsize(outjpg) <= 0:
                continue
            qimg = QtGui.QImage(outjpg)
            if qimg.isNull():
                continue
            images[int(ms)] = qimg
        return images


def _frame_request_available(path: str, ffmpeg_bin: str) -> bool:
    return os.path.exists(path) and ffmpeg_available(ffmpeg_bin)


def _frame_file_command(path: str, ms: int, w: int, ffmpeg_bin: str, output: str) -> list[str]:
    return _frame_input_args(path, ms, w, ffmpeg_bin) + ["-q:v", "3", output]


def _frame_pipe_command(path: str, ms: int, w: int, ffmpeg_bin: str) -> list[str]:
    return _frame_input_args(path, ms, w, ffmpeg_bin) + ["-f", "image2pipe", "-vcodec", "mjpeg", "-"]


def _frame_multi_file_command(path: str, ms_list: List[int], w: int, ffmpeg_bin: str, outputs: List[str]) -> list[str]:
    cmd = [
        ffmpeg_bin,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
    ]
    for ms in ms_list:
        cmd.extend(
            [
                "-ss",
                f"{(max(int(ms), 0) / 1000.0):.3f}",
                "-i",
                path,
            ]
        )
    for index, output in enumerate(outputs):
        cmd.extend(
            [
                "-map",
                f"{int(index)}:v:0",
                "-frames:v",
                "1",
                "-vf",
                f"scale={w}:-1:flags=bilinear",
                "-q:v",
                "3",
                output,
            ]
        )
    return cmd


def _frame_input_args(path: str, ms: int, w: int, ffmpeg_bin: str) -> list[str]:
    ss = max(ms, 0) / 1000.0
    return [
        ffmpeg_bin,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{ss:.3f}",
        "-i",
        path,
        "-frames:v",
        "1",
        "-vf",
        f"scale={w}:-1:flags=bilinear",
    ]


def _run_ffmpeg_jpeg_command(cmd: list[str]) -> None:
    subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **hidden_subprocess_kwargs(),
    )


def _run_ffmpeg_pipe_command(cmd: list[str]) -> bytes:
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            **hidden_subprocess_kwargs(),
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        logger.debug("ffmpeg image2pipe frame extraction failed", exc_info=True)
        return b""
    if int(getattr(proc, "returncode", 1)) != 0:
        return b""
    return bytes(getattr(proc, "stdout", b"") or b"")


def _run_ffmpeg_multi_jpeg_command(cmd: list[str]) -> bool:
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            **hidden_subprocess_kwargs(),
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        logger.debug("ffmpeg multi-frame extraction failed", exc_info=True)
        return False
    return int(getattr(proc, "returncode", 1)) == 0


def _temp_jpeg_path() -> str:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        return tmp.name


def _cleanup_temp_file(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        logger.debug("temporary ffmpeg thumbnail file cleanup skipped", exc_info=True)

__all__ = [
    "FFMPEG_BIN",
    "_ffmpeg_frame_to_pixmap",
    "_ffmpeg_frame_to_qimage",
    "_ffmpeg_frames_to_qimages",
    "_which_ffmpeg",
    "ffmpeg_available",
    "resolve_ffmpeg_bin",
    "spawn_ffmpeg_iter",
]
