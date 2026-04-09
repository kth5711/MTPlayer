import os
from typing import List


VIDEO_FILE_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".m4v", ".webm", ".ts", ".flv", ".wmv"
}


def _norm_path(path: str) -> str:
    try:
        return os.path.normcase(os.path.abspath(str(path or "")))
    except Exception:
        return str(path or "")


def _is_video_file(path: str) -> bool:
    ext = os.path.splitext(str(path or ""))[1].lower()
    return ext in VIDEO_FILE_EXTENSIONS


def _append_batch_file(out: List[str], seen: set[str], path: str) -> None:
    if not os.path.isfile(path) or not _is_video_file(path):
        return
    key = _norm_path(path)
    if key in seen:
        return
    seen.add(key)
    out.append(path)


def _expand_batch_inputs(paths: List[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for raw in paths or []:
        path = os.path.abspath(str(raw or ""))
        if not path or not os.path.exists(path):
            continue
        if os.path.isfile(path):
            _append_batch_file(out, seen, path)
            continue
        if not os.path.isdir(path):
            continue
        for root, dirs, filenames in os.walk(path, topdown=True):
            dirs.sort()
            filenames.sort()
            for name in filenames:
                _append_batch_file(out, seen, os.path.join(root, name))
    return out
