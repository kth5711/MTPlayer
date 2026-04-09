import os
from typing import List

from PyQt6 import QtWidgets

from scene_analysis.core.cache import (
    _normalize_sample_paths,
    _normalize_sample_texts,
    _read_json_dict,
    _read_siglip_scene_feature_meta,
    resolve_cached_video_path,
)
from scene_analysis.core.similarity import _normalize_refilter_mode, _siglip_decode_scale_label

from .history_shared import sampling_mode_label, sampling_mode_value, set_combo_data, set_scene_control_tab


def load_refilter_cache_entry(dialog, ent: dict) -> None:
    payload = _read_json_dict(str(ent.get("file_path") or ""))
    if not payload:
        QtWidgets.QMessageBox.warning(dialog, "오류", "유사씬 캐시를 읽을 수 없습니다.")
        return
    pairs = _normalized_pairs(payload.get("pairs") or [])
    if not pairs:
        QtWidgets.QMessageBox.information(dialog, "알림", "선택한 유사씬 캐시에 결과가 없습니다.")
        return
    path = _history_path(dialog, payload, ent)
    if not dialog._ensure_history_video_loaded(path):
        return
    _prepare_refilter_history_view(dialog)
    source_ms = _source_ms(payload, pairs)
    _apply_refilter_form_state(dialog, payload)
    dialog._refilter_source_data = [(int(ms), 0.0) for ms in source_ms]
    dialog._refilter_source_override_ms = list(source_ms)
    dialog._direct_group_clip_ranges = {}
    dialog._apply_refilter_pairs(dialog._refilter_source_data, pairs, _normalize_refilter_mode(str(payload.get("mode") or "siglip2")), cache_hit=True, allow_auto_clip=False)


def load_siglip_feature_cache_entry(dialog, ent: dict) -> None:
    meta = _read_siglip_scene_feature_meta(str(ent.get("file_path") or ""))
    if not meta:
        QtWidgets.QMessageBox.warning(dialog, "오류", "영상캐시 메타데이터를 읽을 수 없습니다.")
        return
    path = _history_path(dialog, meta, ent)
    if path and not dialog._ensure_history_video_loaded(path):
        return
    _prepare_refilter_history_view(dialog)
    _apply_siglip_feature_state(dialog, meta)
    dialog.lbl_status.setText(_siglip_feature_status(meta))


def _normalized_pairs(raw_pairs) -> List[tuple[int, float]]:
    out: List[tuple[int, float]] = []
    for row in raw_pairs or []:
        try:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                out.append((int(row[0]), float(row[1])))
        except Exception:
            continue
    return out


def _history_path(dialog, payload: dict, ent: dict) -> str:
    path = os.path.abspath(str(payload.get("video_path") or ent.get("video_path") or ""))
    current_path = dialog._history_current_video_path()
    try:
        video_mtime_ns = int(payload.get("video_mtime_ns", ent.get("video_mtime_ns", 0)) or 0)
    except Exception:
        video_mtime_ns = 0
    try:
        video_size = int(payload.get("video_size", ent.get("video_size", 0)) or 0)
    except Exception:
        video_size = 0
    return resolve_cached_video_path(current_path, path, video_mtime_ns, video_size) or current_path


def _prepare_refilter_history_view(dialog) -> None:
    set_scene_control_tab(dialog, 1)
    try:
        dialog.raise_()
        dialog.activateWindow()
    except Exception:
        pass


def _source_ms(payload: dict, pairs) -> List[int]:
    out: List[int] = []
    for value in payload.get("scene_ms") or []:
        try:
            if int(value) >= 0:
                out.append(int(value))
        except Exception:
            continue
    if not out:
        out = [int(ms) for ms, _sim in pairs]
    return sorted(set(out))


def _apply_refilter_form_state(dialog, payload: dict) -> None:
    _apply_refilter_samples(dialog, payload)
    _apply_refilter_combo_state(dialog, payload)
    _apply_refilter_numeric_state(dialog, payload)
    _apply_refilter_toggle_state(dialog, payload)


def _apply_refilter_samples(dialog, payload: dict) -> None:
    try:
        dialog.sample_image_paths = list(_normalize_sample_paths(payload.get("sample_image_paths") or []))
        dialog._update_ref_image_text()
        dialog.edt_ref_text.setPlainText("\n".join(_normalize_sample_texts(payload.get("sample_texts") or [])))
    except Exception:
        pass


