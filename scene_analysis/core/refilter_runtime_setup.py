from __future__ import annotations

from typing import Any, Dict

from .media import (
    TORCHCODEC_HINT,
    _open_torchcodec_video,
)
from .similarity import (
    _open_video_capture_for_siglip,
    _siglip_decode_scale_label,
    _siglip2_image_params,
    _siglip_effective_pre_resize_width,
    _siglip_torchcodec_resize_dims,
)


def prepare_scene_similarity_runtime(worker, setup_state, siglip_bundle) -> Dict[str, Any]:
    runtime_state = _scene_similarity_runtime_state(worker, siglip_bundle)
    runtime_state["video_len_ms"] = _scene_similarity_video_length_ms(runtime_state, setup_state["cv2"])
    _emit_scene_similarity_start_message(worker, setup_state, runtime_state)
    return runtime_state


def _scene_similarity_runtime_state(worker, siglip_bundle):
    runtime_state = _scene_similarity_base_runtime_state(worker, siglip_bundle)
    if worker.siglip_decode_hwaccel:
        _scene_similarity_open_gpu_backends(worker, runtime_state)
        if _scene_similarity_needs_opencv_fallback(runtime_state):
            worker.message.emit("SigLIP2 디코드 GPU backend 실패 → CPU fallback 단계")
    if _scene_similarity_needs_opencv_fallback(runtime_state):
        _scene_similarity_open_cpu_backends(worker, runtime_state)
    if _scene_similarity_needs_opencv_fallback(runtime_state):
        _scene_similarity_open_opencv(worker, runtime_state, prefer_gpu_decode=False)
    _scene_similarity_validate_runtime_state(runtime_state)
    return runtime_state


def _scene_similarity_base_runtime_state(worker, siglip_bundle):
    tc_resize_dims = _siglip_torchcodec_resize_dims(worker.video_path, worker.siglip_ffmpeg_scale_w) if worker.mode == "siglip2" else None
    siglip_pre_resize_w = _siglip_effective_pre_resize_width(worker.video_path, worker.siglip_ffmpeg_scale_w)
    if worker.mode == "siglip2":
        _siglip2_image_params(siglip_bundle)
    return {
        "video_path": worker.video_path,
        "tc_reader": None, "tc_fps": 0.0, "tc_dur_sec": 0.0,
        "cap": None, "decode_mode": "", "decode_label": "",
        "tc_resize_dims": tc_resize_dims,
        "tc_decode_resize_label": "",
        "selected_decode_scale_label": _siglip_decode_scale_label(worker.siglip_ffmpeg_scale_w),
        "siglip_pre_resize_w": siglip_pre_resize_w,
        "decode_stats": {"torchcodec": 0, "opencv": 0},
        "tc_runtime_warned": False,
        "cap_lazy_open_failed": False, "tc_cpu_fallback_warned": False,
    }


def _scene_similarity_open_gpu_backends(worker, runtime_state):
    _scene_similarity_open_torchcodec(
        worker,
        runtime_state,
        prefer_gpu=True,
        allow_cpu_fallback=False,
    )
    if runtime_state["tc_reader"] is not None:
        return
    _scene_similarity_open_opencv(
        worker,
        runtime_state,
        prefer_gpu_decode=True,
        allow_cpu_fallback=False,
    )


def _scene_similarity_open_cpu_backends(worker, runtime_state):
    _scene_similarity_open_torchcodec(
        worker,
        runtime_state,
        prefer_gpu=False,
        allow_cpu_fallback=True,
    )


def _scene_similarity_open_torchcodec(worker, runtime_state, *, prefer_gpu: bool, allow_cpu_fallback: bool):
    tc_reader, tc_fps, tc_dur_sec, tc_mode = _open_torchcodec_video(
        worker.video_path,
        prefer_gpu=prefer_gpu,
        resize_dims=runtime_state["tc_resize_dims"],
        allow_cpu_fallback=allow_cpu_fallback,
    )
    runtime_state["tc_reader"] = tc_reader
    runtime_state["tc_fps"] = float(tc_fps or 0.0)
    runtime_state["tc_dur_sec"] = float(tc_dur_sec or 0.0)
    if tc_reader is None:
        return
    tc_mode_s = str(tc_mode or "").strip().lower()
    runtime_state["decode_label"] = "TorchCodec(GPU)" if "gpu" in tc_mode_s else "TorchCodec(CPU)"
    worker.message.emit(TORCHCODEC_HINT)
    if runtime_state["tc_resize_dims"] is not None:
        runtime_state["tc_decode_resize_label"] = (
            f"{int(runtime_state['tc_resize_dims'][1])}x{int(runtime_state['tc_resize_dims'][0])}(TorchCodec)"
        )
        worker.message.emit(
            f"SigLIP2 TorchCodec 디코드 크기 제한: "
            f"{int(runtime_state['tc_resize_dims'][1])}x{int(runtime_state['tc_resize_dims'][0])} "
            f"({runtime_state['selected_decode_scale_label']})"
        )
    if worker.mode == "siglip2":
        runtime_state["siglip_pre_resize_w"] = 0


