from __future__ import annotations

from typing import Any, Callable, List, Optional
import re
import time

from PyQt6 import QtCore

from .refilter_config import (
    build_scene_similarity_cache_kwargs,
    build_scene_similarity_worker_kwargs,
    build_scene_similarity_worker_plan,
)
from .cache import siglip_scene_feature_cache_get, siglip_scene_feature_cache_set
from .refilter_feature_rows import (
    _siglip_feature_row_count,
    _siglip_feature_rows_from_any,
    _siglip_feature_rows_from_list,
    _siglip_scene_feature_maps_to_arrays,
    _siglip_scene_feature_payload_to_maps,
    _siglip_score_from_feature_rows,
    _slice_siglip_feature_rows,
)
from .refilter_parallel_runner import SceneSimilarityParallelRunner
from .refilter_run_setup import prepare_scene_similarity_run
from .refilter_runtime_score import score_with_times
from .refilter_runtime_setup import prepare_scene_similarity_runtime
from .refilter_scene_tasks import build_scene_similarity_tasks, derive_coarse_feature_rows
from .refilter_siglip_batch_auto import siglip_feats_from_bgr_auto, siglip_feats_from_rgb_auto
from .refilter_worker_init import init_scene_similarity_worker, probe_siglip_gpu_metrics
from .refilter_worker_run import run_scene_similarity_impl
from .similarity import (
    REFILTER_FRAME_PROFILES,
    SIGLIP_TORCHCODEC_MAX_SHORT_SIDE,
    _gpu_decode_chunk_batch_limits,
    _aggregate_sample_scores,
    _aggregate_temporal_scores,
    _build_pattern_profile,
    _build_simple_feature,
    _frame_offsets_for_profile,
    _frame_sample_count_for_profile,
    _normalize_refilter_agg_mode,
    _normalize_refilter_mode,
    _normalize_refilter_sampling_mode,
    _pattern_similarity,
    _release_mediapipe_pose_estimator,
    _robust_renorm_similarity_pairs,
    _siglip2_feature,
    _siglip2_scene_score_gpu,
    _simple_similarity,
)


class SceneSimilarityWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    message = QtCore.pyqtSignal(str)
    finished_ok = QtCore.pyqtSignal(list)
    finished_err = QtCore.pyqtSignal(str)

    def __init__(self, video_path: str, scene_ms: List[int], sample_image_paths: List[str], **options):
        super().__init__()
        init_scene_similarity_worker(self, video_path, scene_ms, sample_image_paths, **options)

    def cancel(self):
        self._cancel = True

    def _raise_if_cancelled(self):
        if bool(self._cancel):
            raise RuntimeError("사용자 취소")

    def _siglip_is_cuda(self, siglip_bundle: Optional[dict]) -> bool:
        if not isinstance(siglip_bundle, dict):
            return False
        device = str(siglip_bundle.get("device", "cpu") or "cpu").lower()
        return device.startswith("cuda")

    def _siglip_cuda_index(self, siglip_bundle: Optional[dict]) -> int:
        if not isinstance(siglip_bundle, dict):
            return 0
        device = str(siglip_bundle.get("device", "cuda:0") or "cuda:0")
        m = re.search(r"cuda:(\d+)", device.lower())
        if m:
            try:
                return max(0, int(m.group(1)))
            except Exception:
                return 0
        return 0

    def _probe_siglip_gpu_metrics(self, siglip_bundle: Optional[dict]) -> tuple[Optional[float], Optional[float], Optional[float]]:
        return probe_siglip_gpu_metrics(self, siglip_bundle)

    def _effective_siglip_batch_size(self, siglip_bundle: Optional[dict], sample_count: int) -> int:
        cur = max(self._siglip_batch_min, min(self._siglip_batch_max, int(self._siglip_batch_auto)))
        if not self._siglip_is_cuda(siglip_bundle):
            cur = min(cur, max(self._siglip_batch_min, 64))
            self._siglip_batch_auto = int(cur)
            return int(cur)

        now = time.time()
        if cur < int(self._siglip_batch_max) and (now - float(self._siglip_batch_probe_ts)) >= 5.0:
            self._siglip_batch_probe_ts = float(now)
            next_levels = [int(x) for x in self._siglip_batch_levels if int(x) > int(cur)]
            if next_levels:
                old = int(cur)
                cur = int(next_levels[0])
                self._siglip_batch_auto = int(cur)
                if (now - float(self._siglip_batch_msg_ts)) >= 1.8:
                    self.message.emit(f"SigLIP2 배치 복구 시도: {old}→{int(cur)}")
                    self._siglip_batch_msg_ts = float(now)
        return cur

    def _siglip_feats_from_rgb_auto(self, frames_rgb, siglip_bundle, return_tensor: bool = True, pre_resize_w: Optional[int] = None):
        return siglip_feats_from_rgb_auto(
            self, frames_rgb, siglip_bundle, return_tensor=return_tensor, pre_resize_w=pre_resize_w
        )

    def _siglip_feats_from_bgr_auto(self, frames_bgr: List[Any], siglip_bundle):
        return siglip_feats_from_bgr_auto(self, frames_bgr, siglip_bundle)

    def run(self):
        try:
            run_scene_similarity_worker(self)
        except Exception as e:
            self.finished_err.emit(str(e))
        finally:
            _release_mediapipe_pose_estimator()