def _apply_refilter_combo_state(dialog, payload: dict) -> None:
    set_combo_data(dialog, "cmb_refilter_agg", str(payload.get("agg_mode") or "max"))
    set_combo_data(dialog, "cmb_frame_profile", str(payload.get("frame_profile") or "normal"))
    set_combo_data(dialog, "cmb_refilter_sampling", sampling_mode_value(payload.get("sampling_mode") or "start_frame"))
    source_mode = str(payload.get("source_mode") or "").strip().lower()
    if source_mode in ("scene", "direct"):
        set_combo_data(dialog, "cmb_refilter_source", source_mode)


def _apply_refilter_numeric_state(dialog, payload: dict) -> None:
    _set_spin(dialog, "spn_kofn_k", payload.get("kofn_k"), minimum=1)
    _set_spin(dialog, "spn_siglip_stage2_ratio", payload.get("siglip_stage2_ratio"), scale=100.0, minimum=10, maximum=100)
    _set_spin(dialog, "spn_refilter_direct_sec", payload.get("direct_interval_sec"), minimum=1)
    _set_double(dialog, "spn_sim_thr", payload.get("sim_threshold"), 0.0, 1.0)
    if isinstance(payload.get("siglip_ffmpeg_scale_w"), (int, float)):
        dialog._set_siglip_decode_scale_w(int(payload.get("siglip_ffmpeg_scale_w")))


def _apply_refilter_toggle_state(dialog, payload: dict) -> None:
    _set_line_edit(dialog, "edt_siglip_adapter", str(payload.get("siglip_adapter_path") or ""))
    _set_checkbox(dialog, "chk_siglip_two_stage", bool(payload.get("siglip_two_stage", False)))
    for slot_name in ("_on_refilter_agg_changed", "_on_refilter_sampling_mode_changed", "_on_siglip_two_stage_changed", "_on_refilter_source_mode_changed"):
        try:
            getattr(dialog, slot_name)()
        except Exception:
            pass


def _apply_siglip_feature_state(dialog, meta: dict) -> None:
    set_combo_data(dialog, "cmb_frame_profile", str(meta.get("frame_profile") or "normal"))
    set_combo_data(dialog, "cmb_refilter_sampling", sampling_mode_value(meta.get("sampling_mode") or "start_frame"))
    if "siglip_ffmpeg_scale_w" in meta:
        try:
            dialog._set_siglip_decode_scale_w(int(meta.get("siglip_ffmpeg_scale_w") or 0))
        except Exception:
            pass
    _set_line_edit(dialog, "edt_siglip_adapter", str(meta.get("siglip_adapter_path") or ""))
    _set_checkbox(dialog, "chk_siglip_two_stage", bool(meta.get("siglip_two_stage", False)))
    try:
        dialog._on_siglip_two_stage_changed()
    except Exception:
        pass


def _siglip_feature_status(meta: dict) -> str:
    model_id = str(meta.get("siglip_model_id") or "").strip()
    model_note = f", 모델={model_id}" if model_id else ""
    scale_note = _siglip_decode_scale_label(int(meta.get("siglip_ffmpeg_scale_w", 0) or 0), compact=True)
    return f"영상캐시 설정 적용: 유사씬 탭 / {sampling_mode_label(str(meta.get('sampling_mode') or 'start_frame'))} / {str(meta.get('frame_profile') or 'normal')} / scale={scale_note}{model_note}"


def _set_spin(dialog, attr_name: str, value, *, minimum: int, maximum: int | None = None, scale: float | None = None):
    if not isinstance(value, (int, float)) or not hasattr(dialog, attr_name):
        return
    val = int(round(float(value) * scale)) if scale is not None else int(value)
    val = max(minimum, val)
    if maximum is not None:
        val = min(maximum, val)
    try:
        getattr(dialog, attr_name).setValue(val)
    except Exception:
        pass


def _set_double(dialog, attr_name: str, value, minimum: float, maximum: float):
    if not isinstance(value, (int, float)) or not hasattr(dialog, attr_name):
        return
    try:
        getattr(dialog, attr_name).setValue(max(minimum, min(maximum, float(value))))
    except Exception:
        pass


def _set_line_edit(dialog, attr_name: str, text: str):
    if not hasattr(dialog, attr_name):
        return
    try:
        getattr(dialog, attr_name).setText(text)
    except Exception:
        pass


def _set_checkbox(dialog, attr_name: str, checked: bool):
    if not hasattr(dialog, attr_name):
        return
    try:
        getattr(dialog, attr_name).setChecked(bool(checked))
    except Exception:
        pass
