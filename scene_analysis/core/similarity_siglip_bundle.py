from __future__ import annotations

from typing import List
import os

from .similarity_siglip_config import _siglip2_default_model_id


_SIGLIP2_BUNDLE = None


def _siglip2_image_params(bundle) -> tuple[int, int, List[float], List[float]]:
    target_h = 224
    target_w = 224
    mean = [0.5, 0.5, 0.5]
    std = [0.5, 0.5, 0.5]
    try:
        processor = (bundle or {}).get("processor")
        img_proc = getattr(processor, "image_processor", None)
        if img_proc is None:
            return int(target_h), int(target_w), mean, std
        target_h, target_w = _siglip2_image_size(img_proc, target_h, target_w)
        mean = _siglip2_image_mean(img_proc, mean)
        std = _siglip2_image_std(img_proc, std)
    except Exception:
        pass
    return int(target_h), int(target_w), mean, std


def _siglip2_image_size(img_proc, target_h: int, target_w: int):
    size = getattr(img_proc, "size", None)
    if isinstance(size, dict):
        h = size.get("height")
        w = size.get("width")
        se = size.get("shortest_edge")
        if h is not None and w is not None:
            return max(8, int(h)), max(8, int(w))
        if se is not None:
            edge = max(8, int(se))
            return edge, edge
    elif isinstance(size, int):
        edge = max(8, int(size))
        return edge, edge
    return int(target_h), int(target_w)


def _siglip2_image_mean(img_proc, fallback):
    mean = getattr(img_proc, "image_mean", None)
    if isinstance(mean, (list, tuple)) and len(mean) >= 3:
        return [float(mean[0]), float(mean[1]), float(mean[2])]
    return list(fallback)


def _siglip2_image_std(img_proc, fallback):
    std = getattr(img_proc, "image_std", None)
    if isinstance(std, (list, tuple)) and len(std) >= 3:
        return [max(1e-6, float(std[0])), max(1e-6, float(std[1])), max(1e-6, float(std[2]))]
    return list(fallback)


def _normalize_adapter_path(adapter_path: str) -> str:
    p = str(adapter_path or "").strip()
    if not p:
        return ""
    return os.path.abspath(os.path.expanduser(p))


def _siglip2_default_adapter_path() -> str:
    return _normalize_adapter_path(str(os.environ.get("SIGLIP2_ADAPTER_PATH", "") or ""))


def _get_siglip2_bundle(model_id: str, adapter_path: str = ""):
    global _SIGLIP2_BUNDLE
    mid = str(model_id or "").strip() or _siglip2_default_model_id()
    adp = _normalize_adapter_path(adapter_path) or _siglip2_default_adapter_path()
    cached = _SIGLIP2_BUNDLE
    if _siglip2_cached_bundle_matches(cached, mid, adp):
        return cached
    torch, processor, model, device = _load_siglip2_components(mid, adp)
    _SIGLIP2_BUNDLE = {
        "model_id": mid,
        "adapter_path": adp,
        "device": device,
        "torch": torch,
        "processor": processor,
        "model": model,
    }
    return _SIGLIP2_BUNDLE


def _siglip2_cached_bundle_matches(cached, model_id: str, adapter_path: str) -> bool:
    return (
        isinstance(cached, dict)
        and cached.get("model_id") == model_id
        and str(cached.get("adapter_path") or "") == adapter_path
    )


def _load_siglip2_components(model_id: str, adapter_path: str):
    torch, AutoModel, AutoProcessor = _import_siglip2_runtime()
    device = "cuda" if bool(getattr(torch, "cuda", None)) and torch.cuda.is_available() else "cpu"
    try:
        processor = AutoProcessor.from_pretrained(model_id)
        model = AutoModel.from_pretrained(model_id)
        model = _attach_siglip2_adapter(model, adapter_path)
        model.eval()
        model.to(device)
    except Exception as exc:
        _raise_siglip2_load_error(model_id, adapter_path, exc)
    return torch, processor, model, device


def _import_siglip2_runtime():
    try:
        import torch  # type: ignore
        from transformers import AutoModel, AutoProcessor  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "SigLIP2 모드에는 torch/transformers/Pillow가 필요합니다. "
            "설치: pip install torch transformers Pillow"
        ) from exc
    return torch, AutoModel, AutoProcessor


def _attach_siglip2_adapter(model, adapter_path: str):
    if not adapter_path:
        return model
    try:
        from peft import PeftModel  # type: ignore
    except Exception as exc:
        raise RuntimeError("LoRA 어댑터를 사용하려면 peft가 필요합니다. 설치: pip install peft") from exc
    return PeftModel.from_pretrained(model, adapter_path)


def _raise_siglip2_load_error(model_id: str, adapter_path: str, exc: Exception):
    if adapter_path:
        raise RuntimeError(f"SigLIP2+어댑터 로딩 실패: model={model_id}, adapter={adapter_path} | {exc}")
    raise RuntimeError(f"SigLIP2 모델 로딩 실패: {model_id} | {exc}")


__all__ = [
    "_siglip2_image_params",
    "_normalize_adapter_path",
    "_siglip2_default_adapter_path",
    "_get_siglip2_bundle",
]