def run_scene_similarity(
    video_path: str,
    scene_ms: List[int],
    sample_image_paths: List[str],
    *,
    progress_cb: Optional[Callable[[int], None]] = None,
    message_cb: Optional[Callable[[str], None]] = None,
    cancel_cb: Optional[Callable[[], bool]] = None,
    **worker_kwargs,
) -> List[tuple[int, float]]:
    return run_scene_similarity_impl(
        SceneSimilarityWorker,
        video_path,
        scene_ms,
        sample_image_paths,
        progress_cb=progress_cb,
        message_cb=message_cb,
        cancel_cb=cancel_cb,
        **worker_kwargs,
    )


def run_scene_similarity_worker(worker):
    setup_state = prepare_scene_similarity_run(worker)
    cached_out = try_scene_similarity_feature_cache(worker, setup_state)
    if cached_out:
        _finish_scene_similarity_output(worker, list(cached_out), None)
        return
    runtime_state = prepare_scene_similarity_runtime(worker, setup_state, setup_state["siglip_bundle"])
    try:
        out = _execute_scene_similarity_tasks(worker, setup_state, runtime_state)
    finally:
        _release_scene_similarity_runtime(runtime_state)
    _finish_scene_similarity_output(worker, out, runtime_state)


def _execute_scene_similarity_tasks(worker, setup_state, runtime_state):
    return execute_scene_similarity_tasks(
        worker,
        runtime_state,
        setup_state["scene_ms_sorted"],
        int(setup_state["total"]),
        int(runtime_state["video_len_ms"]),
        setup_state["sample_prompt_groups"],
        setup_state["siglip_bundle"],
        setup_state["siglip_prompt_group_tensors"],
        setup_state["np"],
        bool(setup_state["feature_cache_enabled"]),
        setup_state["coarse_feat_map"],
        setup_state["full_feat_map"],
        bool(setup_state["use_two_stage"]),
    )


def _release_scene_similarity_runtime(runtime_state):
    cap = runtime_state.get("cap")
    if cap is not None:
        try:
            cap.release()
        except Exception:
            pass
    runtime_state["cap"] = None
    runtime_state["tc_reader"] = None


