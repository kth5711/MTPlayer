from __future__ import annotations

from .refilter_runtime_decode import read_frame_at_ms
from .similarity import _build_pattern_profile, _build_simple_feature, _pattern_similarity, _siglip2_feature, _simple_similarity


def score_non_siglip_times(worker, state, t_list, sample_prompt_groups, siglip_bundle):
    import cv2  # type: ignore

    sample_time_scores = [[] for _ in range(len(sample_prompt_groups))]
    for t_ms in t_list:
        worker._raise_if_cancelled()
        frame = read_frame_at_ms(worker, state, cv2, int(t_ms))
        if frame is None:
            continue
        if worker.mode == "simple":
            _append_simple_scores(frame, sample_prompt_groups, sample_time_scores)
        elif worker.mode == "hybrid":
            _append_hybrid_scores(worker, frame, sample_prompt_groups, sample_time_scores, siglip_bundle)
        else:
            _append_pose_scores(worker, frame, sample_prompt_groups, sample_time_scores)
    return sample_time_scores


def _append_simple_scores(frame, sample_prompt_groups, sample_time_scores):
    frame_simple = _build_simple_feature(frame)
    if frame_simple is None:
        return
    for s_idx, grp in enumerate(sample_prompt_groups):
        score = 0.0
        for prompt in (grp.get("simple") or []):
            score = max(score, _simple_similarity(prompt, frame_simple))
        sample_time_scores[s_idx].append(float(score))


def _append_hybrid_scores(worker, frame, sample_prompt_groups, sample_time_scores, siglip_bundle):
    frame_pose = _build_pattern_profile(frame)
    frame_siglip = _siglip2_feature(frame, siglip_bundle)
    if frame_pose is None and frame_siglip is None:
        return
    for s_idx, grp in enumerate(sample_prompt_groups):
        sample_time_scores[s_idx].append(_hybrid_group_score(worker, grp, frame_pose, frame_siglip))


def _hybrid_group_score(worker, grp, frame_pose, frame_siglip):
    pose_score = _pose_prompt_score(worker, grp, frame_pose)
    sig_score = _siglip_prompt_score(grp, frame_siglip)
    w_sig = worker.hybrid_siglip_weight
    w_pose = max(0.0, 1.0 - w_sig)
    parts = []
    if pose_score is not None and w_pose > 0.0:
        parts.append((w_pose, float(pose_score)))
    if sig_score is not None and w_sig > 0.0:
        parts.append((w_sig, float(sig_score)))
    if not parts:
        return float(pose_score if pose_score is not None else (sig_score or 0.0))
    ws = sum(w for w, _ in parts)
    return float(sum((w * s) for w, s in parts) / max(1e-12, ws))


def _append_pose_scores(worker, frame, sample_prompt_groups, sample_time_scores):
    frame_pose = _build_pattern_profile(frame)
    if frame_pose is None:
        return
    for s_idx, grp in enumerate(sample_prompt_groups):
        sample_time_scores[s_idx].append(float(_pose_prompt_score(worker, grp, frame_pose) or 0.0))


def _pose_prompt_score(worker, grp, frame_pose):
    if frame_pose is None:
        return None
    score = 0.0
    prompts = grp.get("pose") or []
    for prompt in prompts:
        score = max(score, _pattern_similarity(prompt, frame_pose, worker.pose_weights))
    return score if prompts else None


def _siglip_prompt_score(grp, frame_siglip):
    if frame_siglip is None:
        return None
    score = 0.0
    prompts = grp.get("siglip") or []
    for prompt in prompts:
        score = max(score, _simple_similarity(prompt, frame_siglip))
    return score if prompts else None


__all__ = ["score_non_siglip_times"]
