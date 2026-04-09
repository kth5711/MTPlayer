from __future__ import annotations

from typing import Any, Dict, List, Optional

from .similarity import _siglip2_scene_score_gpu


def _siglip_feature_rows_from_any(feats_obj: Any, bundle: Optional[dict]) -> Optional[Any]:
    try:
        import numpy as np  # type: ignore
    except Exception:
        return None
    if feats_obj is None:
        return None
    try:
        torch = bundle.get("torch") if isinstance(bundle, dict) else None
        if torch is not None and isinstance(feats_obj, torch.Tensor):
            arr = feats_obj.detach().float().cpu().numpy()
        else:
            arr = np.asarray(feats_obj, dtype=np.float32)
        if int(getattr(arr, "ndim", 0)) == 1:
            arr = arr.reshape(1, -1)
        if int(getattr(arr, "ndim", 0)) != 2 or int(arr.shape[0]) <= 0 or int(arr.shape[1]) <= 0:
            return None
        return np.asarray(arr, dtype=np.float32)
    except Exception:
        return None


def _siglip_feature_rows_from_list(feats_list: List[Any]) -> Optional[Any]:
    try:
        import numpy as np  # type: ignore
    except Exception:
        return None
    rows = []
    for feat in (feats_list or []):
        if feat is None:
            continue
        try:
            vec = np.asarray(feat, dtype=np.float32).reshape(-1)
        except Exception:
            continue
        if int(vec.size) > 0:
            rows.append(vec)
    if not rows:
        return None
    try:
        return np.stack(rows, axis=0)
    except Exception:
        return None


def _slice_siglip_feature_rows(rows: Any, positions: List[int]) -> Optional[Any]:
    try:
        import numpy as np  # type: ignore
    except Exception:
        return None
    if rows is None:
        return None
    try:
        arr = np.asarray(rows, dtype=np.float32)
        if int(getattr(arr, "ndim", 0)) == 1:
            arr = arr.reshape(1, -1)
        if int(getattr(arr, "ndim", 0)) != 2 or int(arr.shape[0]) <= 0:
            return None
        idx = [int(x) for x in (positions or []) if 0 <= int(x) < int(arr.shape[0])]
        if not idx:
            idx = [0]
        return np.asarray(arr[idx], dtype=np.float32)
    except Exception:
        return None


def _siglip_feature_row_count(rows: Any) -> int:
    try:
        import numpy as np  # type: ignore
    except Exception:
        return 0
    if rows is None:
        return 0
    try:
        arr = np.asarray(rows, dtype=np.float32)
        if int(getattr(arr, "ndim", 0)) == 1:
            arr = arr.reshape(1, -1)
        if int(getattr(arr, "ndim", 0)) != 2:
            return 0
        return max(0, int(arr.shape[0]))
    except Exception:
        return 0


def _siglip_score_from_feature_rows(
    rows: Any,
    prompt_group_tensors: Any,
    agg_mode: str,
    kofn_k: int,
    bundle: Optional[dict],
) -> float:
    score = _siglip2_scene_score_gpu(rows, prompt_group_tensors, agg_mode, kofn_k, bundle)
    try:
        return max(0.0, min(1.0, float(score)))
    except Exception:
        return 0.0