def _finish_scene_similarity_output(worker, out, runtime_state):
    out.sort(key=lambda x: x[0])
    decode_stats = {} if runtime_state is None else dict(runtime_state.get("decode_stats") or {})
    if (
        int(decode_stats.get("torchcodec", 0)) > 0
        or int(decode_stats.get("opencv", 0)) > 0
    ):
        worker.message.emit(
            "SigLIP2 디코드 통계: "
            f"TorchCodec {int(decode_stats.get('torchcodec', 0))} / "
            f"OpenCV {int(decode_stats.get('opencv', 0))}"
        )
    if worker.normalize_scores and worker.mode != "siglip2":
        out = _robust_renorm_similarity_pairs(out)
    worker.progress.emit(100)
    worker.finished_ok.emit(out)


def try_scene_similarity_feature_cache(
    worker,
    state: dict[str, Any],
) -> Optional[list[tuple[int, float]]]:
    if not bool(state.get("feature_cache_enabled")):
        return None
    _load_scene_similarity_feature_cache(worker, state)
    if state.get("siglip_prompt_group_tensors") is None:
        return None
    return _scene_similarity_cached_scores(worker, state)


def _load_scene_similarity_feature_cache(worker, state):
    scene_ms_sorted = list(state.get("scene_ms_sorted") or [])
    total = max(0, int(state.get("total") or 0))
    feature_payload = siglip_scene_feature_cache_get(
        worker.video_path,
        scene_ms_sorted,
        siglip_model_id=worker.siglip_model_id,
        siglip_adapter_path=worker.siglip_adapter_path,
        frame_profile=worker.frame_profile,
        sampling_mode=worker.sampling_mode,
        siglip_ffmpeg_scale_w=worker.siglip_ffmpeg_scale_w,
    )
    cached_scene_ms, coarse_feat_map, full_feat_map = _siglip_scene_feature_payload_to_maps(feature_payload or {})
    if cached_scene_ms != scene_ms_sorted:
        coarse_feat_map = {}
        full_feat_map = {}
    elif coarse_feat_map or full_feat_map:
        worker.message.emit(
            f"SigLIP2 영상 임베딩 캐시 감지: coarse {len(coarse_feat_map)}/{total}, "
            f"full {len(full_feat_map)}/{total}"
        )
    state["coarse_feat_map"] = coarse_feat_map
    state["full_feat_map"] = full_feat_map


def _scene_similarity_cached_scores(worker, state):
    scene_ms_sorted = list(state.get("scene_ms_sorted") or [])
    total = max(0, int(state.get("total") or 0))
    use_two_stage = bool(state.get("use_two_stage"))
    coarse_feat_map = state.get("coarse_feat_map") or {}
    full_feat_map = state.get("full_feat_map") or {}
    tensors = state.get("siglip_prompt_group_tensors")
    siglip_bundle = state.get("siglip_bundle")
    full_missing = max(0, len(scene_ms_sorted) - sum(1 for ms in scene_ms_sorted if int(ms) in full_feat_map))
    if _scene_similarity_full_rows_ready(worker, scene_ms_sorted, coarse_feat_map, full_feat_map) and (not use_two_stage):
        if full_missing > 0:
            worker.message.emit(
                f"SigLIP2 영상 임베딩 캐시 사용… ({total}/{total}, full부족 {full_missing}개는 coarse 대체)"
            )
        else:
            worker.message.emit(f"SigLIP2 영상 임베딩 캐시 사용… ({total}/{total})")
        return _scene_similarity_full_cache_scores(
            worker,
            scene_ms_sorted,
            total,
            coarse_feat_map,
            full_feat_map,
            tensors,
            siglip_bundle,
        )
    if all(int(ms) in coarse_feat_map for ms in scene_ms_sorted) and use_two_stage:
        if full_missing > 0:
            worker.message.emit(
                f"SigLIP2 영상 임베딩 캐시로 1차 재평가… ({len(coarse_feat_map)}/{total}, full부족 {full_missing})"
            )
        else:
            worker.message.emit(f"SigLIP2 영상 임베딩 캐시로 1차 재평가… ({len(coarse_feat_map)}/{total})")
        return _scene_similarity_two_stage_cache_scores(
            worker, scene_ms_sorted, total, coarse_feat_map, full_feat_map, tensors, siglip_bundle
        )
    return None


