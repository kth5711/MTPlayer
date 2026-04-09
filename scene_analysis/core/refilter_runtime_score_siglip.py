from __future__ import annotations

from .refilter_feature_rows import _siglip_feature_rows_from_any, _siglip_feature_rows_from_list
from .refilter_runtime_decode import read_frame_at_ms
from .refilter_runtime_score_siglip_batch import collect_siglip_batch_tensor
from .similarity import _aggregate_sample_scores, _aggregate_temporal_scores, _open_video_capture_for_siglip, _siglip2_scene_score_gpu, _simple_similarity


def score_siglip_times(worker, state, t_list, sample_prompt_groups, siglip_bundle, prompt_tensors, np_mod, return_siglip_rows):
    feats_t, used_batch_decode = collect_siglip_batch_tensor(worker, state, t_list, siglip_bundle)
    if feats_t is not None and prompt_tensors is not None:
        scene_siglip_rows = _siglip_feature_rows_from_any(feats_t, siglip_bundle) if bool(return_siglip_rows) else None
        score_gpu = _siglip2_scene_score_gpu(feats_t, prompt_tensors, worker.agg_mode, worker.kofn_k, siglip_bundle)
        if score_gpu is not None:
            return float(score_gpu), scene_siglip_rows
    feats = _collect_siglip_frame_features(worker, state, t_list, siglip_bundle, used_batch_decode)
    scene_siglip_rows = _siglip_feature_rows_from_list(feats) if bool(return_siglip_rows) else None
    sample_time_scores = [[] for _ in range(len(sample_prompt_groups))]
    for frame_siglip in feats:
        worker._raise_if_cancelled()
        _append_siglip_scores(frame_siglip, sample_prompt_groups, sample_time_scores)
    sample_scores = [_aggregate_temporal_scores(scores) for scores in sample_time_scores]
    return float(_aggregate_sample_scores(sample_scores, worker.agg_mode, worker.kofn_k)), scene_siglip_rows


def _collect_siglip_frame_features(worker, state, t_list, siglip_bundle, used_batch_decode: bool):
    import cv2  # type: ignore

    prefer_cpu_fallback = _ensure_siglip_cpu_fallback(worker, state)
    if used_batch_decode or (state.get("tc_reader") is not None and state.get("cap") is None):
        return []
    frames = []
    for t_ms in t_list:
        worker._raise_if_cancelled()
        frame = read_frame_at_ms(worker, state, cv2, int(t_ms), prefer_cpu_fallback=prefer_cpu_fallback)
        if frame is not None:
            frames.append(frame)
    return worker._siglip_feats_from_bgr_auto(frames, siglip_bundle)


def _ensure_siglip_cpu_fallback(worker, state):
    if state.get("tc_reader") is None or state.get("cap") is not None or bool(state.get("cap_lazy_open_failed")):
        return bool(state.get("tc_reader") is not None and state.get("cap") is not None)
    cap, decode_mode = _open_video_capture_for_siglip(state["video_path"], prefer_gpu_decode=False)
    if cap is None or (not cap.isOpened()):
        state["cap"] = None
        state["cap_lazy_open_failed"] = True
        return False
    state["cap"] = cap
    state["decode_mode"] = decode_mode
    if not bool(state.get("tc_cpu_fallback_warned")):
        worker.message.emit("SigLIP2 TorchCodec 미스 구간 감지 → OpenCV CPU 예비 폴백 활성화")
        state["tc_cpu_fallback_warned"] = True
    return True


def _append_siglip_scores(frame_siglip, sample_prompt_groups, sample_time_scores):
    if frame_siglip is None:
        return
    for s_idx, grp in enumerate(sample_prompt_groups):
        score = 0.0
        for prompt in (grp.get("siglip") or []):
            score = max(score, _simple_similarity(prompt, frame_siglip))
        sample_time_scores[s_idx].append(float(score))


__all__ = ["score_siglip_times"]
