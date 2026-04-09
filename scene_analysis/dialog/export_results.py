import os
from typing import Optional

from PyQt6 import QtWidgets

from .export_common import _existing_scene_path, _pixmap_safe, _show_scene_busy_message
from .export_selection import selected_grouped_scene_clip_ranges, selected_scene_ms_list_for_save


def _scene_shot_save_dir(path: str) -> tuple[str, str]:
    base_dir = os.path.dirname(path)
    base_name, _ = os.path.splitext(os.path.basename(path))
    save_dir = os.path.join(base_dir, f"{base_name}_scene_shots")
    os.makedirs(save_dir, exist_ok=True)
    return base_name, save_dir


def _scene_shot_output_path(base_name: str, save_dir: str, idx: int, label: str, ms: int) -> str:
    return os.path.join(save_dir, f"{base_name}_scene_{idx:04d}_{label}_{int(ms):08d}ms.png")


def _save_scene_shot_with_capture(cap, cv2_mod, out_path: str, ms: int) -> bool:
    if cap is None or cv2_mod is None:
        return False
    try:
        cap.set(cv2_mod.CAP_PROP_POS_MSEC, max(0, int(ms)))
        rr, frame = cap.read()
        return bool(rr and frame is not None and cv2_mod.imwrite(out_path, frame))
    except Exception:
        return False


def _save_scene_shot_with_pixmap(dialog, out_path: str, ms: int) -> bool:
    get_thumb = getattr(dialog.host, "_get_frame_thumbnail", None)
    if get_thumb is None:
        return False
    try:
        pm = _pixmap_safe(get_thumb, dialog.current_path, int(ms), w=1920, h=1080)
    except Exception:
        pm = None
    if pm is None or pm.isNull():
        return False
    try:
        return bool(pm.save(out_path, "PNG"))
    except Exception:
        return False


def _save_single_scene_shot(dialog, cap, cv2_mod, base_name: str, save_dir: str, idx: int, ms: int) -> bool:
    label = dialog._format_ms_mmss(ms).replace(":", "-")
    out_path = _scene_shot_output_path(base_name, save_dir, idx, label, ms)
    if _save_scene_shot_with_capture(cap, cv2_mod, out_path, ms):
        return True
    return _save_scene_shot_with_pixmap(dialog, out_path, ms)


def _open_scene_capture(path: str) -> tuple[Optional[object], Optional[object]]:
    try:
        import cv2  # type: ignore
    except Exception:
        return None, None
    cap = cv2.VideoCapture(path)
    if cap is None or not cap.isOpened():
        return None, cv2
    return cap, cv2


def save_selected_scene_result_shots(dialog) -> None:
    if _show_scene_busy_message(dialog):
        return
    path = _existing_scene_path(dialog)
    if not path:
        QtWidgets.QMessageBox.warning(dialog, "오류", "현재 영상 경로를 찾을 수 없습니다.")
        return
    ms_list = selected_scene_ms_list_for_save(dialog)
    if not ms_list:
        QtWidgets.QMessageBox.information(dialog, "알림", "저장할 씬 결과를 먼저 선택하세요.")
        return
    base_name, save_dir = _scene_shot_save_dir(path)
    cap, cv2_mod = _open_scene_capture(path)
    saved = 0
    try:
        for idx, ms in enumerate(ms_list, start=1):
            if _save_single_scene_shot(dialog, cap, cv2_mod, base_name, save_dir, idx, int(ms)):
                saved += 1
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
    dialog.lbl_status.setText(f"선택 결과 프레임샷 저장: {saved}/{len(ms_list)}장 | {save_dir}")
    if saved <= 0:
        QtWidgets.QMessageBox.warning(dialog, "실패", "프레임샷 저장에 실패했습니다.")


def _scene_bookmark_main_window(dialog):
    try:
        if hasattr(dialog.host, "_main_window"):
            return dialog.host._main_window()
    except Exception:
        pass
    return None


def add_selected_scene_results_to_bookmarks(dialog) -> None:
    if _show_scene_busy_message(dialog):
        return
    path = _existing_scene_path(dialog, allow_host_fallback=True)
    if not path:
        QtWidgets.QMessageBox.warning(dialog, "오류", "현재 영상 경로를 찾을 수 없습니다.")
        return
    grouped_ranges = selected_grouped_scene_clip_ranges(dialog)
    ms_list = selected_scene_ms_list_for_save(dialog) if not grouped_ranges else []
    if not grouped_ranges and not ms_list:
        QtWidgets.QMessageBox.information(dialog, "알림", "책갈피로 보낼 씬 결과를 먼저 선택하세요.")
        return
    mainwin = _scene_bookmark_main_window(dialog)
    if mainwin is None:
        QtWidgets.QMessageBox.warning(dialog, "오류", "책갈피 기능을 찾을 수 없습니다.")
        return
    if grouped_ranges:
        if not hasattr(mainwin, "_add_bookmarks_for_path_ranges"):
            QtWidgets.QMessageBox.warning(dialog, "오류", "구간 책갈피 기능을 찾을 수 없습니다.")
            return
        added, skipped = mainwin._add_bookmarks_for_path_ranges(path, grouped_ranges)
    else:
        if not hasattr(mainwin, "_add_bookmarks_for_path_positions"):
            QtWidgets.QMessageBox.warning(dialog, "오류", "책갈피 기능을 찾을 수 없습니다.")
            return
        added, skipped = mainwin._add_bookmarks_for_path_positions(path, ms_list)
    if added <= 0:
        dialog.lbl_status.setText(f"책갈피 추가: 중복 {skipped}개로 건너뜀")
        return
    suffix = f" (중복 {skipped}개 제외)" if skipped > 0 else ""
    dialog.lbl_status.setText(f"책갈피 추가: {added}개{suffix}")
