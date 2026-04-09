from __future__ import annotations

from typing import List, Optional
import os
import shutil
import tempfile
import time

from .media import FFMPEG_BIN, ffmpeg_available, resolve_ffmpeg_bin


def _validated_job_path(job: dict, key: str, message: str) -> str:
    value = str(job.get(key) or "").strip()
    if not value:
        raise RuntimeError(message)
    return value


def _validated_media_path(job: dict) -> str:
    current_path = _validated_job_path(job, "current_path", "현재 영상 경로를 찾을 수 없습니다.")
    if not os.path.exists(current_path):
        raise RuntimeError("현재 영상 경로를 찾을 수 없습니다.")
    return current_path


def _validated_ffmpeg_path(job: dict) -> str:
    ffbin = resolve_ffmpeg_bin(str(job.get("ffbin") or "").strip() or FFMPEG_BIN)
    if not ffmpeg_available(ffbin):
        raise RuntimeError(f"ffmpeg를 찾을 수 없습니다. 경로: {ffbin}")
    return ffbin


def _validated_time_range(start_ms: int, end_ms: int) -> tuple[float, float]:
    start_s = max(0.0, float(start_ms) / 1000.0)
    duration_s = max(0.0, float(end_ms - start_ms) / 1000.0)
    if duration_s <= 0.0:
        raise RuntimeError("구간 길이가 0초 이하입니다.")
    return start_s, duration_s


def _ensure_parent_dir(path: str):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except Exception:
        pass


def _has_nonempty_output(path: str) -> bool:
    try:
        return os.path.exists(path) and os.path.getsize(path) > 0
    except Exception:
        return False


def _has_output_path(path: str) -> bool:
    try:
        return bool(path) and os.path.exists(path)
    except Exception:
        return False


def _wait_for_nonempty_output(path: str, timeout_ms: int = 1500, interval_ms: int = 50) -> bool:
    if _has_nonempty_output(path):
        return True
    deadline = time.time() + (max(0, int(timeout_ms)) / 1000.0)
    sleep_s = max(0.01, int(interval_ms) / 1000.0)
    while time.time() < deadline:
        time.sleep(sleep_s)
        if _has_nonempty_output(path):
            return True
    return _has_nonempty_output(path)


def _wait_for_output_path(path: str, timeout_ms: int = 3000, interval_ms: int = 50) -> bool:
    if _has_output_path(path):
        return True
    deadline = time.time() + (max(0, int(timeout_ms)) / 1000.0)
    sleep_s = max(0.01, int(interval_ms) / 1000.0)
    while time.time() < deadline:
        time.sleep(sleep_s)
        if _has_output_path(path):
            return True
    return _has_output_path(path)


def _run_ffmpeg_allow_output(worker, cmd: List[str], out_path: str) -> bool:
    try:
        worker._run_ffmpeg(cmd)
        return True
    except Exception:
        if _wait_for_nonempty_output(out_path):
            return False
        raise


def _concat_safe_path(path: str) -> str:
    normalized = os.path.abspath(path).replace("\\", "/")
    return normalized.replace("'", r"'\''")


def export_ranges_job(worker, job: dict) -> dict:
    current_path = _validated_media_path(job)
    ffbin = _validated_ffmpeg_path(job)
    clip_ranges = list(job.get("clip_ranges") or [])
    mode_label = str(job.get("mode_label") or "클립")
    source = str(job.get("source") or "manual")
    job_id = int(job.get("job_id") or 0)
    save_dir, base_name = _scene_clip_output_dir(current_path)
    ok_files, fail_msgs = _export_range_files(
        worker,
        ffbin,
        current_path,
        base_name,
        save_dir,
        clip_ranges,
        mode_label,
        bool(job.get("encode", True)),
        max(0, int(job.get("fps") or 0)),
        max(0, int(job.get("scale") or 0)),
        str(job.get("bitrate") or "").strip(),
    )
    return {
        "job_id": job_id,
        "kind": "ranges",
        "source": source,
        "mode_label": mode_label,
        "ok_cnt": int(len(ok_files)),
        "total_cnt": int(len(clip_ranges)),
        "save_dir": save_dir,
        "ok_files": ok_files,
        "fail_msgs": fail_msgs,
    }


def _scene_clip_output_dir(current_path: str) -> tuple[str, str]:
    base_dir = os.path.dirname(current_path)
    base_name, _ = os.path.splitext(os.path.basename(current_path))
    save_dir = os.path.join(base_dir, f"{base_name}_scene_clips")
    os.makedirs(save_dir, exist_ok=True)
    return save_dir, base_name


