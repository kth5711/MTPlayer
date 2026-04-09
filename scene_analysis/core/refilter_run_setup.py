from __future__ import annotations

from typing import Any, Dict
import os

from .similarity import (
    _build_pattern_prompts,
    _build_siglip2_prompts,
    _build_simple_prompts,
    _clear_siglip_embedding_errors,
    _get_siglip2_bundle,
    _imread_bgr,
    _last_siglip_image_error,
    _last_siglip_text_error,
    _scene_window_sample_cap_for_profile,
    _siglip_prompt_groups_to_tensors,
    _siglip2_text_feature,
)


def prepare_scene_similarity_run(worker) -> Dict[str, Any]:
    valid_samples, valid_texts = _scene_similarity_inputs(worker)
    _validate_scene_similarity_prompt_deps(worker, valid_samples)
    cv2, np = _load_scene_similarity_modules()
    siglip_bundle = _load_scene_similarity_siglip_bundle(worker)
    sample_prompt_groups = _build_scene_similarity_prompt_groups(worker, valid_samples, valid_texts, siglip_bundle)
    siglip_prompt_group_tensors = _build_scene_similarity_prompt_tensors(worker, sample_prompt_groups, siglip_bundle)
    return _scene_similarity_run_state(worker, cv2, np, siglip_bundle, sample_prompt_groups, siglip_prompt_group_tensors)


def _validate_scene_similarity_inputs(worker):
    if not worker.video_path or not os.path.exists(worker.video_path):
        raise RuntimeError("영상 경로가 없습니다.")
    if not worker.scene_ms:
        raise RuntimeError("재필터 대상 씬이 없습니다.")


def _validate_scene_similarity_samples(worker, valid_samples, valid_texts):
    if worker.mode in ("siglip2", "hybrid"):
        if not valid_samples and not valid_texts:
            raise RuntimeError("샘플 이미지 또는 텍스트를 입력하세요.")
        return
    if not valid_samples:
        raise RuntimeError("샘플 이미지 경로가 없습니다.")


def _load_scene_similarity_modules():
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception as exc:
        raise RuntimeError("OpenCV/Numpy 모듈이 없어 재필터 비교를 수행할 수 없습니다.") from exc
    return cv2, np


def _validate_scene_similarity_prompt_deps(worker, valid_samples):
    if worker.mode not in ("siglip2", "hybrid"):
        return
    if not valid_samples:
        return
    try:
        from PIL import Image  # type: ignore  # noqa: F401
    except Exception as exc:
        raise RuntimeError(
            "Pillow 모듈이 없어 샘플 이미지 프롬프트를 만들 수 없습니다. 설치: pip install pillow"
        ) from exc


def _load_scene_similarity_siglip_bundle(worker):
    if worker.mode not in ("siglip2", "hybrid"):
        return None
    try:
        adp = str(worker.siglip_adapter_path or "").strip()
        adp_label = f", adapter={os.path.basename(adp) or adp}" if adp else ""
        worker.message.emit(f"SigLIP2 모델 로딩 중… ({worker.siglip_model_id}{adp_label})")
        return _get_siglip2_bundle(worker.siglip_model_id, worker.siglip_adapter_path)
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc


def _build_scene_similarity_prompt_groups(worker, valid_samples, valid_texts, siglip_bundle):
    sample_prompt_groups = []
    _clear_siglip_embedding_errors()
    image_read_fail = 0
    image_prompt_fail = 0
    text_prompt_fail = 0
    for sample_path in valid_samples:
        worker._raise_if_cancelled()
        prompt_group, fail_kind = _scene_similarity_image_prompt_group(worker, sample_path, siglip_bundle)
        if prompt_group:
            sample_prompt_groups.append(prompt_group)
            continue
        if fail_kind == "read":
            image_read_fail += 1
        else:
            image_prompt_fail += 1
    if worker.mode in ("siglip2", "hybrid"):
        for txt in valid_texts:
            worker._raise_if_cancelled()
            prompt_group, fail_kind = _scene_similarity_text_prompt_group(worker, txt, siglip_bundle)
            if prompt_group:
                sample_prompt_groups.append(prompt_group)
                continue
            if fail_kind:
                text_prompt_fail += 1
    if sample_prompt_groups:
        return sample_prompt_groups
    if worker.mode in ("siglip2", "hybrid"):
        raise RuntimeError(
            _scene_similarity_prompt_failure_message(
                valid_samples,
                valid_texts,
                image_read_fail,
                image_prompt_fail,
                text_prompt_fail,
            )
        )
    raise RuntimeError("샘플 이미지 프롬프트 생성 실패")


