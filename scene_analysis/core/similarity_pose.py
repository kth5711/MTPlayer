from __future__ import annotations

from typing import Optional
import threading


POSE_COMP_KEYS = ("pose", "layout", "grid", "grad", "color")
POSE_COMP_PROFILES = {
    "action": {"pose": 0.65, "layout": 0.25, "grid": 0.06, "grad": 0.03, "color": 0.01},
    "balanced": {"pose": 0.50, "layout": 0.32, "grid": 0.10, "grad": 0.05, "color": 0.03},
    "composition": {"pose": 0.35, "layout": 0.45, "grid": 0.12, "grad": 0.05, "color": 0.03},
}
POSE_COMP_LABELS = {
    "pose": "Pose",
    "layout": "Layout",
    "grid": "Grid",
    "grad": "Grad",
    "color": "Color",
}

_HOG_PERSON_DETECTOR = None
_MP_POSE_SUPPORTED: Optional[bool] = None
_MP_POSE_TLS = threading.local()


def _normalize_pose_weights(weights: Optional[dict]) -> dict[str, float]:
    base = {k: float(POSE_COMP_PROFILES["balanced"].get(k, 0.0)) for k in POSE_COMP_KEYS}
    if isinstance(weights, dict):
        for k in POSE_COMP_KEYS:
            try:
                base[k] = max(0.0, float(weights.get(k, base[k])))
            except Exception:
                pass
    s = sum(base.values())
    if s <= 1e-12:
        return dict(POSE_COMP_PROFILES["balanced"])
    return {k: (base[k] / s) for k in POSE_COMP_KEYS}


def _pose_weight_signature(weights: Optional[dict]) -> str:
    w = _normalize_pose_weights(weights)
    return ",".join(f"{k}:{w[k]:.6f}" for k in POSE_COMP_KEYS)


def _get_hog_person_detector():
    global _HOG_PERSON_DETECTOR
    if _HOG_PERSON_DETECTOR is None:
        try:
            import cv2  # type: ignore

            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            _HOG_PERSON_DETECTOR = hog
        except Exception:
            _HOG_PERSON_DETECTOR = False
    return None if _HOG_PERSON_DETECTOR is False else _HOG_PERSON_DETECTOR


def _detect_person_boxes(img_bgr):
    try:
        import cv2  # type: ignore
    except Exception:
        return []
    if img_bgr is None:
        return []
    h, w = img_bgr.shape[:2]
    if h < 32 or w < 32:
        return []
    hog = _get_hog_person_detector()
    if hog is None:
        return []
    small, ratio = _scaled_person_detect_frame(cv2, img_bgr, w, h)
    try:
        rects, weights = hog.detectMultiScale(small, winStride=(8, 8), padding=(8, 8), scale=1.05)
    except Exception:
        return []
    out = []
    for idx, rect in enumerate(rects):
        box = _person_detect_box(rect, weights, idx, ratio, w, h)
        if box is not None:
            out.append(box)
    out.sort(key=lambda b: (((b[2] - b[0]) * (b[3] - b[1])), b[4]), reverse=True)
    return out[:3]


def _scaled_person_detect_frame(cv2, img_bgr, w: int, h: int):
    target_w = 320
    if w <= target_w:
        return img_bgr, 1.0
    ratio = float(w) / float(target_w)
    target_h = max(32, int(round(h / ratio)))
    return cv2.resize(img_bgr, (target_w, target_h), interpolation=cv2.INTER_AREA), ratio


def _person_detect_box(rect, weights, idx: int, ratio: float, frame_w: int, frame_h: int):
    x, y, bw, bh = [int(v) for v in rect]
    if bw < 18 or bh < 30:
        return None
    wt = float(weights[idx]) if weights is not None and len(weights) > idx else 0.0
    x0 = max(0, min(frame_w - 1, int(round(x * ratio))))
    y0 = max(0, min(frame_h - 1, int(round(y * ratio))))
    x1 = max(x0 + 1, min(frame_w, int(round((x + bw) * ratio))))
    y1 = max(y0 + 1, min(frame_h, int(round((y + bh) * ratio))))
    return (x0, y0, x1, y1, wt)


def _layout_feature_from_boxes(boxes, frame_w: int, frame_h: int, max_people: int = 2):
    try:
        import numpy as np  # type: ignore
    except Exception:
        return None
    if frame_w <= 0 or frame_h <= 0:
        return None
    values = _layout_feature_values(list(boxes or [])[:max_people], frame_w, frame_h, max_people)
    values.extend(_layout_spacing_values(list(boxes or []), frame_w, frame_h))
    return np.asarray(values, dtype=np.float32)


