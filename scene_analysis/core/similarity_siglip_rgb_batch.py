from __future__ import annotations

from typing import Any, List, Optional

from .media import _normalize_siglip_batch_size
from .similarity_image_utils import _normalize_vec
from .similarity_siglip_bundle import _siglip2_image_params
from .similarity_siglip_embeddings import _siglip2_features_batch


def _siglip_rgb_tensor_context(frames_rgb, bundle, return_tensor: bool):
    try:
        import numpy as np  # type: ignore
    except Exception:
        return None if bool(return_tensor) else []
    if bundle is None:
        return None if bool(return_tensor) else []

    model = bundle.get("model")
    torch = bundle.get("torch")
    device = bundle.get("device", "cpu")
    if model is None or torch is None:
        return None if bool(return_tensor) else []

    try:
        if isinstance(frames_rgb, torch.Tensor):
            t = frames_rgb
        else:
            t = torch.as_tensor(frames_rgb)
    except Exception:
        return None if bool(return_tensor) else []

    if t is None or int(getattr(t, "ndim", 0)) != 4:
        return None if bool(return_tensor) else []
    n = int(t.shape[0]) if hasattr(t, "shape") else 0
    out: List[Optional[Any]] = [None for _ in range(max(0, n))]
    return {
        "np": np,
        "model": model,
        "torch": torch,
        "device": device,
        "tensor": t,
        "count": n,
        "output": out,
    }


def _prepare_siglip_rgb_chunk(t_chunk, pre_w: int, target_h: int, target_w: int, device):
    torch = device["torch"]
    target_device = device["name"]
    if t_chunk is None or int(getattr(t_chunk, "ndim", 0)) != 4:
        return None

    if int(t_chunk.shape[-1]) == 3:
        t_chunk = t_chunk.permute(0, 3, 1, 2).contiguous()
    elif int(t_chunk.shape[1]) == 3:
        t_chunk = t_chunk.contiguous()
    else:
        return None

    if t_chunk.dtype == torch.uint8:
        t_chunk = t_chunk.float().mul_(1.0 / 255.0)
    else:
        if t_chunk.dtype != torch.float32:
            t_chunk = t_chunk.float()
        try:
            if float(t_chunk.amax().item()) > 1.5:
                t_chunk = t_chunk / 255.0
        except Exception:
            t_chunk = t_chunk / 255.0

    t_chunk = _resize_siglip_rgb_chunk(t_chunk, pre_w, target_h, target_w)
    if t_chunk is None:
        return None
    if str(t_chunk.device) != str(target_device):
        t_chunk = t_chunk.to(target_device, non_blocking=True)
    return t_chunk


def _resize_siglip_rgb_chunk(t_chunk, pre_w: int, target_h: int, target_w: int):
    import torch.nn.functional as F  # type: ignore

    if pre_w > 0 and int(t_chunk.shape[-1]) > int(pre_w):
        pre_h = max(
            2,
            int(
                round(
                    float(int(t_chunk.shape[-2]))
                    * (float(int(pre_w)) / float(max(1, int(t_chunk.shape[-1]))))
                )
            ),
        )
        t_chunk = F.interpolate(
            t_chunk,
            size=(int(pre_h), int(pre_w)),
            mode="bilinear",
            align_corners=False,
        )

    if int(t_chunk.shape[-2]) != int(target_h) or int(t_chunk.shape[-1]) != int(target_w):
        t_chunk = F.interpolate(
            t_chunk,
            size=(int(target_h), int(target_w)),
            mode="bilinear",
            align_corners=False,
        )
    return t_chunk


def _run_siglip_rgb_chunk(model, t_chunk, mean, std, torch):
    mean_t = torch.tensor(mean, dtype=t_chunk.dtype, device=t_chunk.device).view(1, 3, 1, 1)
    std_t = torch.tensor(std, dtype=t_chunk.dtype, device=t_chunk.device).view(1, 3, 1, 1)
    pixel_values = (t_chunk - mean_t) / std_t

    with torch.inference_mode():
        if hasattr(model, "get_image_features"):
            return model.get_image_features(pixel_values=pixel_values)
        out_obj = model(pixel_values=pixel_values)
        feats = getattr(out_obj, "image_embeds", None)
        if feats is None and isinstance(out_obj, (tuple, list)) and len(out_obj) > 0:
            return out_obj[0]
        return feats


