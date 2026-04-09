from __future__ import annotations

from typing import Optional

from .similarity_image_utils import _center_crop, _normalize_vec
from .similarity_pose import _detect_person_boxes, _extract_pose_feature, _layout_feature_from_boxes, _normalize_pose_weights


def _build_pattern_profile(img_bgr):
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return None
    if img_bgr is None:
        return None
    try:
        img = cv2.resize(img_bgr, (256, 256), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hist_color = _pattern_color_hist(cv2, hsv)
        grad_hist = _pattern_grad_hist(cv2, np, gray)
        grid_vec = _pattern_grid_vec(cv2, np, gray)
        layout_vec, pose_vec, pose_mask = _pattern_pose_layout_vectors(img_bgr)
        return {"color": hist_color, "grad": grad_hist, "grid": grid_vec, "layout": layout_vec, "pose_vec": pose_vec, "pose_mask": pose_mask}
    except Exception:
        return None


def _pattern_color_hist(cv2, hsv):
    hist_color = cv2.calcHist([hsv], [0, 1, 2], None, [8, 6, 6], [0, 180, 0, 256, 0, 256]).flatten()
    return _normalize_vec(hist_color)


def _pattern_grad_hist(cv2, np, gray):
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag, ang = cv2.cartToPolar(gx, gy, angleInDegrees=False)
    bins = 12
    bin_idx = np.floor(((ang % (2 * np.pi)) / (2 * np.pi)) * bins).astype(np.int32)
    grad_hist = np.bincount(bin_idx.reshape(-1), weights=mag.reshape(-1), minlength=bins).astype(np.float32)
    return _normalize_vec(grad_hist)


def _pattern_grid_vec(cv2, np, gray):
    grid = 4
    gh, gw = gray.shape[:2]
    vals = []
    for gy_idx in range(grid):
        y0 = int((gh * gy_idx) / grid)
        y1 = int((gh * (gy_idx + 1)) / grid)
        for gx_idx in range(grid):
            x0 = int((gw * gx_idx) / grid)
            x1 = int((gw * (gx_idx + 1)) / grid)
            patch = gray[y0:y1, x0:x1]
            vals.append(0.0 if patch.size == 0 else float(np.mean(patch)) / 255.0)
    return _normalize_vec(np.array(vals, dtype=np.float32))


def _pattern_pose_layout_vectors(img_bgr):
    h0, w0 = img_bgr.shape[:2]
    boxes = _detect_person_boxes(img_bgr)
    layout_vec = _layout_feature_from_boxes(boxes, w0, h0, max_people=2)
    pose_feat = _extract_pose_feature(img_bgr)
    pose_vec = pose_feat[0] if pose_feat is not None else None
    pose_mask = pose_feat[1] if pose_feat is not None else None
    return layout_vec, pose_vec, pose_mask


def _build_pattern_prompts(sample_bgr):
    prompts = []
    for variant in (sample_bgr, _center_crop(sample_bgr, 0.85), _center_crop(sample_bgr, 0.65)):
        p = _build_pattern_profile(variant)
        if p is not None:
            prompts.append(p)
    return prompts


def _pattern_similarity(prompt_profile, frame_profile, weights: Optional[dict] = None) -> float:
    try:
        import numpy as np  # type: ignore
    except Exception:
        return 0.0
    if prompt_profile is None or frame_profile is None:
        return 0.0
    s_color = _pattern_cos(prompt_profile.get("color"), frame_profile.get("color"), np)
    s_grad = _pattern_cos(prompt_profile.get("grad"), frame_profile.get("grad"), np)
    s_grid = _pattern_cos(prompt_profile.get("grid"), frame_profile.get("grid"), np)
    s_layout = _pattern_layout_similarity(prompt_profile.get("layout"), frame_profile.get("layout"), np)
    s_pose = _pattern_pose_similarity(prompt_profile, frame_profile, np)
    if s_pose is None and prompt_profile.get("pose_vec") is not None and frame_profile.get("pose_vec") is None:
        s_pose = 0.0
    return _pattern_weighted_score(_normalize_pose_weights(weights), s_pose, s_layout, s_grid, s_grad, s_color)


def _pattern_cos(v1, v2, np):
    if v1 is None or v2 is None:
        return None
    return float(max(0.0, min(1.0, float(np.dot(v1, v2)))))


def _pattern_layout_similarity(layout1, layout2, np):
    if layout1 is None or layout2 is None:
        return None
    v1 = np.asarray(layout1, dtype=np.float32).reshape(-1)
    v2 = np.asarray(layout2, dtype=np.float32).reshape(-1)
    if v1.shape != v2.shape or v1.size <= 0:
        return None
    s_layout = max(0.0, min(1.0, 1.0 - float(np.mean(np.abs(v1 - v2)))))
    return _pattern_layout_penalty(v1, v2, s_layout)


def _pattern_layout_penalty(v1, v2, s_layout: float):
    person_count_idx = 8
    if v1.size <= person_count_idx or v2.size <= person_count_idx:
        return s_layout
    c1 = float(v1[person_count_idx])
    c2 = float(v2[person_count_idx])
    if c1 < 0.05 and c2 < 0.05:
        return None
    if c1 >= 0.20 and c2 < 0.05:
        return s_layout * 0.20
    if c1 < 0.05 and c2 >= 0.20:
        return s_layout * 0.35
    return s_layout


def _pattern_pose_similarity(prompt_profile, frame_profile, np):
    pose1 = prompt_profile.get("pose_vec")
    pose2 = frame_profile.get("pose_vec")
    mask1 = prompt_profile.get("pose_mask")
    mask2 = frame_profile.get("pose_mask")
    if pose1 is None or pose2 is None or mask1 is None or mask2 is None:
        return None
    p1 = np.asarray(pose1, dtype=np.float32).reshape(-1, 2)
    p2 = np.asarray(pose2, dtype=np.float32).reshape(-1, 2)
    m = (np.asarray(mask1, dtype=np.float32) > 0.5) & (np.asarray(mask2, dtype=np.float32) > 0.5)
    if p1.shape != p2.shape or p1.shape[0] != m.shape[0] or int(np.count_nonzero(m)) < 4:
        return None
    a = p1[m].reshape(-1)
    b = p2[m].reshape(-1)
    b_flip = p2[m].copy()
    b_flip[:, 0] *= -1.0
    candidates = [c for c in (_pattern_pose_cos(a, b, np), _pattern_pose_cos(a, b_flip.reshape(-1), np)) if c is not None]
    if not candidates:
        return None
    return max(0.0, min(1.0, (max(candidates) + 1.0) * 0.5))


def _pattern_pose_cos(x, y, np):
    nx = float(np.linalg.norm(x))
    ny = float(np.linalg.norm(y))
    if nx <= 1e-9 or ny <= 1e-9:
        return None
    return float(np.dot(x, y) / (nx * ny))


def _pattern_weighted_score(weights, s_pose, s_layout, s_grid, s_grad, s_color):
    weighted = [(s_pose, weights["pose"]), (s_layout, weights["layout"]), (s_grid, weights["grid"]), (s_grad, weights["grad"]), (s_color, weights["color"])]
    total = 0.0
    ws = 0.0
    for value, weight in weighted:
        if value is None:
            continue
        total += float(value) * float(weight)
        ws += float(weight)
    if ws <= 1e-12:
        return 0.0
    return max(0.0, min(1.0, total / ws))


__all__ = ["_build_pattern_profile", "_build_pattern_prompts", "_pattern_similarity"]
