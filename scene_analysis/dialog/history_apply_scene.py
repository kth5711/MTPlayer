import os
from typing import List

from PyQt6 import QtWidgets

from scene_analysis.core.cache import _read_json_dict, resolve_cached_video_path
from .history_shared import set_scene_control_tab


def load_scene_cache_entry(dialog, ent: dict) -> None:
    payload = _scene_payload(dialog, ent)
    if payload is None:
        return
    path, pts, top = payload
    _prepare_scene_history_view(dialog)
    _apply_scene_scan_options(dialog, _read_json_dict(str(ent.get("file_path") or "")))
    filtered_pts = dialog._filter_pts(dialog._apply_user_threshold(pts, top), top)
    dialog._populate_from_result(path, filtered_pts, top)
    dialog.lbl_status.setText(f"결과기록 로드(씬변화): {len(filtered_pts)}개 표시 / 원본 {len(pts)}개")


def _scene_payload(dialog, ent: dict):
    payload = _read_json_dict(str(ent.get("file_path") or ""))
    if not payload:
        QtWidgets.QMessageBox.warning(dialog, "오류", "씬변화 캐시를 읽을 수 없습니다.")
        return None
    pts = _normalized_points(payload.get("pts") or [])
    top = _normalized_pairs(payload.get("top") or payload.get("top10") or [])
    if not pts:
        QtWidgets.QMessageBox.information(dialog, "알림", "선택한 씬변화 캐시에 결과가 없습니다.")
        return None
    path = _payload_video_path(dialog, payload, ent)
    return (path, pts, top) if dialog._ensure_history_video_loaded(path) else None


def _normalized_points(raw_points) -> List[int]:
    out: List[int] = []
    for value in raw_points:
        try:
            if int(value) >= 0:
                out.append(int(value))
        except Exception:
            continue
    return sorted(set(out))


def _normalized_pairs(raw_pairs) -> List[tuple[int, float]]:
    out: List[tuple[int, float]] = []
    for row in raw_pairs or []:
        try:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                out.append((int(row[0]), float(row[1])))
        except Exception:
            continue
    return out


def _payload_video_path(dialog, payload: dict, ent: dict) -> str:
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


def _apply_scene_scan_options(dialog, payload: dict) -> None:
    try:
        if "ff_hwaccel" in payload and hasattr(dialog, "chk_cpu_decode"):
            dialog.chk_cpu_decode.setChecked(not bool(payload.get("ff_hwaccel")))
        for attr, key, cast in (("spn_thr", "thr", float), ("spn_dw", "dw", int), ("spn_fps", "fps", int)):
            if isinstance(payload.get(key), (int, float)):
                getattr(dialog, attr).setValue(cast(payload.get(key)))
    except Exception:
        pass


def _prepare_scene_history_view(dialog) -> None:
    set_scene_control_tab(dialog, 0)
    try:
        dialog.raise_()
        dialog.activateWindow()
    except Exception:
        pass
