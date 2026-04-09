from typing import Any, List
import logging
import os

from scene_analysis.core.media import SIGLIP_BATCH_DEFAULT
from scene_analysis.core.similarity import (
    _auto_decode_chunk_batch_limits,
    _normalize_adapter_path,
    _normalize_siglip_decode_scale_w,
    _siglip2_default_model_id,
)


logger = logging.getLogger(__name__)


def current_siglip_batch_size(dialog) -> int:
    path = _current_dialog_video_path(dialog)
    prefer_gpu_decode = True
    try:
        if hasattr(dialog, "chk_cpu_decode"):
            prefer_gpu_decode = not bool(dialog.chk_cpu_decode.isChecked())
    except (AttributeError, RuntimeError):
        logger.debug("siglip decode mode read failed for auto batch", exc_info=True)
    try:
        _auto_chunk, auto_batch, _tier, _w, _h = _auto_decode_chunk_batch_limits(
            path,
            prefer_gpu_decode=prefer_gpu_decode,
        )
        return int(auto_batch)
    except Exception:
        logger.debug("siglip auto batch fallback used", exc_info=True)
        return int(SIGLIP_BATCH_DEFAULT)


def current_siglip_decode_scale_w(dialog) -> int:
    raw = 0
    try:
        if hasattr(dialog, "cmb_siglip_decode_scale"):
            value = dialog.cmb_siglip_decode_scale.currentData()
            raw = int(value if value is not None else 0)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        logger.debug("siglip decode scale read failed", exc_info=True)
    return _normalize_siglip_decode_scale_w(raw, default=0)


def current_siglip_scene_feature_cache_enabled(_dialog) -> bool:
    return True


def set_siglip_decode_scale_w(dialog, value: Any) -> None:
    if not hasattr(dialog, "cmb_siglip_decode_scale"):
        return
    normalized = _normalize_siglip_decode_scale_w(value, default=0)
    combo = dialog.cmb_siglip_decode_scale
    index = combo.findData(int(normalized))
    if index < 0:
        index = _nearest_siglip_scale_index(combo, normalized)
    if index >= 0:
        combo.setCurrentIndex(int(index))


def current_siglip_two_stage(dialog) -> bool:
    try:
        return bool(dialog.chk_siglip_two_stage.isChecked())
    except (AttributeError, RuntimeError):
        logger.debug("siglip two-stage checkbox read failed", exc_info=True)
        return False


def current_siglip_stage2_ratio(dialog) -> float:
    try:
        percent = int(dialog.spn_siglip_stage2_ratio.value())
    except (AttributeError, RuntimeError, TypeError, ValueError):
        logger.debug("siglip stage2 ratio read failed", exc_info=True)
        percent = 35
    return max(0.10, min(1.00, float(percent) / 100.0))


def on_siglip_two_stage_changed(dialog, *_args) -> None:
    dialog.spn_siglip_stage2_ratio.setEnabled(bool(dialog.chk_siglip_two_stage.isChecked()))


def current_siglip_model_id(_dialog) -> str:
    return _siglip2_default_model_id()


def current_siglip_adapter_path(dialog) -> str:
    return _normalize_adapter_path(str(dialog.edt_siglip_adapter.text() or ""))


def siglip_runtime_device(_dialog) -> str:
    try:
        import torch  # type: ignore

        if bool(getattr(torch, "cuda", None)) and torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _nearest_siglip_scale_index(combo, normalized: int) -> int:
    candidates: List[tuple[int, int]] = []
    for index in range(int(combo.count())):
        try:
            value = _normalize_siglip_decode_scale_w(combo.itemData(index), default=0)
        except (TypeError, ValueError):
            continue
        candidates.append((index, value))
    if not candidates:
        return -1
    return min(candidates, key=lambda item: abs(int(item[1]) - int(normalized)))[0]


def _current_dialog_video_path(dialog) -> str:
    path = os.path.abspath(str(getattr(dialog, "current_path", "") or ""))
    if path and os.path.exists(path):
        return path
    try:
        host_path = os.path.abspath(str(dialog.host._current_media_path() or ""))
        if host_path and os.path.exists(host_path):
            return host_path
    except Exception:
        logger.debug("siglip auto batch host path lookup failed", exc_info=True)
    return ""