def _scene_similarity_image_prompt_group(worker, sample_path: str, siglip_bundle):
    sample_bgr = _imread_bgr(sample_path)
    if sample_bgr is None:
        return None, "read"
    if worker.mode == "simple":
        prompts = _build_simple_prompts(sample_bgr) or []
        return ({"simple": prompts}, None) if prompts else (None, "feature")
    if worker.mode == "siglip2":
        prompts = _build_siglip2_prompts(sample_bgr, siglip_bundle) or []
        return ({"siglip": prompts}, None) if prompts else (None, "feature")
    if worker.mode == "hybrid":
        pose_prompts = _build_pattern_prompts(sample_bgr) or []
        sig_prompts = _build_siglip2_prompts(sample_bgr, siglip_bundle) or []
        return (
            ({"pose": pose_prompts, "siglip": sig_prompts}, None)
            if (pose_prompts or sig_prompts)
            else (None, "feature")
        )
    prompts = _build_pattern_prompts(sample_bgr) or []
    return ({"pose": prompts}, None) if prompts else (None, "feature")


def _scene_similarity_text_prompt_group(worker, txt: str, siglip_bundle):
    feat = _siglip2_text_feature(txt, siglip_bundle)
    if feat is None:
        return None, "feature"
    if worker.mode == "siglip2":
        return {"siglip": [feat]}, None
    return {"pose": [], "siglip": [feat]}, None


def _scene_similarity_prompt_failure_message(
    valid_samples,
    valid_texts,
    image_read_fail: int,
    image_prompt_fail: int,
    text_prompt_fail: int,
) -> str:
    parts = []
    if valid_samples:
        parts.append(
            f"이미지 {len(valid_samples)}개(읽기 실패 {image_read_fail}, 프롬프트 실패 {image_prompt_fail})"
        )
    if valid_texts:
        parts.append(f"텍스트 {len(valid_texts)}개(프롬프트 실패 {text_prompt_fail})")
    detail = ", ".join(parts) if parts else "입력 없음"
    extra = []
    img_err = _last_siglip_image_error()
    txt_err = _last_siglip_text_error()
    if img_err:
        extra.append(f"이미지 임베딩 오류: {img_err}")
    if txt_err:
        extra.append(f"텍스트 임베딩 오류: {txt_err}")
    suffix = f" | {' / '.join(extra)}" if extra else ""
    return (
        "샘플 이미지/텍스트 프롬프트 생성 실패"
        f" ({detail}). Pillow/transformers/모델 상태와 샘플 파일을 확인하세요.{suffix}"
    )


def _build_scene_similarity_prompt_tensors(worker, sample_prompt_groups, siglip_bundle):
    if worker.mode != "siglip2":
        return None
    worker._raise_if_cancelled()
    return _siglip_prompt_groups_to_tensors(sample_prompt_groups, siglip_bundle)


def _scene_similarity_frame_label(worker) -> str:
    if worker.sampling_mode == "scene_window":
        cap_n = _scene_window_sample_cap_for_profile(worker.frame_profile)
        return f"구간가변(min={worker.frame_sample_count}, max={cap_n})"
    return "패스트(씬시작 1샷)"


def _scene_similarity_inputs(worker):
    worker._raise_if_cancelled()
    _validate_scene_similarity_inputs(worker)
    valid_samples = [p for p in worker.sample_image_paths if os.path.exists(p)]
    valid_texts = list(worker.sample_texts or [])
    _validate_scene_similarity_samples(worker, valid_samples, valid_texts)
    return valid_samples, valid_texts


def _scene_similarity_run_state(worker, cv2, np, siglip_bundle, sample_prompt_groups, siglip_prompt_group_tensors):
    scene_ms_sorted = sorted(set(int(ms) for ms in (worker.scene_ms or []) if int(ms) >= 0))
    total = len(scene_ms_sorted)
    k_eff = max(1, min(worker.kofn_k, len(sample_prompt_groups)))
    return {
        "cv2": cv2,
        "np": np,
        "siglip_bundle": siglip_bundle,
        "sample_prompt_groups": sample_prompt_groups,
        "siglip_prompt_group_tensors": siglip_prompt_group_tensors,
        "scene_ms_sorted": scene_ms_sorted,
        "total": total,
        "out": [],
        "k_eff": k_eff,
        "agg_label": f"K-of-N(k={k_eff})" if worker.agg_mode == "kofn" else "최고값",
        "frame_label": _scene_similarity_frame_label(worker),
        "use_two_stage": bool(worker.mode == "siglip2" and worker.siglip_two_stage and total >= 4),
        "feature_cache_enabled": bool(worker.mode == "siglip2" and worker.siglip_scene_feature_cache),
        "coarse_feat_map": {},
        "full_feat_map": {},
        "feature_cache_dirty": False,
    }


__all__ = [
    "prepare_scene_similarity_run",
]
