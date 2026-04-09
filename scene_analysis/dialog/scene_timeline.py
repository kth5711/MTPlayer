import logging
import os
from typing import List


logger = logging.getLogger(__name__)


def _normalized_scene_ms_rows(rows) -> List[int]:
    out: List[int] = []
    for row in list(rows or []):
        try:
            ms = int(row[0])
        except (TypeError, ValueError):
            continue
        if ms >= 0:
            out.append(ms)
    out = sorted(set(out))
    if 0 not in out:
        out.insert(0, 0)
    return out


def timeline_scene_starts_sorted(dialog) -> List[int]:
    out = _normalized_scene_ms_rows(getattr(dialog, "_display_source_data", []) or [])
    if out and len(out) > 1:
        return out
    return _normalized_scene_ms_rows(getattr(dialog, "all_scenes_data", []) or [])


def timeline_scene_starts_prefilter_sorted(dialog) -> List[int]:
    override = [int(x) for x in list(getattr(dialog, "_refilter_source_override_ms", []) or []) if int(x) >= 0]
    if override:
        out = sorted(set(override))
        if 0 not in out:
            out.insert(0, 0)
        return out
    out = _normalized_scene_ms_rows(getattr(dialog, "_refilter_source_data", []) or [])
    return out if out and len(out) > 1 else timeline_scene_starts_sorted(dialog)


def _media_length_ms(dialog) -> int:
    try:
        return int(dialog.host.mediaplayer.get_length() or 0)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        logger.debug("media length probe failed", exc_info=True)
        return 0


def _cv2_video_length_ms(path: str) -> int:
    if not path or not os.path.exists(path):
        return 0
    try:
        import cv2  # type: ignore

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return 0
        try:
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        finally:
            cap.release()
        if fps > 0.0 and frame_count > 0.0:
            return max(0, int(round((frame_count / fps) * 1000.0)))
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        logger.debug("cv2 video length probe failed", exc_info=True)
    return 0


def current_video_length_ms(dialog) -> int:
    media_length = _media_length_ms(dialog)
    if media_length > 0:
        return media_length
    return _cv2_video_length_ms(getattr(dialog, "current_path", "") or "")


def scene_end_ms_from_starts(dialog, scene_start_ms: int, starts: List[int], fallback_sec: int = 3) -> int:
    start_ms = max(0, int(scene_start_ms))
    for ms in starts or []:
        if int(ms) > start_ms:
            return max(start_ms, int(ms) - 1)
    length_ms = _media_length_ms(dialog)
    if length_ms > start_ms + 1:
        return max(start_ms, length_ms - 1)
    return start_ms + max(1000, int(max(1, fallback_sec) * 1000))


def scene_end_ms(dialog, scene_start_ms: int, fallback_sec: int = 3) -> int:
    return scene_end_ms_from_starts(dialog, scene_start_ms, timeline_scene_starts_sorted(dialog), fallback_sec=fallback_sec)