def _scene_similarity_full_cache_scores(worker, scene_ms_sorted, total, coarse_feat_map, full_feat_map, tensors, siglip_bundle):
    out = []
    for i, ms in enumerate(scene_ms_sorted):
        worker._raise_if_cancelled()
        feature_rows = _scene_similarity_cached_full_rows(worker, int(ms), coarse_feat_map, full_feat_map)
        if feature_rows is None:
            return None
        out.append((int(ms), _scene_similarity_cached_score(worker, feature_rows, tensors, siglip_bundle)))
        worker.progress.emit(int(round(((i + 1) * 98.0) / max(1, total))))
    return out


def _scene_similarity_two_stage_cache_scores(
    worker,
    scene_ms_sorted,
    total,
    coarse_feat_map,
    full_feat_map,
    tensors,
    siglip_bundle,
):
    coarse_rows = _scene_similarity_cached_coarse_rows(
        worker,
        scene_ms_sorted,
        total,
        coarse_feat_map,
        tensors,
        siglip_bundle,
    )
    cand_idx = _scene_similarity_cached_candidate_indices(worker, total, coarse_rows)
    if not _scene_similarity_cached_candidate_rows_ready(worker, scene_ms_sorted, cand_idx, coarse_feat_map, full_feat_map):
        return None
    return _scene_similarity_cached_reranked_scores(
        worker,
        scene_ms_sorted,
        total,
        coarse_rows,
        cand_idx,
        coarse_feat_map,
        full_feat_map,
        tensors,
        siglip_bundle,
    )


def _scene_similarity_cached_coarse_rows(worker, scene_ms_sorted, total, coarse_feat_map, tensors, siglip_bundle):
    coarse_rows = []
    for i, ms in enumerate(scene_ms_sorted):
        worker._raise_if_cancelled()
        coarse_rows.append((i, int(ms), _scene_similarity_cached_score(worker, coarse_feat_map[int(ms)], tensors, siglip_bundle)))
        worker.progress.emit(int(round(((i + 1) * 42.0) / max(1, total))))
    return coarse_rows


def _scene_similarity_cached_candidate_indices(worker, total, coarse_rows):
    cand_n = max(1, min(total, int(round(float(total) * worker.siglip_stage2_ratio))))
    top_rows = sorted(coarse_rows, key=lambda x: x[2], reverse=True)[:cand_n]
    return sorted(int(r[0]) for r in top_rows)


def _scene_similarity_full_rows_equivalent(worker):
    return str(getattr(worker, "sampling_mode", "") or "").strip().lower() != "scene_window"


def _scene_similarity_cached_full_rows(worker, scene_start_ms, coarse_feat_map, full_feat_map):
    rows = full_feat_map.get(int(scene_start_ms))
    if rows is not None:
        return rows
    if _scene_similarity_full_rows_equivalent(worker):
        return coarse_feat_map.get(int(scene_start_ms))
    return None


def _scene_similarity_full_rows_ready(worker, scene_ms_sorted, coarse_feat_map, full_feat_map):
    return all(
        _scene_similarity_cached_full_rows(worker, int(ms), coarse_feat_map, full_feat_map) is not None
        for ms in scene_ms_sorted
    )


def _scene_similarity_cached_candidate_rows_ready(worker, scene_ms_sorted, cand_idx, coarse_feat_map, full_feat_map):
    return all(
        _scene_similarity_cached_full_rows(worker, int(scene_ms_sorted[idx]), coarse_feat_map, full_feat_map) is not None
        for idx in cand_idx
    )


