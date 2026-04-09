from __future__ import annotations

from typing import List, Tuple

from .similarity_siglip_bundle import (
    _get_siglip2_bundle,
    _normalize_adapter_path,
    _siglip2_default_adapter_path,
    _siglip2_image_params,
)
from .similarity_siglip_embeddings import (
    _build_siglip2_prompts,
    _clear_siglip_embedding_errors,
    _last_siglip_image_error,
    _last_siglip_text_error,
    _siglip2_feature,
    _siglip2_features_batch,
    _siglip2_text_feature,
)
from . import similarity_pattern as _similarity_pattern
from . import similarity_pose as _similarity_pose
from . import similarity_siglip_rgb_batch as _similarity_siglip_rgb_batch
from .similarity_siglip_scoring import _siglip_prompt_groups_to_tensors, _siglip2_scene_score_gpu
from .similarity_siglip_config import (
    DEFAULT_SIGLIP2_MODEL_ID,
    SIGLIP_DECODE_SCALE_ORIGINAL,
    SIGLIP_TORCHCODEC_MAX_SHORT_SIDE,
    _auto_decode_chunk_batch_limits,
    _cpu_auto_worker_count,
    _cpu_decode_chunk_batch_limits,
    _gpu_decode_chunk_batch_limits,
    _normalize_siglip_decode_scale_w,
    _siglip_decode_scale_label,
    _siglip_decode_scale_signature,
    _siglip_effective_pre_resize_width,
    _siglip_resize_dims_for_width,
    _siglip_torchcodec_resize_dims,
    _siglip2_default_model_id,
    _video_frame_size,
)
from .similarity_video_capture import _open_video_capture_for_siglip
from .similarity_image_utils import _center_crop, _imread_bgr, _normalize_vec

POSE_COMP_KEYS = _similarity_pose.POSE_COMP_KEYS
POSE_COMP_LABELS = _similarity_pose.POSE_COMP_LABELS
POSE_COMP_PROFILES = _similarity_pose.POSE_COMP_PROFILES
_detect_person_boxes = _similarity_pose._detect_person_boxes
_extract_pose_feature = _similarity_pose._extract_pose_feature
_get_mediapipe_pose_estimator = _similarity_pose._get_mediapipe_pose_estimator
_layout_feature_from_boxes = _similarity_pose._layout_feature_from_boxes
_normalize_pose_weights = _similarity_pose._normalize_pose_weights
_pose_weight_signature = _similarity_pose._pose_weight_signature
_release_mediapipe_pose_estimator = _similarity_pose._release_mediapipe_pose_estimator

_build_pattern_profile = _similarity_pattern._build_pattern_profile
_build_pattern_prompts = _similarity_pattern._build_pattern_prompts
_pattern_similarity = _similarity_pattern._pattern_similarity

_siglip2_features_from_rgb_tensor_batch = (
    _similarity_siglip_rgb_batch._siglip2_features_from_rgb_tensor_batch
)

REFILTER_FRAME_PROFILES: dict[str, tuple[int, ...]] = {
    "normal": (0, -120, 120),
    "wide": (0, -180, 180, -360, 360),
    "high": (0, -80, 80, -160, 160, -240, 240, -320, 320),
}
REFILTER_SAMPLING_MODES: tuple[str, ...] = ("start_frame", "scene_window")

def _normalize_refilter_mode(mode: str) -> str:
    m = str(mode or "").strip().lower()
    if m in ("simple", "pose_comp", "siglip2", "hybrid"):
        return m
    return "pose_comp"


def _normalize_refilter_agg_mode(mode: str) -> str:
    m = str(mode or "").strip().lower()
    if m in ("max", "kofn"):
        return m
    return "max"


def _normalize_refilter_sampling_mode(mode: str) -> str:
    m = str(mode or "").strip().lower()
    if m == "adaptive_window":
        return "scene_window"
    if m in REFILTER_SAMPLING_MODES:
        return m
    return "start_frame"


def _frame_offsets_for_profile(profile: str) -> tuple[int, ...]:
    p = str(profile or "").strip().lower()
    if p not in REFILTER_FRAME_PROFILES:
        p = "normal"
    return tuple(int(x) for x in REFILTER_FRAME_PROFILES[p])


def _frame_sample_count_for_profile(profile: str) -> int:
    return max(1, len(_frame_offsets_for_profile(profile)))


def _scene_window_sample_cap_for_profile(profile: str) -> int:
    p = str(profile or "").strip().lower()
    if p == "high":
        return 24
    if p == "wide":
        return 18
    return 12


def _scene_window_dynamic_sample_count(start_ms: int, end_ms: int, base_count: int, profile: str) -> int:
    s = max(0, int(start_ms))
    e = max(s, int(end_ms))
    base_n = max(1, int(base_count))
    cap_n = max(base_n, _scene_window_sample_cap_for_profile(profile))
    span_sec = max(0.0, float(e - s) / 1000.0)
    dyn_n = int(round(span_sec / 1.8))
    n = max(base_n, dyn_n)
    return max(base_n, min(cap_n, n))


