from __future__ import annotations

from typing import List, Optional, Tuple
import os
import queue
import re
import subprocess
import threading

from PyQt6 import QtCore

from process_utils import hidden_subprocess_kwargs
from .media import (
    SIGLIP_BATCH_DEFAULT,
    _normalize_siglip_batch_size,
    _torchcodec_detect_scenes_scored,
    ffmpeg_available,
    resolve_ffmpeg_bin,
    spawn_ffmpeg_iter,
)


SCENE_SCORE_RE = re.compile(r"lavfi\.scene_score\s*[:=]\s*([0-9.]+)", re.I)
PTS_RE = re.compile(r"pts_time:\s*([0-9]+(?:\.[0-9]+)?)")


def detect_scenes_ffmpeg_scored(
    path: str,
    downscale_w: int = 320,
    sample_fps: int = 0,
    ffmpeg_bin: str = "",
    ff_hwaccel: bool = False,
    topk: int = 10,
    nms_ms: int = 1000,
) -> list[tuple[int, float]]:
    ffmpeg_bin = resolve_ffmpeg_bin(ffmpeg_bin)
    if not os.path.exists(path) or not ffmpeg_available(ffmpeg_bin):
        return []
    parts = []
    if downscale_w and downscale_w > 0:
        parts.append(f"scale={downscale_w}:-1:flags=bilinear")
    if sample_fps and sample_fps > 0:
        parts.append(f"fps={int(sample_fps)}")
    parts.append("select='gt(scene,0)'")
    parts.append("showinfo,metadata=print:key=lavfi.scene_score")
    vf = ",".join(parts)
    cmd = [ffmpeg_bin, "-nostdin", "-hide_banner", "-loglevel", "info"]
    if ff_hwaccel:
        cmd.extend(["-hwaccel", "cuda"])
    cmd.extend(["-i", path, "-an", "-vf", vf, "-f", "null", "-"])
    pairs: list[tuple[int, float]] = []
    cur_pts_ms: Optional[int] = None
    for line in spawn_ffmpeg_iter(cmd):
        m1 = PTS_RE.search(line)
        if m1:
            cur_pts_ms = int(round(float(m1.group(1)) * 1000))
        m2 = SCENE_SCORE_RE.search(line)
        if m2 and cur_pts_ms is not None:
            score = float(m2.group(1))
            pairs.append((cur_pts_ms, score))
    if not pairs:
        return []
    pairs.sort(key=lambda x: x[1], reverse=True)
    picked: list[tuple[int, float]] = []
    for ms, sc in pairs:
        if all(abs(ms - pms) >= nms_ms for pms, _ in picked):
            picked.append((ms, sc))
        if len(picked) >= topk:
            break
    return picked


def detect_scenes_pts_only(
    path: str,
    threshold: float = 0.35,
    downscale_w: int = 320,
    sample_fps: int = 0,
    ffmpeg_bin: str = "",
    ff_hwaccel: bool = False,
) -> List[int]:
    ffmpeg_bin = resolve_ffmpeg_bin(ffmpeg_bin)
    if not os.path.exists(path) or not ffmpeg_available(ffmpeg_bin):
        return [0]

    def vf_str(thr: float) -> str:
        parts = []
        if downscale_w and downscale_w > 0:
            parts.append(f"scale={downscale_w}:-1:flags=bilinear")
        if sample_fps and sample_fps > 0:
            parts.append(f"fps={int(sample_fps)}")
        parts.append(f"select='gt(scene,{thr})'")
        parts.append("showinfo")
        return ",".join(parts)

    def run_once(thr: float) -> List[int]:
        cmd = [ffmpeg_bin, "-nostdin", "-hide_banner", "-loglevel", "info"]
        if ff_hwaccel:
            cmd.extend(["-hwaccel", "cuda"])
        cmd.extend(["-i", path, "-an", "-vf", vf_str(thr), "-f", "null", "-"])
        out_pts: List[int] = []
        for line in spawn_ffmpeg_iter(cmd):
            m = PTS_RE.search(line)
            if m:
                out_pts.append(int(round(float(m.group(1)) * 1000)))
        out_pts = sorted(set(out_pts))
        if not out_pts or out_pts[0] != 0:
            out_pts = [0] + out_pts
        return out_pts

    pts = []
    for thr in (threshold, 0.25 if threshold >= 0.25 else max(0.05, threshold - 0.1), 0.18):
        pts = run_once(thr)
        if len(pts) > 1:
            return pts
    return pts


