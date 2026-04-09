from __future__ import annotations

from typing import List, Optional
import os
import subprocess

from process_utils import hidden_subprocess_kwargs
from .cache import _normalize_sample_texts
from .media import SIGLIP_BATCH_DEFAULT, _normalize_siglip_batch_size, _siglip_batch_levels_up_to, resolve_ffmpeg_bin
from .similarity import (
    REFILTER_FRAME_PROFILES,
    _frame_offsets_for_profile,
    _frame_sample_count_for_profile,
    _normalize_adapter_path,
    _normalize_pose_weights,
    _normalize_refilter_agg_mode,
    _normalize_refilter_mode,
    _normalize_refilter_sampling_mode,
    _normalize_siglip_decode_scale_w,
    _siglip2_default_model_id,
)

def init_scene_similarity_worker(worker, video_path: str, scene_ms: List[int], sample_image_paths: List[str], **options):
    _init_scene_similarity_core(
        worker,
        video_path,
        scene_ms,
        sample_image_paths,
        options.get("sample_texts"),
        options.get("mode", "siglip2"),
        options.get("pose_weights"),
    )
    _init_scene_similarity_siglip(worker, options)
    worker._cancel = False


def _init_scene_similarity_core(worker, video_path, scene_ms, sample_image_paths, sample_texts, mode, pose_weights):
    worker.video_path = video_path
    worker.scene_ms = [int(ms) for ms in (scene_ms or [])]
    worker.sample_image_paths = [os.path.abspath(p) for p in (sample_image_paths or []) if str(p or "").strip()]
    worker.sample_texts = _normalize_sample_texts(sample_texts or [])
    worker.mode = _normalize_refilter_mode(mode)
    worker.pose_weights = _normalize_pose_weights(pose_weights)


def _init_scene_similarity_siglip(worker, options):
    worker.siglip_model_id = str(options.get("siglip_model_id") or "").strip() or _siglip2_default_model_id()
    worker.siglip_adapter_path = _normalize_adapter_path(options.get("siglip_adapter_path"))
    worker.agg_mode = _normalize_refilter_agg_mode(options.get("agg_mode", "max"))
    worker.kofn_k = max(1, int(options.get("kofn_k") or 1))
    worker.frame_profile = _scene_similarity_frame_profile(options.get("frame_profile", "normal"))
    worker.sampling_mode = _normalize_refilter_sampling_mode(options.get("sampling_mode", "start_frame"))
    worker.frame_offsets = _frame_offsets_for_profile(worker.frame_profile)
    worker.frame_sample_count = _frame_sample_count_for_profile(worker.frame_profile)
    worker.hybrid_siglip_weight = max(0.0, min(1.0, float(options.get("hybrid_siglip_weight") or 0.55)))
    worker.normalize_scores = bool(options.get("normalize_scores", True))
    worker.siglip_batch_size = _normalize_siglip_batch_size(options.get("siglip_batch_size", SIGLIP_BATCH_DEFAULT))
    worker.siglip_decode_hwaccel = bool(options.get("siglip_decode_hwaccel", True))
    worker.siglip_two_stage = bool(options.get("siglip_two_stage"))
    worker.siglip_stage2_ratio = max(0.10, min(1.00, float(options.get("siglip_stage2_ratio") or 0.35)))
    worker.siglip_ffmpeg_bin = resolve_ffmpeg_bin(str(options.get("siglip_ffmpeg_bin") or "").strip())
    worker.siglip_ffmpeg_scale_w = _normalize_siglip_decode_scale_w(options.get("siglip_ffmpeg_scale_w", 0), default=0)
    worker.siglip_scene_feature_cache = bool(options.get("siglip_scene_feature_cache", True))
    _init_scene_similarity_batch_state(worker)


def _scene_similarity_frame_profile(frame_profile: str) -> str:
    profile = str(frame_profile or "").strip().lower()
    return profile if profile in REFILTER_FRAME_PROFILES else "normal"


def _init_scene_similarity_batch_state(worker):
    worker._siglip_batch_levels = _siglip_batch_levels_up_to(worker.siglip_batch_size)
    worker._siglip_batch_min = min(worker._siglip_batch_levels)
    worker._siglip_batch_max = max(worker._siglip_batch_levels)
    worker._siglip_batch_auto = int(worker._siglip_batch_max)
    worker._siglip_batch_probe_ts = 0.0
    worker._siglip_batch_msg_ts = 0.0


def probe_siglip_gpu_metrics(worker, siglip_bundle: Optional[dict]) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if not worker._siglip_is_cuda(siglip_bundle):
        return None, None, None
    cuda_idx = worker._siglip_cuda_index(siglip_bundle)
    free_gb, total_gb = _probe_siglip_cuda_memory(siglip_bundle, cuda_idx)
    util = _probe_siglip_nvidia_smi(cuda_idx)
    return util, free_gb, total_gb


def _probe_siglip_cuda_memory(siglip_bundle: Optional[dict], cuda_idx: int):
    free_gb = None
    total_gb = None
    torch = siglip_bundle.get("torch") if isinstance(siglip_bundle, dict) else None
    if torch is None:
        return free_gb, total_gb
    try:
        with torch.cuda.device(cuda_idx):
            free_b, total_b = torch.cuda.mem_get_info()
        free_gb = float(free_b) / (1024.0 ** 3)
        total_gb = float(total_b) / (1024.0 ** 3)
    except Exception:
        free_gb = None
        total_gb = None
    return free_gb, total_gb


def _probe_siglip_nvidia_smi(cuda_idx: int):
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=0.35,
            **hidden_subprocess_kwargs(),
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    try:
        lines = [ln.strip() for ln in str(proc.stdout or "").splitlines() if ln.strip()]
        if 0 <= cuda_idx < len(lines):
            return float(lines[cuda_idx])
        if lines:
            return float(lines[0])
    except Exception:
        return None
    return None

__all__ = [
    "init_scene_similarity_worker",
    "probe_siglip_gpu_metrics",
]
