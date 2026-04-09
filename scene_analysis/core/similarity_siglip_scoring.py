from __future__ import annotations


def _siglip_prompt_groups_to_tensors(sample_prompt_groups, bundle):
    if not isinstance(sample_prompt_groups, list) or bundle is None:
        return None
    torch = bundle.get("torch")
    device = bundle.get("device", "cpu")
    if torch is None:
        return None
    return [_siglip_prompt_tensor_rows(torch, device, grp) for grp in sample_prompt_groups]


def _siglip_prompt_tensor_rows(torch, device, grp):
    prompts = list(grp.get("siglip") or []) if isinstance(grp, dict) else []
    rows = [_siglip_prompt_tensor(torch, device, feat) for feat in prompts if feat is not None]
    rows = [row for row in rows if row is not None]
    if not rows:
        return None
    try:
        return torch.stack(rows, dim=0)
    except Exception:
        return None


def _siglip_prompt_tensor(torch, device, feat):
    try:
        if isinstance(feat, torch.Tensor):
            t = feat.detach().to(device=device, dtype=torch.float32).reshape(-1)
        else:
            t = torch.as_tensor(feat, dtype=torch.float32, device=device).reshape(-1)
        if int(getattr(t, "numel", lambda: 0)()) <= 0:
            return None
        return t / t.norm(p=2).clamp_min(1e-12)
    except Exception:
        return None


def _siglip2_scene_score_gpu(frame_feats_t, prompt_group_tensors, agg_mode: str, kofn_k: int, bundle):
    if frame_feats_t is None or prompt_group_tensors is None or bundle is None:
        return None
    torch = bundle.get("torch")
    device = bundle.get("device", "cpu")
    if torch is None:
        return None
    try:
        feats = _siglip_scene_frame_tensor(torch, device, frame_feats_t)
        if feats is None:
            return 0.0
        sample_scores = [_siglip_group_score(torch, feats, p) for p in (prompt_group_tensors or [])]
        vals = sorted((max(0.0, min(1.0, float(v))) for v in sample_scores), reverse=True)
        return _siglip_aggregate_group_scores(vals, agg_mode, kofn_k)
    except Exception:
        return None


def _siglip_scene_frame_tensor(torch, device, frame_feats_t):
    feats = frame_feats_t if isinstance(frame_feats_t, torch.Tensor) else torch.as_tensor(frame_feats_t, dtype=torch.float32, device=device)
    if int(getattr(feats, "ndim", 0)) == 1:
        feats = feats.unsqueeze(0)
    if int(getattr(feats, "ndim", 0)) != 2 or int(feats.shape[0]) <= 0:
        return None
    if str(feats.device) != str(device):
        feats = feats.to(device, non_blocking=True)
    feats = feats.float()
    return feats / feats.norm(dim=1, keepdim=True).clamp_min(1e-12)


def _siglip_group_score(torch, feats, prompt_tensor):
    if prompt_tensor is None:
        return 0.0
    pp = prompt_tensor if str(prompt_tensor.device) == str(feats.device) else prompt_tensor.to(feats.device, non_blocking=True)
    sims = torch.matmul(feats, pp.t())
    frame_best = torch.clamp(torch.max(sims, dim=1).values, min=0.0, max=1.0)
    if int(frame_best.numel()) <= 0:
        return 0.0
    n_frames = int(feats.shape[0])
    temporal_k = 3 if n_frames >= 7 else (2 if n_frames >= 3 else 1)
    k = max(1, min(int(temporal_k), int(frame_best.numel())))
    return float(torch.topk(frame_best, k=k, largest=True).values.mean().item())


def _siglip_aggregate_group_scores(vals, agg_mode: str, kofn_k: int) -> float:
    if not vals:
        return 0.0
    if str(agg_mode or "").strip().lower() == "kofn":
        k = max(1, min(int(kofn_k), len(vals)))
        return max(0.0, min(1.0, float(sum(vals[:k]) / float(max(1, k)))))
    return max(0.0, min(1.0, float(vals[0])))


__all__ = ["_siglip_prompt_groups_to_tensors", "_siglip2_scene_score_gpu"]