def _layout_feature_values(chosen, frame_w: int, frame_h: int, max_people: int):
    values: list[float] = []
    for (x0, y0, x1, y1, _wt) in chosen:
        bw = max(1, x1 - x0)
        bh = max(1, y1 - y0)
        cx = ((x0 + x1) * 0.5) / float(frame_w)
        cy = ((y0 + y1) * 0.5) / float(frame_h)
        values.extend([max(0.0, min(1.0, cx)), max(0.0, min(1.0, cy)), max(0.0, min(1.0, bw / float(frame_w))), max(0.0, min(1.0, bh / float(frame_h)))])
    for _ in range(max_people - len(chosen)):
        values.extend([0.0, 0.0, 0.0, 0.0])
    values.append(min(float(len(chosen)), float(max_people)) / float(max_people))
    return values


def _layout_spacing_values(boxes, frame_w: int, frame_h: int):
    if len(boxes) < 2:
        return [0.0, 0.0]
    b1, b2 = boxes[0], boxes[1]
    c1x = ((b1[0] + b1[2]) * 0.5) / float(frame_w)
    c1y = ((b1[1] + b1[3]) * 0.5) / float(frame_h)
    c2x = ((b2[0] + b2[2]) * 0.5) / float(frame_w)
    c2y = ((b2[1] + b2[3]) * 0.5) / float(frame_h)
    return [abs(c1x - c2x), abs(c1y - c2y)]


def _get_mediapipe_pose_estimator():
    global _MP_POSE_SUPPORTED
    if _MP_POSE_SUPPORTED is False:
        return None
    pose = getattr(_MP_POSE_TLS, "pose_estimator", None)
    if pose is not None:
        return pose
    try:
        import mediapipe as mp  # type: ignore

        pose = mp.solutions.pose.Pose(static_image_mode=True, model_complexity=1, enable_segmentation=False, min_detection_confidence=0.4)
        _MP_POSE_TLS.pose_estimator = pose
        _MP_POSE_SUPPORTED = True
        return pose
    except Exception:
        _MP_POSE_SUPPORTED = False
        return None


def _release_mediapipe_pose_estimator():
    pose = getattr(_MP_POSE_TLS, "pose_estimator", None)
    if pose is None:
        return
    try:
        close_fn = getattr(pose, "close", None)
        if callable(close_fn):
            close_fn()
    except Exception:
        pass
    try:
        delattr(_MP_POSE_TLS, "pose_estimator")
    except Exception:
        pass


def _extract_pose_feature(img_bgr):
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return None
    if img_bgr is None:
        return None
    pose = _get_mediapipe_pose_estimator()
    if pose is None:
        return None
    try:
        res = pose.process(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    except Exception:
        return None
    if not res or not res.pose_landmarks:
        return None
    arr, mask = _pose_landmark_arrays(np, res.pose_landmarks.landmark)
    if arr is None or mask is None or float(mask.sum()) < 4:
        return None
    center = _pose_feature_center(np, arr, mask)
    scale = _pose_feature_scale(np, arr, mask)
    norm_arr = (arr - center.reshape(1, 2)) / scale
    norm_arr[mask <= 0.5] = 0.0
    return norm_arr.reshape(-1), mask


def _pose_landmark_arrays(np, landmarks):
    landmark_indices = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
    pts = []
    vis = []
    for idx in landmark_indices:
        if idx >= len(landmarks):
            pts.append([0.0, 0.0])
            vis.append(0.0)
            continue
        lm = landmarks[idx]
        v = float(getattr(lm, "visibility", 1.0))
        if v < 0.35:
            pts.append([0.0, 0.0])
            vis.append(0.0)
            continue
        pts.append([float(lm.x), float(lm.y)])
        vis.append(1.0)
    return np.asarray(pts, dtype=np.float32), np.asarray(vis, dtype=np.float32)


def _pose_feature_center(np, arr, mask):
    shoulder_center = _mean_visible(np, arr, mask, [0, 1])
    hip_center = _mean_visible(np, arr, mask, [6, 7])
    if hip_center is not None:
        return hip_center
    if shoulder_center is not None:
        return shoulder_center
    return np.mean(arr[mask > 0.5], axis=0)


def _pose_feature_scale(np, arr, mask):
    shoulder_center = _mean_visible(np, arr, mask, [0, 1])
    hip_center = _mean_visible(np, arr, mask, [6, 7])
    if shoulder_center is not None and hip_center is not None:
        return max(float(np.linalg.norm(shoulder_center - hip_center)), 0.08)
    return 0.25


def _mean_visible(np, arr, mask, indices):
    vals = [arr[i] for i in indices if i < len(arr) and mask[i] > 0.5]
    if not vals:
        return None
    return np.mean(np.asarray(vals, dtype=np.float32), axis=0)


__all__ = [
    "POSE_COMP_KEYS",
    "POSE_COMP_PROFILES",
    "POSE_COMP_LABELS",
    "_normalize_pose_weights",
    "_pose_weight_signature",
    "_detect_person_boxes",
    "_layout_feature_from_boxes",
    "_get_mediapipe_pose_estimator",
    "_release_mediapipe_pose_estimator",
    "_extract_pose_feature",
]