def _siglip_scene_feature_payload_to_maps(payload: dict) -> tuple[List[int], Dict[int, Any], Dict[int, Any]]:
    try:
        import numpy as np  # type: ignore
    except Exception:
        return [], {}, {}
    if not isinstance(payload, dict):
        return [], {}, {}
    try:
        scene_arr = np.asarray(payload.get("scene_ms"), dtype=np.int64).reshape(-1)
        coarse_counts = np.asarray(payload.get("coarse_counts"), dtype=np.int32).reshape(-1)
        full_counts = np.asarray(payload.get("full_counts"), dtype=np.int32).reshape(-1)
        coarse_feats = _siglip_scene_feature_matrix(payload.get("coarse_feats"))
        full_feats = _siglip_scene_feature_matrix(payload.get("full_feats"))
        coarse_map: Dict[int, Any] = {}
        full_map: Dict[int, Any] = {}
        scene_ms = [int(x) for x in scene_arr.tolist()]
        coarse_ofs = 0
        full_ofs = 0
        for idx, ms in enumerate(scene_ms):
            coarse_ofs = _siglip_scene_feature_slice(coarse_map, coarse_feats, coarse_counts, idx, ms, coarse_ofs)
            full_ofs = _siglip_scene_feature_slice(full_map, full_feats, full_counts, idx, ms, full_ofs)
        return scene_ms, coarse_map, full_map
    except Exception:
        return [], {}, {}


def _siglip_scene_feature_matrix(values):
    try:
        import numpy as np  # type: ignore
    except Exception:
        return None
    arr = np.asarray(values, dtype=np.float16)
    if arr.ndim == 1:
        return arr.reshape(0 if arr.size <= 0 else 1, -1)
    return arr


def _siglip_scene_feature_slice(target_map: Dict[int, Any], feats, counts, idx: int, ms: int, offset: int) -> int:
    count = int(counts[idx]) if idx < int(counts.size) else 0
    if count > 0:
        target_map[int(ms)] = feats[offset:offset + count]
    return offset + max(0, count)


def _siglip_scene_feature_maps_to_arrays(
    scene_ms_sorted: List[int],
    coarse_map: Dict[int, Any],
    full_map: Dict[int, Any],
) -> Optional[dict]:
    try:
        import numpy as np  # type: ignore
    except Exception:
        return None
    scene_norm = [int(x) for x in (scene_ms_sorted or []) if int(x) >= 0]
    coarse_counts: List[int] = []
    full_counts: List[int] = []
    coarse_rows: List[Any] = []
    full_rows: List[Any] = []
    feat_dim = 0
    for ms in scene_norm:
        feat_dim = _siglip_collect_feature_rows(ms, coarse_map, coarse_counts, coarse_rows, feat_dim)
        feat_dim = _siglip_collect_feature_rows(ms, full_map, full_counts, full_rows, feat_dim)
    return {
        "scene_ms": scene_norm,
        "coarse_counts": np.asarray(coarse_counts, dtype=np.int32),
        "coarse_feats": _siglip_concat_feature_rows(np, coarse_rows, feat_dim),
        "full_counts": np.asarray(full_counts, dtype=np.int32),
        "full_feats": _siglip_concat_feature_rows(np, full_rows, feat_dim),
    }


def _siglip_collect_feature_rows(ms: int, source_map: Dict[int, Any], counts: List[int], rows: List[Any], feat_dim: int) -> int:
    try:
        import numpy as np  # type: ignore
    except Exception:
        counts.append(0)
        return feat_dim
    raw_rows = source_map.get(int(ms))
    if raw_rows is None:
        counts.append(0)
        return feat_dim
    arr = np.asarray(raw_rows, dtype=np.float16)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.ndim != 2 or int(arr.shape[0]) <= 0 or int(arr.shape[1]) <= 0:
        counts.append(0)
        return feat_dim
    counts.append(int(arr.shape[0]))
    rows.append(arr)
    return max(feat_dim, int(arr.shape[1]))


def _siglip_concat_feature_rows(np, rows: List[Any], feat_dim: int):
    if rows:
        return np.concatenate(rows, axis=0).astype(np.float16, copy=False)
    return np.zeros((0, max(0, feat_dim)), dtype=np.float16)


__all__ = [
    "_siglip_feature_row_count",
    "_siglip_feature_rows_from_any",
    "_siglip_feature_rows_from_list",
    "_siglip_scene_feature_maps_to_arrays",
    "_siglip_scene_feature_payload_to_maps",
    "_siglip_score_from_feature_rows",
    "_slice_siglip_feature_rows",
]