def _export_range_files(
    worker,
    ffbin: str,
    current_path: str,
    base_name: str,
    save_dir: str,
    clip_ranges,
    mode_label: str,
    encode: bool,
    fps: int,
    scale: int,
    bitrate: str,
):
    ok_files: List[str] = []
    fail_msgs: List[str] = []
    total = max(0, int(len(clip_ranges)))
    many = total > 1
    for idx, (start_ms, end_ms) in enumerate(clip_ranges, start=1):
        _raise_if_stopped(worker)
        result = _export_single_range(
            worker, ffbin, current_path, base_name, save_dir, idx, many, start_ms, end_ms, encode, fps, scale, bitrate
        )
        if result["ok"]:
            ok_files.append(result["path"])
        elif result["error"]:
            fail_msgs.append(result["error"])
        worker.message.emit(f"{mode_label} 클립 저장 진행: {len(ok_files)}/{total} | {idx}/{total}")
    return ok_files, fail_msgs


def _export_single_range(
    worker,
    ffbin: str,
    current_path: str,
    base_name: str,
    save_dir: str,
    idx: int,
    many: bool,
    start_ms: int,
    end_ms: int,
    encode: bool,
    fps: int,
    scale: int,
    bitrate: str,
):
    start_ms = int(start_ms)
    end_ms = int(end_ms)
    if end_ms <= start_ms:
        return {"ok": False, "path": "", "error": ""}
    s_tag = worker._fmt_ms_tag(start_ms)
    e_tag = worker._fmt_ms_tag(end_ms)
    out_name = f"{base_name}_sceneclip_{idx:04d}_{s_tag}_{e_tag}.mp4" if many else f"{base_name}_sceneclip_{s_tag}_{e_tag}.mp4"
    out_path = worker._unique_path(os.path.join(save_dir, out_name))
    start_s = max(0.0, float(start_ms) / 1000.0)
    end_s = max(start_s, float(end_ms) / 1000.0)
    try:
        _run_ffmpeg_allow_output(
            worker,
            _scene_clip_cmd(ffbin, current_path, out_path, start_s, end_s, encode, fps, scale, bitrate),
            out_path,
        )
        return {"ok": True, "path": out_path, "error": ""}
    except Exception as exc:
        return {"ok": False, "path": "", "error": f"{s_tag}~{e_tag} | {exc}"}


