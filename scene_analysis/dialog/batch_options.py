from typing import Dict, List

from scene_analysis.core.cache import _normalize_sample_paths, _normalize_sample_texts
from scene_analysis.core.media import FFMPEG_BIN, resolve_ffmpeg_bin


def _sampling_mode_label(mode: str) -> str:
    m = str(mode or "").strip().lower()
    if m == "adaptive_window":
        m = "scene_window"
    if m == "scene_window":
        return "구간 샘플링"
    if m == "start_frame":
        return "패스트(씬시작 1샷)"
    return m or "-"


def _scene_batch_run_flags(dialog) -> Dict[str, object]:
    run_scene = _dialog_checkbox_checked(dialog, "_scene_batch_chk_scene", True)
    run_refilter = _dialog_checkbox_checked(dialog, "_scene_batch_chk_refilter", False)
    refilter_source_mode = dialog._current_refilter_source_mode() if hasattr(dialog, "_current_refilter_source_mode") else "direct"
    if run_refilter and (not run_scene):
        refilter_source_mode = "direct"
    return {
        "run_scene": run_scene,
        "run_refilter": run_refilter,
        "use_ff": True,
        "ff_hwaccel": (not bool(dialog.chk_cpu_decode.isChecked())) if hasattr(dialog, "chk_cpu_decode") else True,
        "refilter_source_mode": refilter_source_mode,
    }


def _dialog_checkbox_checked(dialog, name: str, default: bool) -> bool:
    widget = getattr(dialog, name, None)
    if widget is None or not hasattr(widget, "isChecked"):
        return bool(default)
    return bool(widget.isChecked())


def _scene_batch_scan_options(dialog) -> Dict[str, object]:
    return {
        "thr": float(dialog.spn_thr.value()) if hasattr(dialog, "spn_thr") else 0.35,
        "dw": int(dialog.spn_dw.value()) if hasattr(dialog, "spn_dw") else 320,
        "fps": int(dialog.spn_fps.value()) if hasattr(dialog, "spn_fps") else 5,
        "ffbin": _scene_batch_ffmpeg_bin(dialog),
        "use_cache": bool(dialog.chk_use_cache.isChecked()) if hasattr(dialog, "chk_use_cache") else True,
        "scene_topk": int(dialog.spn_topk.value()) if hasattr(dialog, "spn_topk") else 0,
        "scene_mingap": int(dialog.spn_mingap.value()) if hasattr(dialog, "spn_mingap") else 0,
        "decode_chunk_size": int(
            dialog._current_siglip_batch_size() if hasattr(dialog, "_current_siglip_batch_size") else 64
        ),
        "sim_thr": float(dialog.spn_sim_thr.value()) if hasattr(dialog, "spn_sim_thr") else 0.70,
    }


def _scene_batch_ffmpeg_bin(dialog) -> str:
    return resolve_ffmpeg_bin(
        (str(dialog.ed_ff.text()).strip() if hasattr(dialog, "ed_ff") else "") or FFMPEG_BIN
    )


def _scene_batch_sample_options(dialog) -> Dict[str, object]:
    return {
        "sample_image_paths": _normalize_sample_paths(getattr(dialog, "sample_image_paths", []) or []),
        "sample_texts": _normalize_sample_texts(
            dialog._current_sample_texts() if hasattr(dialog, "_current_sample_texts") else []
        ),
    }