def _scene_similarity_cached_reranked_scores(
    worker,
    scene_ms_sorted,
    total,
    coarse_rows,
    cand_idx,
    coarse_feat_map,
    full_feat_map,
    tensors,
    siglip_bundle,
):
    worker.message.emit(f"SigLIP2 영상 임베딩 캐시로 2차 재평가… ({len(cand_idx)}/{total})")
    score_map: dict[int, float] = {int(ms): float(s) for _, ms, s in coarse_rows}
    for j, idx in enumerate(cand_idx):
        worker._raise_if_cancelled()
        ms = int(scene_ms_sorted[idx])
        feature_rows = _scene_similarity_cached_full_rows(worker, ms, coarse_feat_map, full_feat_map)
        if feature_rows is None:
            return None
        score_map[ms] = _scene_similarity_cached_score(worker, feature_rows, tensors, siglip_bundle)
        worker.progress.emit(42 + int(round(((j + 1) * 56.0) / max(1, len(cand_idx)))))
    return sorted([(int(ms), float(sim)) for ms, sim in score_map.items()], key=lambda x: x[0])


def _scene_similarity_cached_score(worker, feature_rows, tensors, siglip_bundle):
    return _siglip_score_from_feature_rows(
        feature_rows,
        tensors,
        worker.agg_mode,
        worker.kofn_k,
        siglip_bundle,
    )


def execute_scene_similarity_tasks(worker, runtime_state, scene_ms_sorted, total, video_len_ms, sample_prompt_groups, siglip_bundle, siglip_prompt_group_tensors, np_mod, feature_cache_enabled, coarse_feat_map, full_feat_map, use_two_stage):
    scene_tasks = build_scene_similarity_tasks(worker, scene_ms_sorted, total, video_len_ms)
    feature_cache_dirty = _derive_coarse_feature_cache(scene_tasks, feature_cache_enabled, coarse_feat_map, full_feat_map)
    if use_two_stage:
        out, feature_cache_dirty = _run_scene_similarity_two_stage(
            worker, runtime_state, scene_tasks, total, sample_prompt_groups, siglip_bundle,
            siglip_prompt_group_tensors, np_mod, feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty
        )
    else:
        out, feature_cache_dirty = _run_scene_similarity_single_stage(
            worker, runtime_state, scene_tasks, total, sample_prompt_groups, siglip_bundle,
            siglip_prompt_group_tensors, np_mod, feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty
        )
    _persist_scene_similarity_feature_cache(
        worker, scene_ms_sorted, feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty
    )
    return out


def _derive_coarse_feature_cache(scene_tasks, feature_cache_enabled, coarse_feat_map, full_feat_map):
    if feature_cache_enabled and derive_coarse_feature_rows(scene_tasks, coarse_feat_map, full_feat_map):
        return True
    return False


def _run_scene_similarity_single_stage(worker, runtime_state, scene_tasks, total, sample_prompt_groups, siglip_bundle, tensors, np_mod, feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty):
    out = []
    for i, task in enumerate(scene_tasks):
        worker._raise_if_cancelled()
        scene_start_ms = int(task.get("scene_start_ms", 0))
        best_sim, feature_cache_dirty = _single_scene_similarity_score(
            worker, runtime_state, task, sample_prompt_groups, siglip_bundle, tensors, np_mod,
            feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty
        )
        out.append((scene_start_ms, float(best_sim)))
        worker.progress.emit(int(round(((i + 1) * 98.0) / max(1, total))))
    return out, feature_cache_dirty


def _single_scene_similarity_score(worker, runtime_state, task, sample_prompt_groups, siglip_bundle, tensors, np_mod, feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty):
    scene_start_ms = int(task.get("scene_start_ms", 0))
    full_rows_cached = _cached_full_like_rows(worker, scene_start_ms, coarse_feat_map, full_feat_map)
    if full_rows_cached is not None:
        return _siglip_feature_rows_score(worker, full_rows_cached, tensors, siglip_bundle), feature_cache_dirty
    best_sim, full_rows_new = _score_scene_similarity_times(
        worker, runtime_state, task.get("t_full") or [], sample_prompt_groups, siglip_bundle, tensors, np_mod
    )
    return float(best_sim), _update_single_stage_feature_cache(
        task, scene_start_ms, full_rows_new, feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty
    )


