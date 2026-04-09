import concurrent.futures
import multiprocessing
import os
import re
import subprocess
import sys

from process_utils import hidden_subprocess_kwargs
from scene_analysis.core.media import resolve_ffmpeg_bin


VIDEO_FILE_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".m4v", ".webm", ".ts", ".flv", ".wmv"
}
IMAGE_FILE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".tif", ".tiff"
}
ANIMATED_IMAGE_FILE_EXTENSIONS = {
    ".gif",
    ".webp",
}
MEDIA_FILE_EXTENSIONS = VIDEO_FILE_EXTENSIONS | IMAGE_FILE_EXTENSIONS


if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_BUNDLED_FFMPEG_BIN = os.path.join(BASE_DIR, "ffmpeg", "bin", "ffmpeg.exe")
FFMPEG_BIN = resolve_ffmpeg_bin(_BUNDLED_FFMPEG_BIN if os.path.exists(_BUNDLED_FFMPEG_BIN) else "")


try:
    from scenedetect import SceneManager
    from scenedetect.detectors import ContentDetector
    _SCENEDETECT_IMPORT_ERROR = None
except Exception as exc:  # optional dependency
    SceneManager = None
    ContentDetector = None
    _SCENEDETECT_IMPORT_ERROR = exc


def is_image_file_path(path: str) -> bool:
    try:
        return os.path.splitext(str(path or ""))[1].lower() in IMAGE_FILE_EXTENSIONS
    except Exception:
        return False


def is_animated_image_file_path(path: str) -> bool:
    try:
        return os.path.splitext(str(path or ""))[1].lower() in ANIMATED_IMAGE_FILE_EXTENSIONS
    except Exception:
        return False


def media_file_dialog_filter() -> str:
    media_patterns = " ".join(f"*{ext}" for ext in sorted(MEDIA_FILE_EXTENSIONS))
    video_patterns = " ".join(f"*{ext}" for ext in sorted(VIDEO_FILE_EXTENSIONS))
    image_patterns = " ".join(f"*{ext}" for ext in sorted(IMAGE_FILE_EXTENSIONS))
    return (
        f"Media Files ({media_patterns});;"
        f"Video Files ({video_patterns});;"
        f"Image Files ({image_patterns});;"
        "All Files (*)"
    )


def current_ffmpeg_bin(preferred: str = "") -> str:
    bundled = _BUNDLED_FFMPEG_BIN if os.path.exists(_BUNDLED_FFMPEG_BIN) else ""
    return resolve_ffmpeg_bin(preferred or bundled or FFMPEG_BIN)


def _spawn_ffmpeg(cmd_list):
    proc = subprocess.Popen(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        **hidden_subprocess_kwargs(),
    )
    out, err = proc.communicate()
    return (out or ""), (err or "")


def _ffmpeg_available(bin_path: str = "") -> bool:
    probe_bin = current_ffmpeg_bin(bin_path)
    try:
        out, err = _spawn_ffmpeg([probe_bin, "-version"])
        return "ffmpeg version" in (out + err)
    except Exception:
        return False


def _require_scenedetect():
    if SceneManager is None or ContentDetector is None:
        raise RuntimeError(
            "scenedetect가 설치되어 있지 않아 장면 탐지를 사용할 수 없습니다. "
            "앱은 정상 실행되며, 씬 관련 기능만 비활성화됩니다."
        ) from _SCENEDETECT_IMPORT_ERROR


def _scene_ffmpeg_filters(threshold: float, downscale_w: int, sample_fps: int) -> list[str]:
    filters = []
    if downscale_w and downscale_w > 0:
        filters.append(f"scale={downscale_w}:-1:flags=bilinear")
    if sample_fps and sample_fps > 0:
        filters.append(f"fps={sample_fps}")
    filters.append(f"select='gt(scene,{threshold})'")
    filters.append("showinfo")
    return filters


def _scene_pts_from_ffmpeg_log(stderr_text: str) -> list[int]:
    pts = []
    for line in stderr_text.splitlines():
        match = re.search(r"pts_time:\s*([0-9]+(?:\.[0-9]+)?)", line)
        if match:
            pts.append(int(round(float(match.group(1)) * 1000.0)))
    pts = sorted(set(pts))
    if not pts or pts[0] != 0:
        pts = [0] + pts
    return pts