def _scene_clip_cmd(
    ffbin: str,
    current_path: str,
    out_path: str,
    start_s: float,
    end_s: float,
    encode: bool,
    fps: int,
    scale: int,
    bitrate: str,
) -> List[str]:
    cmd = [
        ffbin, "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start_s:.3f}", "-to", f"{end_s:.3f}",
        "-i", current_path, "-map", "0:v:0", "-map", "0:a?",
        "-sn", "-dn",
    ]
    if not bool(encode):
        cmd += ["-c", "copy", out_path]
        return cmd
    vf = []
    if int(fps) > 0:
        vf.append(f"fps={int(fps)}")
    if int(scale) > 0:
        vf.append(f"scale={int(scale)}:-1:flags=lanczos")
    if vf:
        cmd += ["-vf", ",".join(vf)]
    if str(bitrate or "").strip():
        cmd += ["-b:v", f"{str(bitrate).strip()}k"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-movflags", "+faststart", out_path]
    return cmd


def export_merge_job(worker, job: dict) -> dict:
    current_path = _validated_media_path(job)
    ffbin = _validated_ffmpeg_path(job)
    ranges = _normalized_merge_ranges(job.get("clip_ranges") or [])
    if len(ranges) < 2:
        raise RuntimeError("합치기에는 2개 이상의 유효 구간이 필요합니다.")
    mode_label = str(job.get("mode_label") or "클립병합")
    source = str(job.get("source") or "manual")
    job_id = int(job.get("job_id") or 0)
    save_dir, base_name = _scene_clip_output_dir(current_path)
    out_path = _merge_output_path(worker, save_dir, base_name, ranges)
    _run_merge_segments(
        worker,
        ffbin,
        current_path,
        ranges,
        mode_label,
        out_path,
        bool(job.get("encode", True)),
        max(0, int(job.get("fps") or 0)),
        max(0, int(job.get("scale") or 0)),
        str(job.get("bitrate") or "").strip(),
    )
    return {
        "job_id": job_id,
        "kind": "merge",
        "source": source,
        "mode_label": mode_label,
        "out_path": out_path,
        "save_dir": save_dir,
        "ok_cnt": 1,
        "total_cnt": 1,
        "ok_files": [out_path],
        "fail_msgs": [],
    }


def _normalized_merge_ranges(clip_ranges) -> List[tuple[int, int]]:
    return sorted(
        set((max(0, int(st)), max(0, int(ed))) for st, ed in (clip_ranges or []) if int(ed) > int(st)),
        key=lambda item: (item[0], item[1]),
    )


def _merge_output_path(worker, save_dir: str, base_name: str, ranges: List[tuple[int, int]]) -> str:
    first_tag = worker._fmt_ms_tag(int(ranges[0][0]))
    last_tag = worker._fmt_ms_tag(int(ranges[-1][1]))
    out_name = f"{base_name}_sceneclip_merge_{len(ranges):03d}cuts_{first_tag}_{last_tag}.mp4"
    return worker._unique_path(os.path.join(save_dir, out_name))


def _run_merge_segments(
    worker,
    ffbin: str,
    current_path: str,
    ranges: List[tuple[int, int]],
    mode_label: str,
    out_path: str,
    encode: bool,
    fps: int,
    scale: int,
    bitrate: str,
):
    temp_dir = tempfile.mkdtemp(prefix="scene_merge_", dir=os.path.dirname(out_path))
    seg_paths: List[str] = []
    try:
        for idx, (start_ms, end_ms) in enumerate(ranges, start=1):
            _raise_if_stopped(worker)
            seg_path = os.path.join(temp_dir, f"seg_{idx:04d}.mp4")
            start_s = max(0.0, float(start_ms) / 1000.0)
            end_s = max(start_s, float(end_ms) / 1000.0)
            _run_ffmpeg_allow_output(
                worker,
                _scene_clip_cmd(ffbin, current_path, seg_path, start_s, end_s, encode, fps, scale, bitrate),
                seg_path,
            )
            if _has_nonempty_output(seg_path):
                seg_paths.append(seg_path)
            worker.message.emit(f"{mode_label} 세그먼트 생성: {idx}/{len(ranges)}")
        _run_merge_concat(worker, ffbin, temp_dir, seg_paths, out_path)
    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
    if not _wait_for_nonempty_output(out_path):
        raise RuntimeError("병합 출력 파일 생성에 실패했습니다.")


def _run_merge_concat(worker, ffbin: str, temp_dir: str, seg_paths: List[str], out_path: str):
    if len(seg_paths) < 2:
        raise RuntimeError("병합할 임시 클립 생성에 실패했습니다.")
    list_path = os.path.join(temp_dir, "concat.txt")
    with open(list_path, "w", encoding="utf-8") as handle:
        for path in seg_paths:
            handle.write(f"file '{_concat_safe_path(path)}'\n")
    _run_ffmpeg_allow_output(worker, [
        ffbin, "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", "-movflags", "+faststart", out_path,
    ], out_path)


def export_gif_job(worker, job: dict) -> dict:
    current_path = _validated_media_path(job)
    ffbin = _validated_ffmpeg_path(job)
    start_ms = int(job.get("start_ms") or 0)
    end_ms = int(job.get("end_ms") or 0)
    fps = max(0, int(job.get("fps") or 0))
    scale = max(0, int(job.get("scale") or 0))
    out_path = _validated_job_path(job, "out_path", "출력 GIF 경로가 비어 있습니다.")
    _ensure_parent_dir(out_path)
    start_s, duration_s = _validated_time_range(start_ms, end_ms)
    mode_label = str(job.get("mode_label") or "GIF").strip()
    source = str(job.get("source") or "manual").strip().lower() or "manual"
    job_id = int(job.get("job_id") or 0)
    worker.message.emit(f"{mode_label} 저장 중...")
    ffmpeg_clean = _run_ffmpeg_allow_output(worker, _gif_cmd(ffbin, current_path, out_path, start_s, duration_s, fps, scale), out_path)
    if (not ffmpeg_clean) and (not _wait_for_output_path(out_path, timeout_ms=3000)):
        raise RuntimeError("GIF 출력 파일 생성에 실패했습니다.")
    return {"job_id": job_id, "kind": "gif", "source": source, "mode_label": mode_label, "out_path": out_path, "ok_cnt": 1, "total_cnt": 1, "ok_files": [out_path], "fail_msgs": []}


def _gif_cmd(ffbin: str, current_path: str, out_path: str, start_s: float, duration_s: float, fps: int, scale: int) -> List[str]:
    cmd = [ffbin, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start_s:.3f}", "-t", f"{duration_s:.3f}", "-i", current_path]
    vf = []
    if fps > 0:
        vf.append(f"fps={fps}")
    if scale > 0:
        vf.append(f"scale={scale}:-1:flags=lanczos")
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd.append(out_path)
    return cmd


def export_tile_clip_job(worker, job: dict) -> dict:
    current_path = _validated_media_path(job)
    ffbin = _validated_ffmpeg_path(job)
    start_ms = int(job.get("start_ms") or 0)
    end_ms = int(job.get("end_ms") or 0)
    out_path = _validated_job_path(job, "out_path", "출력 클립 경로가 비어 있습니다.")
    _ensure_parent_dir(out_path)
    start_s, duration_s = _validated_time_range(start_ms, end_ms)
    audio_only = bool(job.get("audio_only"))
    audio_format = str(job.get("audio_format") or "m4a").strip().lower() or "m4a"
    if audio_only and audio_format not in {"m4a", "mp3", "wav"}:
        raise RuntimeError(f"지원하지 않는 오디오 포맷입니다: {audio_format}")
    mode_label = str(job.get("mode_label") or "클립").strip()
    source = str(job.get("source") or "manual").strip().lower() or "manual"
    job_id = int(job.get("job_id") or 0)
    result_kind = "tile_audio_clip" if audio_only else "tile_clip"
    worker.message.emit(f"{mode_label} 저장 중...")
    _run_tile_clip(
        worker,
        _tile_clip_cmd(ffbin, current_path, out_path, start_s, duration_s, job, audio_only, audio_format),
        audio_only,
        out_path,
    )
    if not _wait_for_nonempty_output(out_path):
        raise RuntimeError("클립 출력 파일 생성에 실패했습니다.")
    return {"job_id": job_id, "kind": result_kind, "source": source, "mode_label": mode_label, "out_path": out_path, "ok_cnt": 1, "total_cnt": 1, "ok_files": [out_path], "fail_msgs": []}


def _tile_clip_cmd(ffbin: str, current_path: str, out_path: str, start_s: float, duration_s: float, job: dict, audio_only: bool, audio_format: str) -> List[str]:
    cmd = [ffbin, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start_s:.3f}", "-t", f"{duration_s:.3f}", "-i", current_path]
    if audio_only:
        return _tile_audio_cmd(cmd, out_path, audio_format)
    return _tile_video_cmd(cmd, out_path, bool(job.get("encode")), max(0, int(job.get("fps") or 0)), max(0, int(job.get("scale") or 0)), str(job.get("bitrate") or "").strip())


def _tile_audio_cmd(cmd: List[str], out_path: str, audio_format: str) -> List[str]:
    cmd += ["-map", "0:a:0", "-vn", "-sn", "-dn"]
    if audio_format == "wav":
        cmd += ["-c:a", "pcm_s16le"]
    elif audio_format == "mp3":
        cmd += ["-c:a", "libmp3lame", "-b:a", "192k"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    cmd.append(out_path)
    return cmd


def _tile_video_cmd(cmd: List[str], out_path: str, encode: bool, fps: int, scale: int, bitrate: str) -> List[str]:
    cmd += ["-map", "0:v:0", "-map", "0:a?", "-sn", "-dn"]
    if encode:
        vf = []
        if fps > 0:
            vf.append(f"fps={fps}")
        if scale > 0:
            vf.append(f"scale={scale}:-1:flags=lanczos")
        if vf:
            cmd += ["-vf", ",".join(vf)]
        if bitrate:
            cmd += ["-b:v", f"{bitrate}k"]
        cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac"]
    else:
        cmd += ["-c", "copy"]
    cmd.append(out_path)
    return cmd


def _run_tile_clip(worker, cmd: List[str], audio_only: bool, out_path: str):
    try:
        _run_ffmpeg_allow_output(worker, cmd, out_path)
    except RuntimeError as exc:
        if audio_only and "Stream map" in str(exc) and "matches no streams" in str(exc):
            raise RuntimeError("오디오 스트림을 찾을 수 없습니다.") from exc
        raise


def _raise_if_stopped(worker):
    if (not worker._running) or worker._cancel_current:
        raise RuntimeError("사용자 취소")


__all__ = [
    "export_ranges_job",
    "export_merge_job",
    "export_gif_job",
    "export_tile_clip_job",
]