def _run_scene_similarity_two_stage(worker, runtime_state, scene_tasks, total, sample_prompt_groups, siglip_bundle, tensors, np_mod, feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty):
    coarse_rows, feature_cache_dirty = _coarse_scene_similarity_rows(
        worker, runtime_state, scene_tasks, total, sample_prompt_groups, siglip_bundle, tensors,
        np_mod, feature_cache_enabled, coarse_feat_map, feature_cache_dirty
    )
    cand_idx = _scene_similarity_candidate_indices(worker, total, coarse_rows)
    worker.message.emit(f"SigLIP2 2차 정밀 재평가… ({len(cand_idx)}/{total})")
    score_map, feature_cache_dirty = _rerank_scene_similarity_candidates(
        worker, runtime_state, scene_tasks, cand_idx, coarse_rows, sample_prompt_groups, siglip_bundle,
        tensors, np_mod, feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty
    )
    out = sorted([(int(ms), float(sim)) for ms, sim in score_map.items()], key=lambda x: x[0])
    return out, feature_cache_dirty


def _coarse_scene_similarity_rows(worker, runtime_state, scene_tasks, total, sample_prompt_groups, siglip_bundle, tensors, np_mod, feature_cache_enabled, coarse_feat_map, feature_cache_dirty):
    coarse_rows = []
    for i, task in enumerate(scene_tasks):
        worker._raise_if_cancelled()
        scene_start_ms = int(task.get("scene_start_ms", 0))
        coarse_sim, feature_cache_dirty = _coarse_scene_similarity_score(
            worker, runtime_state, task, sample_prompt_groups, siglip_bundle, tensors, np_mod,
            feature_cache_enabled, coarse_feat_map, feature_cache_dirty
        )
        coarse_rows.append((i, scene_start_ms, float(coarse_sim)))
        worker.progress.emit(int(round(((i + 1) * 42.0) / max(1, total))))
    return coarse_rows, feature_cache_dirty


def _coarse_scene_similarity_score(worker, runtime_state, task, sample_prompt_groups, siglip_bundle, tensors, np_mod, feature_cache_enabled, coarse_feat_map, feature_cache_dirty):
    scene_start_ms = int(task.get("scene_start_ms", 0))
    coarse_rows_cached = coarse_feat_map.get(scene_start_ms)
    if coarse_rows_cached is not None:
        return _siglip_feature_rows_score(worker, coarse_rows_cached, tensors, siglip_bundle), feature_cache_dirty
    coarse_sim, coarse_rows_new = _score_scene_similarity_times(
        worker, runtime_state, task.get("t_coarse") or [], sample_prompt_groups, siglip_bundle, tensors, np_mod
    )
    if feature_cache_enabled and coarse_rows_new is not None:
        coarse_feat_map[scene_start_ms] = coarse_rows_new
        feature_cache_dirty = True
    return float(coarse_sim), feature_cache_dirty


def _scene_similarity_candidate_indices(worker, total, coarse_rows):
    cand_n = max(1, min(total, int(round(float(total) * worker.siglip_stage2_ratio))))
    top_rows = sorted(coarse_rows, key=lambda x: x[2], reverse=True)[:cand_n]
    return sorted(int(r[0]) for r in top_rows)


def _rerank_scene_similarity_candidates(worker, runtime_state, scene_tasks, cand_idx, coarse_rows, sample_prompt_groups, siglip_bundle, tensors, np_mod, feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty):
    score_map: dict[int, float] = {int(ms): float(s) for _, ms, s in coarse_rows}
    for j, idx in enumerate(cand_idx):
        worker._raise_if_cancelled()
        scene_start_ms = int(scene_tasks[idx].get("scene_start_ms", 0))
        score_map[scene_start_ms], feature_cache_dirty = _reranked_scene_similarity_score(
            worker, runtime_state, scene_tasks[idx], sample_prompt_groups, siglip_bundle, tensors, np_mod,
            feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty
        )
        worker.progress.emit(42 + int(round(((j + 1) * 56.0) / max(1, len(cand_idx)))))
    return score_map, feature_cache_dirty