def _collect_siglip_rgb_chunk_features(
    feats,
    index: int,
    total_count: int,
    return_tensor: bool,
    out,
    feat_chunks,
    torch,
    np,
    device,
):
    if feats is None:
        return
    if bool(return_tensor):
        try:
            if hasattr(feats, "detach"):
                feats_t = feats.detach().float()
            else:
                feats_t = torch.as_tensor(feats, dtype=torch.float32, device=device)
            if int(getattr(feats_t, "ndim", 0)) == 1:
                feats_t = feats_t.unsqueeze(0)
            norms = feats_t.norm(dim=1, keepdim=True).clamp_min(1e-12)
            feat_chunks.append(feats_t / norms)
        except Exception:
            return
        return

    if hasattr(feats, "detach"):
        arr2d = feats.detach().float().cpu().numpy()
    else:
        arr2d = np.asarray(feats, dtype=np.float32)
    if arr2d.ndim == 1:
        arr2d = arr2d.reshape(1, -1)
    for offset in range(int(arr2d.shape[0])):
        out_index = int(index + offset)
        if 0 <= out_index < total_count:
            out[out_index] = _normalize_vec(np.asarray(arr2d[offset], dtype=np.float32).reshape(-1))


def _siglip_rgb_tensor_result(feat_chunks, out, return_tensor: bool, torch):
    if bool(return_tensor):
        if feat_chunks:
            try:
                return torch.cat(feat_chunks, dim=0)
            except Exception:
                return None
        return None
    return out


def _siglip_rgb_tensor_fallback(t, out, bundle, batch_size: int, return_tensor: bool):
    if bool(return_tensor):
        return None
    try:
        import numpy as np  # type: ignore
    except Exception:
        return out
    try:
        arr = t.detach().cpu().numpy()
    except Exception:
        return out
    frames_bgr = []
    try:
        import cv2  # type: ignore

        for x in arr:
            if x.ndim == 3 and x.shape[0] == 3:
                x = np.transpose(x, (1, 2, 0))
            if x is None or int(getattr(x, "ndim", 0)) != 3:
                frames_bgr.append(None)
                continue
            if x.dtype != np.uint8:
                xx = np.clip(x, 0.0, 1.0) * 255.0
                x = xx.astype(np.uint8)
            frames_bgr.append(cv2.cvtColor(x, cv2.COLOR_RGB2BGR))
    except Exception:
        return out
    return _siglip2_features_batch(frames_bgr, bundle, batch_size=batch_size)


def _siglip2_features_from_rgb_tensor_batch(
    frames_rgb,
    bundle,
    batch_size: int = 64,
    pre_resize_w: int = 0,
    return_tensor: bool = False,
):
    ctx = _siglip_rgb_tensor_context(frames_rgb, bundle, bool(return_tensor))
    if not isinstance(ctx, dict):
        return ctx
    if int(ctx["count"]) <= 0:
        return None if bool(return_tensor) else ctx["output"]
    try:
        target_h, target_w, mean, std = _siglip2_image_params(bundle)
        pre_w = max(0, int(pre_resize_w))
        bs = _normalize_siglip_batch_size(batch_size)
        feat_chunks = []
        device_ctx = {"torch": ctx["torch"], "name": ctx["device"]}
        for i in range(0, int(ctx["count"]), bs):
            t_chunk = _prepare_siglip_rgb_chunk(
                ctx["tensor"][i:i + bs],
                pre_w,
                int(target_h),
                int(target_w),
                device_ctx,
            )
            if t_chunk is None:
                continue
            feats = _run_siglip_rgb_chunk(ctx["model"], t_chunk, mean, std, ctx["torch"])
            _collect_siglip_rgb_chunk_features(
                feats,
                i,
                int(ctx["count"]),
                bool(return_tensor),
                ctx["output"],
                feat_chunks,
                ctx["torch"],
                ctx["np"],
                ctx["device"],
            )
        return _siglip_rgb_tensor_result(feat_chunks, ctx["output"], bool(return_tensor), ctx["torch"])
    except Exception:
        return _siglip_rgb_tensor_fallback(
            ctx["tensor"],
            ctx["output"],
            bundle,
            batch_size=batch_size,
            return_tensor=bool(return_tensor),
        )
