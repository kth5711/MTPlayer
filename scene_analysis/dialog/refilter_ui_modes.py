import logging

from scene_analysis.core.similarity import (
    REFILTER_FRAME_PROFILES,
    _normalize_refilter_agg_mode,
)


logger = logging.getLogger(__name__)


def current_refilter_mode(_dialog) -> str:
    return "siglip2"


def current_refilter_agg_mode(dialog) -> str:
    mode = dialog.cmb_refilter_agg.currentData()
    if isinstance(mode, str) and mode:
        return _normalize_refilter_agg_mode(mode)
    text = dialog.cmb_refilter_agg.currentText().strip().lower()
    if "k-of-n" in text or "kofn" in text:
        return "kofn"
    return "max"


def current_auto_clip_end_mode(dialog) -> str:
    mode = dialog.cmb_auto_clip_end_mode.currentData() if hasattr(dialog, "cmb_auto_clip_end_mode") else "next_scene"
    normalized = str(mode or "").strip().lower()
    return normalized if normalized in ("next_scene", "sim_drop") else "next_scene"


def current_refilter_source_mode(dialog) -> str:
    mode = dialog.cmb_refilter_source.currentData() if hasattr(dialog, "cmb_refilter_source") else "direct"
    normalized = str(mode or "").strip().lower()
    return "scene" if normalized == "scene" else "direct"


def current_refilter_direct_sec(dialog) -> int:
    try:
        return max(1, min(120, int(dialog.spn_refilter_direct_sec.value())))
    except (AttributeError, RuntimeError, TypeError, ValueError):
        logger.debug("refilter direct interval read failed", exc_info=True)
        return 2


def current_refilter_direct_group_enabled(dialog) -> bool:
    try:
        return bool(dialog.chk_refilter_direct_group.isChecked())
    except (AttributeError, RuntimeError):
        logger.debug("refilter direct group checkbox read failed", exc_info=True)
        return False


def current_refilter_direct_group_band(dialog) -> float:
    try:
        return max(0.01, min(0.20, float(dialog.spn_refilter_direct_group_band.value())))
    except (AttributeError, RuntimeError, TypeError, ValueError):
        logger.debug("refilter direct group band read failed", exc_info=True)
        return 0.05


def current_kofn_k(dialog) -> int:
    return max(1, int(dialog.spn_kofn_k.value()))


def current_frame_profile(dialog) -> str:
    profile = dialog.cmb_frame_profile.currentData()
    normalized = str(profile or "").strip().lower()
    return normalized if normalized in REFILTER_FRAME_PROFILES else "normal"


def current_refilter_sampling_mode(dialog) -> str:
    mode = dialog.cmb_refilter_sampling.currentData() if hasattr(dialog, "cmb_refilter_sampling") else "start_frame"
    if hasattr(dialog, "_normalize_refilter_sampling_mode"):
        return dialog._normalize_refilter_sampling_mode(mode)
    return str(mode or "")


def on_refilter_agg_changed(dialog, *_args) -> None:
    dialog.spn_kofn_k.setEnabled(dialog._current_refilter_agg_mode() == "kofn")


def on_refilter_source_mode_changed(dialog, *_args) -> None:
    is_direct = dialog._current_refilter_source_mode() == "direct"
    if not is_direct:
        dialog._refilter_source_override_ms = []
    dialog.spn_refilter_direct_sec.setEnabled(is_direct)
    dialog.chk_refilter_direct_group.setEnabled(is_direct)
    dialog.spn_refilter_direct_group_band.setEnabled(is_direct and dialog._current_refilter_direct_group_enabled())


def on_refilter_sampling_mode_changed(dialog, *_args) -> None:
    is_scene_window = dialog._current_refilter_sampling_mode() == "scene_window"
    try:
        dialog.cmb_frame_profile.setEnabled(
            (dialog.refilter_worker is None or not dialog.refilter_worker.isRunning()) and is_scene_window
        )
    except (AttributeError, RuntimeError):
        logger.debug("refilter sampling mode UI update skipped", exc_info=True)


def refilter_mode_label(_dialog, _mode: str) -> str:
    return "SigLIP2"
