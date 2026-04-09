from __future__ import annotations

from typing import List

from .similarity import _aggregate_sample_scores, _aggregate_temporal_scores
from .refilter_runtime_score_non_siglip import score_non_siglip_times
from .refilter_runtime_score_siglip import score_siglip_times


def score_with_times(
    worker,
    state,
    t_list: List[int],
    sample_prompt_groups,
    siglip_bundle,
    siglip_prompt_group_tensors,
    np_mod,
    return_siglip_rows: bool = False,
):
    worker._raise_if_cancelled()
    if worker.mode == "siglip2":
        score_val, scene_siglip_rows = score_siglip_times(
            worker,
            state,
            t_list,
            sample_prompt_groups,
            siglip_bundle,
            siglip_prompt_group_tensors,
            np_mod,
            return_siglip_rows,
        )
        return (score_val, scene_siglip_rows) if bool(return_siglip_rows) else score_val
    sample_time_scores = score_non_siglip_times(worker, state, t_list, sample_prompt_groups, siglip_bundle)
    sample_scores = [_aggregate_temporal_scores(scores) for scores in sample_time_scores]
    return float(_aggregate_sample_scores(sample_scores, worker.agg_mode, worker.kofn_k))


__all__ = ["score_with_times"]
