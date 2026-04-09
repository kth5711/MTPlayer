from typing import Dict

from scene_analysis.core.cache import scene_cache_set, store_to_disk
from scene_analysis.core.detect import run_scene_detect
from scene_analysis.core.similarity import _gpu_decode_chunk_batch_limits

from .batch_sources import _load_scene_cache_payload, _scene_filtered_points


def _scene_stage_end(config: Dict[str, object]) -> int:
    return 50 if bool(config.get("run_refilter", False)) else 100


def _load_scene_batch_cache(path: str, config: Dict[str, object], state: Dict[str, object]) -> None:
    if not bool(config.get("use_cache", True)):
        return
    cache_label, scene_pts, scene_top = _load_scene_cache_payload(path, config)
    state["scene_cache_label"] = cache_label
    state["scene_pts"] = scene_pts
    state["scene_top"] = scene_top


def _emit_scene_batch_cache_hit(worker, idx: int, total: int, base: str, config: Dict[str, object], state: Dict[str, object]) -> None:
    worker.current_progress.emit(_scene_stage_end(config))
    worker.message.emit(
        f"[{idx + 1}/{total}] {base} 씬변화 캐시 사용({state['scene_cache_label']})"
    )


def _scene_detect_chunk_size(path: str, config: Dict[str, object]) -> int:
    chunk_size = int(config.get("decode_chunk_size", 64))
    if bool(config.get("ff_hwaccel", False)):
        chunk_size, _scan_batch, _tier, _vw, _vh = _gpu_decode_chunk_batch_limits(path)
    return int(chunk_size)


def _scene_message(worker, idx: int, total: int, base: str, text: str) -> None:
    worker.message.emit(f"[{idx + 1}/{total}] {base} | {text}")


def _run_scene_batch_detect(
    worker,
    path: str,
    idx: int,
    total: int,
    base: str,
    config: Dict[str, object],
    state: Dict[str, object],
) -> None:
    state["item_cache_only"] = False
    scene_pts, scene_top = run_scene_detect(
        path,
        bool(config.get("use_ff", True)),
        float(config.get("thr", 0.35)),
        int(config.get("dw", 320)),
        int(config.get("fps", 5)),
        str(config.get("ffbin") or ""),
        worker.dialog.host,
        ff_hwaccel=bool(config.get("ff_hwaccel", False)),
        decode_chunk_size=_scene_detect_chunk_size(path, config),
        progress_cb=lambda p: worker.current_progress.emit(
            worker._map_stage_progress(0, _scene_stage_end(config), int(p))
        ),
        message_cb=lambda msg: _scene_message(worker, idx, total, base, msg),
        cancel_cb=lambda: bool(worker._cancel),
    )
    state["scene_pts"] = scene_pts
    state["scene_top"] = scene_top


def _store_scene_batch_detect_result(path: str, config: Dict[str, object], state: Dict[str, object]) -> None:
    scene_cache_set(
        path,
        bool(config.get("use_ff", True)),
        float(config.get("thr", 0.35)),
        int(config.get("dw", 320)),
        int(config.get("fps", 5)),
        list(state.get("scene_pts") or []),
        list(state.get("scene_top") or []),
        ff_hwaccel=bool(config.get("ff_hwaccel", False)),
    )
    store_to_disk(
        path,
        bool(config.get("use_ff", True)),
        float(config.get("thr", 0.35)),
        int(config.get("dw", 320)),
        int(config.get("fps", 5)),
        list(state.get("scene_pts") or []),
        list(state.get("scene_top") or []),
        ff_hwaccel=bool(config.get("ff_hwaccel", False)),
    )


def _update_scene_source_ms(worker, state: Dict[str, object]) -> None:
    state["scene_source_ms"] = _scene_filtered_points(
        list(state.get("scene_pts") or []),
        list(state.get("scene_top") or []),
        worker.options,
    )
    if not state["scene_source_ms"]:
        state["scene_source_ms"] = [0]


def _run_scene_batch_stage(
    worker,
    path: str,
    idx: int,
    total: int,
    base: str,
    config: Dict[str, object],
    state: Dict[str, object],
) -> None:
    if not bool(config.get("run_scene", True)):
        return
    _load_scene_batch_cache(path, config, state)
    if state.get("scene_cache_label") is not None:
        _emit_scene_batch_cache_hit(worker, idx, total, base, config, state)
    else:
        _run_scene_batch_detect(worker, path, idx, total, base, config, state)
        _store_scene_batch_detect_result(path, config, state)
    _update_scene_source_ms(worker, state)