def _scene_window_sample_times(start_ms: int, end_ms: int, sample_count: int) -> List[int]:
    s = max(0, int(start_ms))
    e = max(s, int(end_ms))
    n = max(1, int(sample_count))
    if n <= 1 or e <= s:
        return [s]

    span = max(1, e - s)
    margin = int(round(span * 0.10))
    margin = max(0, min(margin, 500))
    left = s + margin
    right = e - margin
    if right <= left:
        left, right = s, e

    out: List[int] = []
    seen = set()
    for i in range(n):
        if n <= 1:
            t = left
        else:
            t = left + int(round((right - left) * (i / float(n - 1))))
        t = max(s, min(e, int(t)))
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    if not out:
        out.append(s)
    return out


def _pick_anchor_times(times_ms: List[int], max_count: int = 3) -> List[int]:
    vals = sorted(set(int(x) for x in (times_ms or []) if int(x) >= 0))
    if not vals:
        return []
    n = max(1, int(max_count))
    if len(vals) <= n:
        return vals
    out = [vals[0]]
    if n >= 3 and len(vals) >= 3:
        out.append(vals[len(vals) // 2])
    if n >= 2:
        out.append(vals[-1])
    return sorted(set(out))


def _pick_anchor_positions(count: int, max_count: int = 3) -> List[int]:
    n_vals = max(0, int(count))
    n = max(1, int(max_count))
    if n_vals <= 0:
        return []
    if n_vals <= n:
        return list(range(n_vals))
    out = [0]
    if n >= 3 and n_vals >= 3:
        out.append(n_vals // 2)
    if n >= 2:
        out.append(n_vals - 1)
    return sorted(set(int(x) for x in out if 0 <= int(x) < n_vals))


def _aggregate_temporal_scores(frame_scores: List[float]) -> float:
    vals = [max(0.0, min(1.0, float(v))) for v in (frame_scores or [])]
    if not vals:
        return 0.0
    vals.sort(reverse=True)
    n = len(vals)
    if n >= 7:
        k = 3
    elif n >= 3:
        k = 2
    else:
        k = 1
    k = max(1, min(k, n))
    head = vals[:k]
    return max(0.0, min(1.0, float(sum(head) / float(len(head)))))


def _aggregate_sample_scores(sample_scores: List[float], agg_mode: str, kofn_k: int) -> float:
    vals = [max(0.0, min(1.0, float(v))) for v in (sample_scores or [])]
    if not vals:
        return 0.0
    mode = _normalize_refilter_agg_mode(agg_mode)
    if mode == "kofn":
        vals.sort(reverse=True)
        k = max(1, min(int(kofn_k), len(vals)))
        head = vals[:k]
        return max(0.0, min(1.0, float(sum(head) / max(1, len(head)))))
    return max(vals)


def _robust_renorm_similarity_pairs(pairs: List[tuple[int, float]]) -> List[tuple[int, float]]:
    out = [(int(ms), float(s)) for ms, s in (pairs or [])]
    if len(out) < 5:
        return out
    try:
        import numpy as np  # type: ignore

        sims = np.asarray([float(s) for _, s in out], dtype=np.float32)
        lo = float(np.percentile(sims, 10))
        hi = float(np.percentile(sims, 90))
        if hi - lo <= 1e-6:
            return out
        renorm: List[tuple[int, float]] = []
        for ms, s in out:
            v = (float(s) - lo) / (hi - lo)
            renorm.append((int(ms), max(0.0, min(1.0, float(v)))))
        return renorm
    except Exception:
        return out

def _build_simple_feature(img_bgr):
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return None
    if img_bgr is None:
        return None
    try:
        img = cv2.resize(img_bgr, (224, 224), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hist_color = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256]).flatten()
        edges = cv2.Canny(gray, 80, 180)
        edge_hist = cv2.calcHist([gray], [0], edges, [16], [0, 256]).flatten()
        grid = cv2.resize(gray, (4, 4), interpolation=cv2.INTER_AREA).reshape(-1).astype(np.float32) / 255.0
        feat = np.concatenate([hist_color.astype(np.float32), edge_hist.astype(np.float32), grid.astype(np.float32)])
        return _normalize_vec(feat)
    except Exception:
        return None


def _build_simple_prompts(sample_bgr):
    prompts = []
    for variant in (
        sample_bgr,
        _center_crop(sample_bgr, 0.85),
        _center_crop(sample_bgr, 0.65),
    ):
        feat = _build_simple_feature(variant)
        if feat is not None:
            prompts.append(feat)
    return prompts


def _simple_similarity(prompt_feat, frame_feat) -> float:
    try:
        import numpy as np  # type: ignore
    except Exception:
        return 0.0
    if prompt_feat is None or frame_feat is None:
        return 0.0
    try:
        s = float(np.dot(prompt_feat, frame_feat))
        return max(0.0, min(1.0, s))
    except Exception:
        return 0.0
