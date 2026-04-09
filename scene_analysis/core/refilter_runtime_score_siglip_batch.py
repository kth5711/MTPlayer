from __future__ import annotations

from .media import _torchcodec_batch_rgb_by_ms


def collect_siglip_batch_tensor(worker, state, t_list, siglip_bundle):
    feats_t = _torchcodec_siglip_tensor(worker, state, t_list, siglip_bundle)
    return feats_t, feats_t is not None


def _torchcodec_siglip_tensor(worker, state, t_list, siglip_bundle):
    tc_reader = state.get("tc_reader")
    if tc_reader is None or (not t_list):
        return None
    tc_times = [int(x) for x in t_list]
    decode_bs = max(1, min(len(tc_times), int(worker._effective_siglip_batch_size(siglip_bundle, len(tc_times)))))
    parts = []
    decoded_n = 0
    for k in range(0, len(tc_times), decode_bs):
        worker._raise_if_cancelled()
        tc_batch = _torchcodec_batch_or_singles(worker, tc_reader, tc_times[k:k + decode_bs], siglip_bundle)
        if tc_batch is None:
            continue
        part = worker._siglip_feats_from_rgb_auto(tc_batch, siglip_bundle, return_tensor=True, pre_resize_w=state["siglip_pre_resize_w"])
        if part is None:
            continue
        parts.append(part)
        decoded_n += _batch_len(tc_batch, tc_times[k:k + decode_bs])
    return _finish_siglip_tensor(parts, state, "torchcodec", decoded_n, "SigLIP2 TorchCodec 배치/단건 읽기 실패 감지", worker)


def _torchcodec_batch_or_singles(worker, tc_reader, tc_chunk_times, siglip_bundle):
    tc_batch, _tc_pts = _torchcodec_batch_rgb_by_ms(tc_reader, tc_chunk_times)
    if tc_batch is not None:
        return tc_batch
    torch_mod = siglip_bundle.get("torch") if isinstance(siglip_bundle, dict) else None
    rows = []
    for one_ms in tc_chunk_times:
        worker._raise_if_cancelled()
        one_batch, _one_pts = _torchcodec_batch_rgb_by_ms(tc_reader, [int(one_ms)])
        if _batch_has_rows(one_batch):
            rows.append(one_batch[0:1])
    if not rows or torch_mod is None:
        return None
    try:
        return rows[0] if len(rows) == 1 else torch_mod.cat(rows, dim=0)
    except Exception:
        return None


def _batch_len(batch_obj, fallback_list):
    try:
        return int(batch_obj.shape[0])
    except Exception:
        return len(fallback_list)


def _batch_has_rows(batch_obj):
    try:
        return batch_obj is not None and int(getattr(batch_obj, "shape", [0])[0]) >= 1
    except Exception:
        return False


def _finish_siglip_tensor(parts, state, key: str, decoded_n: int, fail_message: str, worker):
    if parts:
        if len(parts) == 1:
            feats_t = parts[0]
        else:
            torch_mod = parts[0].__class__.__module__.split(".")[0]
            try:
                torch = __import__(torch_mod)
                feats_t = torch.cat(parts, dim=0)
            except Exception:
                feats_t = parts[0]
        state["decode_stats"][key] = int(state["decode_stats"].get(key, 0)) + int(decoded_n)
        return feats_t
    if not bool(state.get("tc_runtime_warned")) and key == "torchcodec":
        worker.message.emit(fail_message)
        state["tc_runtime_warned"] = True
    return None


__all__ = ["collect_siglip_batch_tensor"]
