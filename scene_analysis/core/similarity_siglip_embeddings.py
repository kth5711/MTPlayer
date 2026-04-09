from __future__ import annotations

from typing import Any, List, Optional

from .media import _normalize_siglip_batch_size
from .similarity_image_utils import _center_crop, _normalize_vec

_LAST_SIGLIP_IMAGE_ERROR = ""
_LAST_SIGLIP_TEXT_ERROR = ""


def _set_siglip_image_error(exc: Exception | str) -> None:
    global _LAST_SIGLIP_IMAGE_ERROR
    _LAST_SIGLIP_IMAGE_ERROR = str(exc or "").strip()


def _set_siglip_text_error(exc: Exception | str) -> None:
    global _LAST_SIGLIP_TEXT_ERROR
    _LAST_SIGLIP_TEXT_ERROR = str(exc or "").strip()


def _clear_siglip_embedding_errors() -> None:
    global _LAST_SIGLIP_IMAGE_ERROR, _LAST_SIGLIP_TEXT_ERROR
    _LAST_SIGLIP_IMAGE_ERROR = ""
    _LAST_SIGLIP_TEXT_ERROR = ""


def _last_siglip_image_error() -> str:
    return str(_LAST_SIGLIP_IMAGE_ERROR or "").strip()


def _last_siglip_text_error() -> str:
    return str(_LAST_SIGLIP_TEXT_ERROR or "").strip()


def _siglip2_feature(img_bgr, bundle):
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as exc:
        _set_siglip_image_error(exc)
        return None
    if img_bgr is None or bundle is None:
        return None
    try:
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        inputs, torch, _device = _siglip_processor_inputs(bundle, images=pil_img)
        if inputs is None or torch is None:
            return None
        feats = _siglip_run_image_features(bundle, inputs, torch)
        return _siglip_normalized_numpy_feature(np, feats)
    except Exception as exc:
        _set_siglip_image_error(exc)
        return None


def _siglip2_features_batch(img_bgr_list, bundle, batch_size: int = 64):
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore
    except Exception:
        return [None for _ in (img_bgr_list or [])]
    items = list(img_bgr_list or [])
    out: List[Optional[Any]] = [None for _ in items]
    if bundle is None or not items:
        return out
    try:
        valid_idx, valid_pil = _siglip_valid_pil_items(cv2, Image, items)
        if not valid_pil:
            return out
        processor = bundle.get("processor")
        model = bundle.get("model")
        torch = bundle.get("torch")
        device = bundle.get("device", "cpu")
        if processor is None or model is None or torch is None:
            return out
        bs = _normalize_siglip_batch_size(batch_size)
        for i in range(0, len(valid_pil), bs):
            inputs = processor(images=valid_pil[i:i + bs], return_tensors="pt")
            pixel_values = inputs.get("pixel_values") if hasattr(inputs, "get") else None
            feats = _siglip_run_image_features(bundle, pixel_values.to(device) if pixel_values is not None else None, torch)
            _siglip_batch_to_output(np, feats, valid_idx[i:i + bs], out)
        return out
    except Exception:
        return [None for _ in items]


def _siglip2_text_feature(text: str, bundle):
    try:
        import numpy as np  # type: ignore
    except Exception as exc:
        _set_siglip_text_error(exc)
        return None
    if bundle is None:
        return None
    txt = str(text or "").strip()
    if not txt:
        return None
    try:
        payload, torch, _device = _siglip_processor_inputs(bundle, text=[txt], padding=True, truncation=True)
        if not payload or torch is None:
            return None
        feats = _siglip_run_text_features(bundle, payload, torch)
        return _siglip_normalized_numpy_feature(np, feats)
    except Exception as exc:
        _set_siglip_text_error(exc)
        return None


def _build_siglip2_prompts(sample_bgr, bundle):
    prompts = []
    for variant in (sample_bgr, _center_crop(sample_bgr, 0.85), _center_crop(sample_bgr, 0.65)):
        feat = _siglip2_feature(variant, bundle)
        if feat is not None:
            prompts.append(feat)
    return prompts


def _siglip_valid_pil_items(cv2, Image, items):
    valid_idx: List[int] = []
    valid_pil = []
    for idx, img_bgr in enumerate(items):
        if img_bgr is None:
            continue
        try:
            valid_pil.append(Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)))
            valid_idx.append(int(idx))
        except Exception:
            continue
    return valid_idx, valid_pil


def _siglip_batch_to_output(np, feats, idx_chunk, out):
    if feats is None:
        return
    arr2d = feats.detach().float().cpu().numpy() if hasattr(feats, "detach") else np.asarray(feats, dtype=np.float32)
    if arr2d.ndim == 1:
        arr2d = arr2d.reshape(1, -1)
    for local_i, orig_idx in enumerate(idx_chunk):
        try:
            out[int(orig_idx)] = _normalize_vec(np.asarray(arr2d[local_i], dtype=np.float32).reshape(-1))
        except Exception:
            continue


def _siglip_processor_inputs(bundle, **kwargs):
    processor = bundle.get("processor")
    model = bundle.get("model")
    torch = bundle.get("torch")
    device = bundle.get("device", "cpu")
    if processor is None or model is None or torch is None:
        return None, None, None
    inputs = processor(return_tensors="pt", **kwargs)
    if "images" in kwargs:
        pixel_values = inputs.get("pixel_values") if hasattr(inputs, "get") else None
        return (pixel_values.to(device) if pixel_values is not None else None), torch, device
    payload = {}
    for key in ("input_ids", "attention_mask", "token_type_ids"):
        val = inputs.get(key) if hasattr(inputs, "get") else None
        if val is not None:
            payload[key] = val.to(device)
    return payload, torch, device


def _siglip_run_image_features(bundle, pixel_values, torch):
    if pixel_values is None:
        return None
    model = bundle.get("model")
    with torch.inference_mode():
        if hasattr(model, "get_image_features"):
            return model.get_image_features(pixel_values=pixel_values)
        out = model(pixel_values=pixel_values)
        feats = getattr(out, "image_embeds", None)
        return out[0] if (feats is None and isinstance(out, (tuple, list)) and len(out) > 0) else feats


def _siglip_run_text_features(bundle, payload, torch):
    if not payload:
        return None
    model = bundle.get("model")
    with torch.inference_mode():
        if hasattr(model, "get_text_features"):
            return model.get_text_features(**payload)
        out = model(**payload)
        feats = getattr(out, "text_embeds", None)
        return out[0] if (feats is None and isinstance(out, (tuple, list)) and len(out) > 0) else feats


def _siglip_normalized_numpy_feature(np, feats):
    if feats is None:
        return None
    arr = feats.detach().float().cpu().numpy().reshape(-1) if hasattr(feats, "detach") else np.asarray(feats, dtype=np.float32).reshape(-1)
    return _normalize_vec(arr)


__all__ = [
    "_siglip2_feature",
    "_siglip2_features_batch",
    "_siglip2_text_feature",
    "_build_siglip2_prompts",
    "_clear_siglip_embedding_errors",
    "_last_siglip_image_error",
    "_last_siglip_text_error",
]