def _reranked_scene_similarity_score(worker, runtime_state, task, sample_prompt_groups, siglip_bundle, tensors, np_mod, feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty):
    scene_start_ms = int(task.get("scene_start_ms", 0))
    full_rows_cached = _cached_full_like_rows(worker, scene_start_ms, coarse_feat_map, full_feat_map)
    if full_rows_cached is not None:
        return _siglip_feature_rows_score(worker, full_rows_cached, tensors, siglip_bundle), feature_cache_dirty
    full_sim, full_rows_new = _score_scene_similarity_times(
        worker, runtime_state, task.get("t_full") or [], sample_prompt_groups, siglip_bundle, tensors, np_mod
    )
    feature_cache_dirty = _update_rerank_feature_cache(
        task, scene_start_ms, full_rows_new, feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty
    )
    return float(full_sim), feature_cache_dirty


def _score_scene_similarity_times(worker, runtime_state, t_list, sample_prompt_groups, siglip_bundle, tensors, np_mod):
    return score_with_times(
        worker, runtime_state, t_list, sample_prompt_groups, siglip_bundle, tensors, np_mod,
        return_siglip_rows=(worker.mode == "siglip2")
    )


def _update_single_stage_feature_cache(task, scene_start_ms, full_rows_new, feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty):
    if feature_cache_enabled and full_rows_new is not None:
        full_feat_map[scene_start_ms] = full_rows_new
        derived = _slice_siglip_feature_rows(full_rows_new, task.get("coarse_pos") or [])
        if derived is not None:
            coarse_feat_map[scene_start_ms] = derived
        return True
    return feature_cache_dirty


def _update_rerank_feature_cache(task, scene_start_ms, full_rows_new, feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty):
    if feature_cache_enabled and full_rows_new is not None:
        full_feat_map[scene_start_ms] = full_rows_new
        if scene_start_ms not in coarse_feat_map:
            derived = _slice_siglip_feature_rows(full_rows_new, task.get("coarse_pos") or [])
            if derived is not None:
                coarse_feat_map[scene_start_ms] = derived
        return True
    return feature_cache_dirty


def _cached_full_like_rows(worker, scene_start_ms, coarse_feat_map, full_feat_map):
    full_rows = full_feat_map.get(scene_start_ms)
    if full_rows is not None:
        return full_rows
    return coarse_feat_map.get(scene_start_ms)


def _persist_scene_similarity_feature_cache(worker, scene_ms_sorted, feature_cache_enabled, coarse_feat_map, full_feat_map, feature_cache_dirty):
    if not (feature_cache_enabled and bool(feature_cache_dirty)):
        return
    packed = _siglip_scene_feature_maps_to_arrays(scene_ms_sorted, coarse_feat_map, full_feat_map)
    if packed is None:
        return
    packed_scene_ms = packed.get("scene_ms")
    siglip_scene_feature_cache_set(
        worker.video_path,
        scene_ms_sorted if packed_scene_ms is None else packed_scene_ms,
        coarse_counts=packed.get("coarse_counts"),
        coarse_feats=packed.get("coarse_feats"),
        full_counts=packed.get("full_counts"),
        full_feats=packed.get("full_feats"),
        siglip_model_id=worker.siglip_model_id,
        siglip_adapter_path=worker.siglip_adapter_path,
        frame_profile=worker.frame_profile,
        sampling_mode=worker.sampling_mode,
        siglip_ffmpeg_scale_w=worker.siglip_ffmpeg_scale_w,
        siglip_two_stage=worker.siglip_two_stage,
    )


def _siglip_feature_rows_score(worker, feature_rows, tensors, siglip_bundle):
    return _siglip_score_from_feature_rows(feature_rows, tensors, worker.agg_mode, worker.kofn_k, siglip_bundle)