def _detect_scenes_ffmpeg(
    path: str,
    threshold: float = 0.35,
    downscale_w: int = 320,
    sample_fps: int = 12,
) -> list[int]:
    if not path or not os.path.exists(path):
        return [0]
    _, err = _spawn_ffmpeg(
        [
            current_ffmpeg_bin(),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "info",
            "-i",
            path,
            "-an",
            "-vf",
            ",".join(_scene_ffmpeg_filters(threshold, downscale_w, sample_fps)),
            "-f",
            "null",
            "-",
        ]
    )
    return _scene_pts_from_ffmpeg_log(err)


def _detect_scenes_worker(args):
    _require_scenedetect()
    import cv2

    path, threshold, start_frame, end_frame, fps = args
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"[Worker] 비디오 파일 열기 실패: {path}")
        return []

    mgr = SceneManager()
    mgr.add_detector(ContentDetector(threshold=threshold))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    current_frame = start_frame
    while current_frame < end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        mgr.process_frame(current_frame, frame)
        current_frame += 1
    cap.release()
    return [int(start.get_seconds() * 1000) for start, _ in mgr.get_scene_list()]


def _scene_capture_stats(path: str) -> tuple[float, int]:
    import cv2

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(f"비디오 열기 실패: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    if total_frames <= 0:
        total_frames = int(10 * 60 * fps)
    return fps, total_frames


def _default_scene_workers(workers):
    if workers and workers > 0:
        return workers
    try:
        return max(1, min(multiprocessing.cpu_count() - 1, 8))
    except Exception:
        return 4


def _scene_chunks(path, total_frames: int, fps: float, workers: int, downscale_w: int, use_gray: bool, threshold: float):
    overlap = 2
    chunk_frames = max(int(total_frames / workers), int(fps * 10))
    chunks = []
    start = 0
    while start < total_frames:
        end = min(total_frames, start + chunk_frames)
        chunks.append((path, start, end, fps, downscale_w, use_gray, threshold, overlap))
        start = end
    return chunks


def _scene_executor_class(backend: str):
    if backend != "process":
        return concurrent.futures.ThreadPoolExecutor
    if os.name == "nt" and getattr(sys, "frozen", False):
        print("[씬탐색] frozen Windows에서 ProcessPool 비활성화: ThreadPool로 폴백")
        return concurrent.futures.ThreadPoolExecutor
    return concurrent.futures.ProcessPoolExecutor


def _prepare_scene_frame(frame, down_w: int, use_gray: bool, h_ratio):
    import cv2

    if down_w and down_w > 0:
        if h_ratio is None:
            h_ratio = frame.shape[0] / frame.shape[1]
        frame = cv2.resize(
            frame,
            (int(down_w), max(1, int(down_w * h_ratio))),
            interpolation=cv2.INTER_AREA,
        )
    if use_gray:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return frame, h_ratio


def _scene_chunk_worker(args):
    import cv2
    import numpy as np

    path, start_f, end_f, fps, down_w, use_gray, diff_thresh, overlap = args
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return []

    prev = None
    scene_ms = []
    cur_idx = max(0, start_f - overlap)
    h_ratio = None
    cap.set(cv2.CAP_PROP_POS_FRAMES, cur_idx)
    while cur_idx < end_f:
        ret, frame = cap.read()
        if not ret:
            break
        frame, h_ratio = _prepare_scene_frame(frame, down_w, use_gray, h_ratio)
        if prev is not None and float(np.mean(cv2.absdiff(frame, prev))) >= diff_thresh:
            scene_ms.append(int((cur_idx / fps) * 1000.0))
        prev = frame
        cur_idx += 1
    cap.release()
    return scene_ms


def _merge_scene_points(points: list[int]) -> list[int]:
    merged = []
    last = None
    for point in sorted(set(points)):
        if last is None or (point - last) > 500:
            merged.append(point)
            last = point
    if not merged or merged[0] != 0:
        merged = [0] + merged
    return merged


def _detect_scenes_parallel(path, threshold=30, workers=None, backend="thread", downscale_w=320, use_gray=True):
    fps, total_frames = _scene_capture_stats(path)
    worker_count = _default_scene_workers(workers)
    chunks = _scene_chunks(path, total_frames, fps, worker_count, downscale_w, use_gray, float(threshold))
    out = []
    executor_cls = _scene_executor_class(backend)
    with executor_cls(max_workers=worker_count) as executor:
        for ms_list in executor.map(_scene_chunk_worker, chunks):
            out.extend(ms_list)
    return _merge_scene_points(out)
