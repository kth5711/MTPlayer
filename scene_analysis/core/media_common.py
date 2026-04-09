from __future__ import annotations

from typing import Any
import logging


SIGLIP_BATCH_MIN = 16
SIGLIP_BATCH_MAX = 256
SIGLIP_BATCH_STEP = 16
SIGLIP_BATCH_DEFAULT = 64

logger = logging.getLogger(__name__)


def _normalize_siglip_batch_size(value: Any, default: int = SIGLIP_BATCH_DEFAULT) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        logger.debug("siglip batch size normalization input parse failed", exc_info=True)
        n = int(default)
    n = max(int(SIGLIP_BATCH_MIN), min(int(SIGLIP_BATCH_MAX), int(n)))
    base = int(SIGLIP_BATCH_MIN)
    step = int(max(1, SIGLIP_BATCH_STEP))
    idx = int(round((float(n - base)) / float(step)))
    out = base + (idx * step)
    out = max(int(SIGLIP_BATCH_MIN), min(int(SIGLIP_BATCH_MAX), int(out)))
    return int(out)


def _siglip_batch_levels_up_to(limit: int) -> tuple[int, ...]:
    top = _normalize_siglip_batch_size(limit)
    arr = list(range(int(SIGLIP_BATCH_MIN), int(top) + 1, int(SIGLIP_BATCH_STEP)))
    if not arr:
        arr = [int(SIGLIP_BATCH_MIN)]
    return tuple(int(x) for x in arr)


def _first_float(value, default: float = 0.0) -> float:
    if isinstance(value, (list, tuple)):
        for item in value:
            try:
                return float(item)
            except (TypeError, ValueError):
                continue
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


__all__ = [
    "SIGLIP_BATCH_DEFAULT",
    "SIGLIP_BATCH_MAX",
    "SIGLIP_BATCH_MIN",
    "SIGLIP_BATCH_STEP",
    "_first_float",
    "_normalize_siglip_batch_size",
    "_siglip_batch_levels_up_to",
]