def _scene_similarity_needs_opencv_fallback(runtime_state):
    cap = runtime_state.get("cap")
    return runtime_state["tc_reader"] is None and (cap is None or (not cap.isOpened()))


def _scene_similarity_open_opencv(worker, runtime_state, *, prefer_gpu_decode: bool, allow_cpu_fallback: bool = True):
    cap, decode_mode = _open_video_capture_for_siglip(
        worker.video_path,
        prefer_gpu_decode=prefer_gpu_decode,
        allow_cpu_fallback=allow_cpu_fallback,
    )
    runtime_state["cap"] = cap
    runtime_state["decode_mode"] = str(decode_mode or "")
    if cap is None or (not cap.isOpened()):
        return
    dmode = str(runtime_state["decode_mode"]).strip().lower()
    runtime_state["decode_label"] = "OpenCV(GPU)" if dmode.startswith("gpu") else "OpenCV(CPU)"


def _scene_similarity_validate_runtime_state(runtime_state):
    if _scene_similarity_needs_opencv_fallback(runtime_state):
        cap = runtime_state["cap"]
        if cap is None or (not cap.isOpened()):
            raise RuntimeError("영상 열기 실패: 재필터를 진행할 수 없습니다.")


def _scene_similarity_video_length_ms(runtime_state, cv2):
    if runtime_state["tc_reader"] is not None and float(runtime_state["tc_dur_sec"]) > 0.0:
        return _scene_similarity_duration_ms(runtime_state["tc_dur_sec"])
    if runtime_state["cap"] is not None:
        return _scene_similarity_cap_length_ms(runtime_state["cap"], cv2)
    return 0


def _scene_similarity_duration_ms(duration_sec):
    try:
        return int(round(float(duration_sec) * 1000.0))
    except Exception:
        return 0


def _scene_similarity_cap_length_ms(cap, cv2):
    try:
        fps_val = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        if fps_val > 0.0 and frame_count > 0.0:
            return int(round((frame_count / fps_val) * 1000.0))
    except Exception:
        return 0
    return 0


def _emit_scene_similarity_start_message(worker, setup_state, runtime_state):
    total = int(setup_state["total"])
    sample_count = len(setup_state["sample_prompt_groups"])
    agg_label = str(setup_state["agg_label"])
    frame_label = str(setup_state["frame_label"])
    decode_label = str(runtime_state["decode_label"])
    if worker.mode == "simple":
        worker.message.emit(f"단순 재필터 분석 중… ({total}개, 샘플 {sample_count}개, {agg_label}, {frame_label}, {decode_label})")
        return
    if worker.mode == "siglip2":
        worker.message.emit(_scene_similarity_siglip_message(worker, total, sample_count, agg_label, frame_label, runtime_state, bool(setup_state["use_two_stage"])))
        return
    if worker.mode == "hybrid":
        worker.message.emit(
            f"하이브리드 재필터 분석 중… ({total}개, 샘플 {sample_count}개, "
            f"SigLIP비중={worker.hybrid_siglip_weight:.2f}, {agg_label}, {frame_label}, {decode_label})"
        )
        return
    worker.message.emit(f"구도/포즈 재필터 분석 중… ({total}개, 샘플 {sample_count}개, {agg_label}, {frame_label}, {decode_label})")


def _scene_similarity_siglip_message(worker, total, sample_count, agg_label, frame_label, runtime_state, use_two_stage):
    adp = str(worker.siglip_adapter_path or "").strip()
    adp_label = f", adapter={os.path.basename(adp) or adp}" if adp else ""
    stage_label = ", 2단계(1차/2차)" if use_two_stage else ""
    decode_scale_label = runtime_state["tc_decode_resize_label"] or runtime_state["selected_decode_scale_label"]
    return (
        f"SigLIP2 재필터 분석 중… ({total}개, 샘플 {sample_count}개, "
        f"모델={worker.siglip_model_id}{adp_label}, {agg_label}, {frame_label}, {runtime_state['decode_label']}, "
        f"배치=자동기준({worker.siglip_batch_size})/현재({worker._siglip_batch_auto}), "
        f"처리크기={decode_scale_label}{stage_label})"
    )


__all__ = ["prepare_scene_similarity_runtime"]