def _ffmpeg_progress_filter(downscale_w: int, sample_fps: int, threshold: float) -> str:
    parts = []
    if downscale_w and downscale_w > 0:
        parts.append(f"scale={downscale_w}:-1:flags=bilinear")
    if sample_fps and sample_fps > 0:
        parts.append(f"fps={int(sample_fps)}")
    parts.append(f"select='gt(scene,{threshold})'")
    parts.append("showinfo,metadata=print:key=lavfi.scene_score")
    return ",".join(parts)


def _ffmpeg_progress_command(ffbin: str, path: str, vf: str, use_hwaccel: bool) -> List[str]:
    cmd = [ffbin, "-nostdin", "-hide_banner", "-loglevel", "info"]
    if use_hwaccel:
        cmd.extend(["-hwaccel", "cuda"])
    cmd.extend(["-i", path, "-an", "-vf", vf, "-f", "null", "-"])
    return cmd


def _start_ffmpeg_progress_reader(proc: subprocess.Popen, q: "queue.Queue[object]", stop_token: object) -> threading.Thread:
    def _reader(stream) -> None:
        for line in iter(stream.readline, ""):
            q.put(line)
        q.put(stop_token)

    thread = threading.Thread(target=_reader, args=(proc.stderr,), daemon=True)
    thread.start()
    return thread