def _scene_batch_refilter_options(dialog) -> Dict[str, object]:
    return {
        "refilter_mode": dialog._current_refilter_mode() if hasattr(dialog, "_current_refilter_mode") else "siglip2",
        "refilter_direct_sec": int(
            dialog._current_refilter_direct_sec() if hasattr(dialog, "_current_refilter_direct_sec") else 2
        ),
        "agg_mode": dialog._current_refilter_agg_mode() if hasattr(dialog, "_current_refilter_agg_mode") else "max",
        "kofn_k": int(dialog._current_kofn_k() if hasattr(dialog, "_current_kofn_k") else 1),
        "frame_profile": dialog._current_frame_profile() if hasattr(dialog, "_current_frame_profile") else "normal",
        "sampling_mode": dialog._current_refilter_sampling_mode() if hasattr(dialog, "_current_refilter_sampling_mode") else "start_frame",
        "siglip_model_id": dialog._current_siglip_model_id() if hasattr(dialog, "_current_siglip_model_id") else "",
        "siglip_adapter_path": dialog._current_siglip_adapter_path() if hasattr(dialog, "_current_siglip_adapter_path") else "",
        "siglip_batch_size": int(
            dialog._current_siglip_batch_size() if hasattr(dialog, "_current_siglip_batch_size") else 64
        ),
        "siglip_decode_hwaccel": (not bool(dialog.chk_cpu_decode.isChecked())) if hasattr(dialog, "chk_cpu_decode") else True,
        "siglip_two_stage": bool(
            dialog._current_siglip_two_stage() if hasattr(dialog, "_current_siglip_two_stage") else False
        ),
        "siglip_stage2_ratio": float(
            dialog._current_siglip_stage2_ratio() if hasattr(dialog, "_current_siglip_stage2_ratio") else 0.35
        ),
        "siglip_scene_feature_cache": True,
        "siglip_ffmpeg_bin": _scene_batch_ffmpeg_bin(dialog),
        "siglip_ffmpeg_scale_w": int(
            dialog._current_siglip_decode_scale_w() if hasattr(dialog, "_current_siglip_decode_scale_w") else 0
        ),
    }


def _scene_batch_option_snapshot(dialog) -> Dict[str, object]:
    options = {}
    options.update(_scene_batch_run_flags(dialog))
    options.update(_scene_batch_scan_options(dialog))
    options.update(_scene_batch_sample_options(dialog))
    options.update(_scene_batch_refilter_options(dialog))
    return options


def _scene_batch_option_text(options: Dict[str, object]) -> str:
    parts: List[str] = [
        f"현재 옵션: {_scene_batch_work_label(options)}",
        _scene_batch_decode_label(options),
    ]
    if bool(options.get("run_scene", True)):
        parts.append(_scene_batch_scan_text(options))
    if bool(options.get("run_refilter", False)):
        parts.append(_scene_batch_refilter_text(options))
    parts.append("캐시 사용" if bool(options.get("use_cache", True)) else "캐시 미사용")
    parts.append("결과기록만 저장, 썸네일 생략")
    return " | ".join(parts)


def _scene_batch_work_label(options: Dict[str, object]) -> str:
    modes: List[str] = []
    if bool(options.get("run_scene", True)):
        modes.append("씬변화")
    if bool(options.get("run_refilter", False)):
        if bool(options.get("run_scene", True)):
            modes.append("유사씬(씬변화 결과)")
        else:
            modes.append(f"유사씬(직행 {int(options.get('refilter_direct_sec', 2))}s)")
    return " + ".join(modes) if modes else "작업 없음"


def _scene_batch_decode_label(options: Dict[str, object]) -> str:
    run_scene = bool(options.get("run_scene", True))
    decode_on = bool(options.get("ff_hwaccel", False)) if run_scene else bool(options.get("siglip_decode_hwaccel", False))
    return "기본 GPU 우선" if decode_on else "CPU 디코드"


def _scene_batch_scan_text(options: Dict[str, object]) -> str:
    return (
        f"scan thr={float(options.get('thr', 0.35)):.2f}, "
        f"dw={int(options.get('dw', 320))}, fps={int(options.get('fps', 5))}, "
        f"TopK={int(options.get('scene_topk', 0))}, MinGap={int(options.get('scene_mingap', 0))}"
    )


def _scene_batch_refilter_text(options: Dict[str, object]) -> str:
    source_label = _scene_batch_refilter_source_label(options)
    img_n = len(list(options.get("sample_image_paths") or []))
    txt_n = len(list(options.get("sample_texts") or []))
    return (
        f"{source_label}, sim={float(options.get('sim_thr', 0.70)):.2f}, "
        f"agg={str(options.get('agg_mode') or 'max')}, "
        f"sampling={_sampling_mode_label(str(options.get('sampling_mode') or 'start_frame'))}, "
        f"샘플 img={img_n}, text={txt_n}, "
        "영상캐시=자동"
    )


def _scene_batch_refilter_source_label(options: Dict[str, object]) -> str:
    if bool(options.get("run_scene", True)):
        return "src=씬결과"
    return f"src=직행 {int(options.get('refilter_direct_sec', 2))}s"
