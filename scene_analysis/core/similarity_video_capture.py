from __future__ import annotations

import os


def _open_video_capture_for_siglip(video_path: str, prefer_gpu_decode: bool = False, allow_cpu_fallback: bool = True):
    try:
        import cv2  # type: ignore
    except Exception:
        return None, "cv2-unavailable"
    if not prefer_gpu_decode:
        cap = _open_video_capture_default(cv2, video_path)
        return cap, ("cpu" if cap is not None else "open-failed")
    cap, decode_mode = _open_video_capture_gpu(cv2, video_path)
    if cap is not None:
        return cap, decode_mode
    cap, decode_mode = _open_video_capture_env_gpu(cv2, video_path)
    if cap is not None:
        return cap, decode_mode
    if not bool(allow_cpu_fallback):
        return None, "gpu-open-failed"
    cap = _open_video_capture_default(cv2, video_path)
    return cap, ("cpu-fallback" if cap is not None else "open-failed")


def _open_video_capture_default(cv2, video_path: str):
    cap = cv2.VideoCapture(video_path)
    if cap is not None and cap.isOpened():
        return cap
    try:
        if cap is not None:
            cap.release()
    except Exception:
        pass
    return None


def _open_video_capture_gpu(cv2, video_path: str):
    try:
        backend = cv2.CAP_FFMPEG if hasattr(cv2, "CAP_FFMPEG") else 0
        cap = cv2.VideoCapture(video_path, backend) if backend else cv2.VideoCapture(video_path)
        if cap is None or (not cap.isOpened()):
            _release_capture(cap)
            return None, "open-failed"
        used_hw = _try_enable_hw_decode(cv2, cap)
        if cap.isOpened():
            return cap, ("gpu-opencv" if used_hw else "ffmpeg-nohw")
        _release_capture(cap)
    except Exception:
        return None, "open-failed"
    return None, "open-failed"


def _try_enable_hw_decode(cv2, cap) -> bool:
    used_hw = False
    if hasattr(cv2, "CAP_PROP_HW_ACCELERATION"):
        hw_any = getattr(cv2, "VIDEO_ACCELERATION_ANY", None)
        if hw_any is not None:
            try:
                used_hw = bool(cap.set(cv2.CAP_PROP_HW_ACCELERATION, float(hw_any)))
            except Exception:
                used_hw = False
    if hasattr(cv2, "CAP_PROP_HW_DEVICE"):
        try:
            cap.set(cv2.CAP_PROP_HW_DEVICE, 0.0)
        except Exception:
            pass
    return bool(used_hw)


def _open_video_capture_env_gpu(cv2, video_path: str):
    env_key = "OPENCV_FFMPEG_CAPTURE_OPTIONS"
    old_env = os.environ.get(env_key)
    try:
        for opt in ("hwaccel;cuda", "hwaccel;cuda|video_codec;h264_cuvid", "hwaccel;cuda|video_codec;hevc_cuvid"):
            cap = _open_video_capture_with_env(cv2, video_path, env_key, opt)
            if cap is not None:
                return cap, f"gpu-env:{opt}"
    finally:
        _restore_capture_env(env_key, old_env)
    return None, "open-failed"


def _open_video_capture_with_env(cv2, video_path: str, env_key: str, option: str):
    try:
        os.environ[env_key] = option
        backend = cv2.CAP_FFMPEG if hasattr(cv2, "CAP_FFMPEG") else 0
        cap = cv2.VideoCapture(video_path, backend) if backend else cv2.VideoCapture(video_path)
        if cap is not None and cap.isOpened():
            return cap
        _release_capture(cap)
    except Exception:
        return None
    return None


def _restore_capture_env(env_key: str, old_env: str | None):
    try:
        if old_env is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = old_env
    except Exception:
        pass


def _release_capture(cap):
    try:
        if cap is not None:
            cap.release()
    except Exception:
        pass


__all__ = ["_open_video_capture_for_siglip"]