def _consume_ffmpeg_progress_line(
    line: str,
    recent_errors: List[str],
    state: dict,
    emit_progress,
) -> None:
    if "error" in line.lower():
        recent_errors.append(line.strip())
        if len(recent_errors) > 6:
            recent_errors[:] = recent_errors[-6:]
    if "frame=" in line:
        state["frame_count"] += 1
        if state["frame_count"] - state["last_emit"] >= 50:
            state["last_emit"] = state["frame_count"]
            emit_progress(min(95, 10 + state["frame_count"] // 20))
    m_pts = PTS_RE.search(line)
    if m_pts:
        state["cur_pts_ms"] = int(round(float(m_pts.group(1)) * 1000))
    m_score = SCENE_SCORE_RE.search(line)
    cur_pts_ms = state.get("cur_pts_ms")
    if m_score and cur_pts_ms is not None:
        state["all_scenes"].append((cur_pts_ms, float(m_score.group(1))))
        state["cur_pts_ms"] = None


def _finalize_ffmpeg_progress_result(
    runner,
    proc: Optional[subprocess.Popen],
    all_scenes: List[tuple[int, float]],
    recent_errors: List[str],
    use_hwaccel: bool,
) -> Tuple[List[int], List[tuple[int, float]], bool]:
    try:
        rc = proc.wait(timeout=1) if proc is not None else None
    except Exception:
        rc = proc.poll() if proc is not None else None
    runner._proc = None
    ok = bool(rc == 0 or all_scenes)
    if use_hwaccel and not ok and recent_errors:
        runner._emit_message(f"FFmpeg GPU 실패: {recent_errors[-1]}")
    if not all_scenes:
        return [0], [], ok
    all_scenes = sorted(list(set(all_scenes)), key=lambda item: item[0])
    pts_only = [ms for ms, _score in all_scenes]
    if 0 not in pts_only:
        pts_only = [0] + pts_only
    runner._emit_progress(98)
    return pts_only, all_scenes, ok


class _SceneDetectRunner:
    def __init__(
        self,
        path: str,
        use_ff: bool,
        thr: float,
        dw: int,
        fps: int,
        ffbin: str,
        host,
        ff_hwaccel: bool = False,
        decode_chunk_size: int = 64,
        progress_cb=None,
        message_cb=None,
        cancel_cb=None,
    ):
        self.path = path
        self.use_ff = bool(use_ff)
        self.thr = float(thr)
        self.dw = int(dw)
        self.fps = int(fps)
        self.ffbin = ffbin
        self.host = host
        self.ff_hwaccel = bool(ff_hwaccel)
        try:
            self.decode_chunk_size = int(
                _normalize_siglip_batch_size(decode_chunk_size, default=SIGLIP_BATCH_DEFAULT)
            )
        except Exception:
            self.decode_chunk_size = max(16, int(decode_chunk_size))
        self.progress_cb = progress_cb
        self.message_cb = message_cb
        self.cancel_cb = cancel_cb
        self._proc: Optional[subprocess.Popen] = None

    def _emit_progress(self, value: int) -> None:
        cb = self.progress_cb
        if callable(cb):
            try:
                cb(int(value))
            except Exception:
                pass

    def _emit_message(self, text: str) -> None:
        cb = self.message_cb
        if callable(cb):
            try:
                cb(str(text))
            except Exception:
                pass

    def _is_canceled(self) -> bool:
        cb = self.cancel_cb
        if not callable(cb):
            return False
        try:
            return bool(cb())
        except Exception:
            return False

    def cancel_active_process(self) -> None:
        try:
            if self._proc is not None:
                self._proc.kill()
        except Exception:
            pass

    def _raise_if_canceled(self) -> None:
        if self._is_canceled():
            self.cancel_active_process()
            raise RuntimeError("사용자 취소")

    def _run_parallel(self) -> List[int]:
        try:
            return self.host._detect_scenes_parallel(self.path, threshold=55, backend="thread")
        except Exception:
            return getattr(self.host, "_fallback_detect_scenes", lambda p: [0])(self.path)

    def _run_torchcodec_progress(self) -> Tuple[List[int], List[tuple[int, float]], bool]:
        self._emit_message(f"TorchCodec 단일 패스 분석 중… (chunk={int(self.decode_chunk_size)})")
        pts, top, ok, mode = _torchcodec_detect_scenes_scored(
            self.path,
            threshold=self.thr,
            downscale_w=self.dw,
            sample_fps=self.fps,
            prefer_gpu=self.ff_hwaccel,
            decode_chunk_size=self.decode_chunk_size,
            progress_cb=lambda p: self._emit_progress(int(max(1, min(98, int(p))))),
            cancel_cb=lambda: self._is_canceled(),
        )
        mode_s = str(mode or "").strip().lower()
        if ok:
            if "torchcodec-gpu" in mode_s:
                self._emit_message("TorchCodec GPU 디코드 경로 사용")
            elif "torchcodec" in mode_s:
                self._emit_message("TorchCodec CPU 디코드 경로 사용")
        return pts, top, bool(ok)

    def _run_ffmpeg_progress_once(self, use_hwaccel: bool) -> Tuple[List[int], List[tuple[int, float]], bool]:
        if not ffmpeg_available(self.ffbin):
            return [0], [], False
        fixed_thr = 0.10
        vf = _ffmpeg_progress_filter(self.dw, self.fps, fixed_thr)
        cmd = _ffmpeg_progress_command(self.ffbin, self.path, vf, use_hwaccel)
        self._proc = subprocess.Popen(
            cmd,
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
        _start_ffmpeg_progress_reader(self._proc, q, stop)
        state = {"all_scenes": [], "cur_pts_ms": None, "frame_count": 0, "last_emit": 0}
        mode_label = "GPU(CUDA)" if use_hwaccel else "CPU"
        self._emit_message(f"FFmpeg 단일 패스 분석 중 ({mode_label}, thr={fixed_thr:.2f})…")
        recent_errors: list[str] = []
        while True:
            if self._is_canceled():
                self.cancel_active_process()
                self._proc = None
                raise RuntimeError("사용자 취소")
            line = q.get()
            if line is stop:
                break
            _consume_ffmpeg_progress_line(line, recent_errors, state, self._emit_progress)
        return _finalize_ffmpeg_progress_result(
            self,
            self._proc,
            state["all_scenes"],
            recent_errors,
            use_hwaccel,
        )

    def _run_ffmpeg_progress(self) -> Tuple[List[int], List[tuple[int, float]]]:
        if self.ff_hwaccel:
            pts, top, ok = self._run_ffmpeg_progress_once(use_hwaccel=True)
            if ok:
                return pts, top
            self._emit_message("FFmpeg GPU 모드 실패 → CPU 모드로 재시도합니다.")
        pts, top, _ok = self._run_ffmpeg_progress_once(use_hwaccel=False)
        return pts, top

    def run(self) -> Tuple[List[int], List[tuple[int, float]]]:
        if not self.path or not os.path.exists(self.path):
            raise FileNotFoundError("영상 경로 없음")

        self._emit_progress(5)
        pts: List[int] = []
        top: List[tuple[int, float]] = []

        pts, top, tc_ok = self._run_torchcodec_progress()
        self._raise_if_canceled()

        if (not tc_ok) or len(pts) <= 1:
            if self.use_ff:
                self._emit_message("TorchCodec 결과 부족/실패 → FFmpeg 폴백")
                pts, top = self._run_ffmpeg_progress()
                self._raise_if_canceled()
                if len(pts) <= 1:
                    self._emit_message("FFmpeg 결과 적음 → OpenCV 병렬 폴백")
                    pts = self._run_parallel()
                    top = []
            else:
                self._emit_message("TorchCodec 결과 부족/실패 → OpenCV 병렬 폴백")
                pts = self._run_parallel()
                top = []

        self._raise_if_canceled()
        self._emit_progress(100)
        return pts, top


def run_scene_detect(
    path: str,
    use_ff: bool,
    thr: float,
    dw: int,
    fps: int,
    ffbin: str,
    host,
    ff_hwaccel: bool = False,
    decode_chunk_size: int = 64,
    progress_cb=None,
    message_cb=None,
    cancel_cb=None,
) -> Tuple[List[int], List[tuple[int, float]]]:
    runner = _SceneDetectRunner(
        path,
        use_ff,
        thr,
        dw,
        fps,
        ffbin,
        host,
        ff_hwaccel=ff_hwaccel,
        decode_chunk_size=decode_chunk_size,
        progress_cb=progress_cb,
        message_cb=message_cb,
        cancel_cb=cancel_cb,
    )
    return runner.run()


class SceneDetectWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    message = QtCore.pyqtSignal(str)
    finished_ok = QtCore.pyqtSignal(list, list)
    finished_err = QtCore.pyqtSignal(str)

    def __init__(
        self,
        path: str,
        use_ff: bool,
        thr: float,
        dw: int,
        fps: int,
        ffbin: str,
        host,
        ff_hwaccel: bool = False,
        decode_chunk_size: int = 64,
    ):
        super().__init__()
        self._cancel = False
        self.path, self.use_ff = path, use_ff
        self.thr, self.dw, self.fps = thr, dw, fps
        self.ffbin = ffbin
        self.host = host
        self.ff_hwaccel = bool(ff_hwaccel)
        try:
            self.decode_chunk_size = int(_normalize_siglip_batch_size(decode_chunk_size, default=SIGLIP_BATCH_DEFAULT))
        except Exception:
            self.decode_chunk_size = max(16, int(decode_chunk_size))
        self._runner: Optional[_SceneDetectRunner] = None

    def cancel(self):
        self._cancel = True
        try:
            if self._runner is not None:
                self._runner.cancel_active_process()
        except Exception:
            pass

    def run(self):
        try:
            self._runner = _SceneDetectRunner(
                self.path,
                self.use_ff,
                self.thr,
                self.dw,
                self.fps,
                self.ffbin,
                self.host,
                ff_hwaccel=self.ff_hwaccel,
                decode_chunk_size=self.decode_chunk_size,
                progress_cb=self.progress.emit,
                message_cb=self.message.emit,
                cancel_cb=lambda: bool(self._cancel),
            )
            pts, top = self._runner.run()
            self.finished_ok.emit(pts, top)
        except Exception as e:
            self.finished_err.emit(str(e))
        finally:
            self._runner = None
