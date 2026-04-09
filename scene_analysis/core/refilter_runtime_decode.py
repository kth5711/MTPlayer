from __future__ import annotations

from .media import _torchcodec_frame_bgr_at_ms
from .similarity import _open_video_capture_for_siglip


def read_frame_at_ms(worker, state, cv2, t_ms: int, prefer_cpu_fallback: bool = False):
    worker._raise_if_cancelled()
    frame = _read_torchcodec_frame(worker, state, cv2, int(t_ms), prefer_cpu_fallback)
    if frame is not None:
        return frame
    return _read_opencv_frame(state, cv2, int(t_ms))


def _downscale_if_needed(frame_bgr, cv2, pre_resize_w: int):
    if frame_bgr is None or int(pre_resize_w) <= 0:
        return frame_bgr
    try:
        h0, w0 = frame_bgr.shape[:2]
        if int(w0) > int(pre_resize_w):
            nh = max(2, int(round(float(h0) * (float(pre_resize_w) / float(max(1, int(w0)))))))
            return cv2.resize(frame_bgr, (int(pre_resize_w), int(nh)), interpolation=cv2.INTER_AREA)
    except Exception:
        return frame_bgr
    return frame_bgr


def _ensure_cpu_capture(state):
    if state["cap"] is not None or bool(state["cap_lazy_open_failed"]):
        return
    cap, decode_mode = _open_video_capture_for_siglip(state["video_path"], prefer_gpu_decode=False)
    if cap is None or (not cap.isOpened()):
        state["cap"] = None
        state["cap_lazy_open_failed"] = True
        return
    state["cap"] = cap
    state["decode_mode"] = decode_mode


def _read_torchcodec_frame(worker, state, cv2, t_ms: int, prefer_cpu_fallback: bool):
    if bool(prefer_cpu_fallback) or state["tc_reader"] is None:
        return None
    frame = _torchcodec_frame_bgr_at_ms(state["tc_reader"], int(t_ms), downscale_w=state["siglip_pre_resize_w"])
    if frame is not None:
        state["decode_stats"]["torchcodec"] = int(state["decode_stats"].get("torchcodec", 0)) + 1
        return frame
    if not bool(state["tc_runtime_warned"]):
        worker.message.emit("SigLIP2 TorchCodec 프레임 읽기 실패 감지 → OpenCV 폴백")
        state["tc_runtime_warned"] = True
    _ensure_cpu_capture(state)
    return None


def _read_opencv_frame(state, cv2, t_ms: int):
    cap = state["cap"]
    if cap is None:
        return None
    cap.set(cv2.CAP_PROP_POS_MSEC, int(t_ms))
    ok, frame = cap.read()
    if not ok or frame is None:
        return None
    frame = _downscale_if_needed(frame, cv2, int(state["siglip_pre_resize_w"]))
    state["decode_stats"]["opencv"] = int(state["decode_stats"].get("opencv", 0)) + 1
    return frame


__all__ = ["read_frame_at_ms"]
