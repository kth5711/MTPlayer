import os

from PyQt6 import QtWidgets

from .export_common import _current_existing_media_path, _tile_status_message
from .support import is_image_file_path


def _screenshot_output_path(tile, path: str) -> str:
    base_dir = os.path.dirname(path)
    base_name, _ = os.path.splitext(os.path.basename(path))
    save_dir = os.path.join(base_dir, f"{base_name}_screenshots")
    os.makedirs(save_dir, exist_ok=True)
    cur_ms = max(0, int(tile.mediaplayer.get_time() or 0))
    t_str = tile._ms_to_hms(cur_ms).replace(":", "-")
    return os.path.join(save_dir, f"{base_name}_{t_str}_{cur_ms:08d}.png")


def _save_image_screenshot(tile, out_path: str) -> bool:
    try:
        pixmap = tile._current_image_export_pixmap()
    except Exception:
        pixmap = None
    if pixmap is None or pixmap.isNull():
        return False
    try:
        return bool(pixmap.save(out_path, "PNG"))
    except Exception:
        return False


def _save_video_screenshot(tile, out_path: str) -> bool:
    try:
        rc = int(tile.mediaplayer.video_take_snapshot(0, out_path, 0, 0))
        return rc == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception:
        return False


def _save_video_screenshot_fallback(tile, path: str, out_path: str) -> bool:
    cur_ms = max(0, int(tile.mediaplayer.get_time() or 0))
    try:
        pixmap = tile._get_frame_thumbnail_safe(path, cur_ms, w=1920, h=1080)
    except Exception:
        pixmap = None
    if pixmap is None or pixmap.isNull():
        return False
    try:
        return bool(pixmap.save(out_path, "PNG"))
    except Exception:
        return False


def capture_screenshot(tile):
    path = _current_existing_media_path(tile)
    if not path:
        QtWidgets.QMessageBox.information(tile, "알림", "스크린샷을 저장할 영상이 없습니다.")
        return
    out_path = _screenshot_output_path(tile, path)
    is_image = is_image_file_path(path)
    saved = _save_image_screenshot(tile, out_path) if is_image else _save_video_screenshot(tile, out_path)
    if (not saved) and (not is_image):
        saved = _save_video_screenshot_fallback(tile, path, out_path)
    if saved:
        _tile_status_message(tile, f"스크린샷 저장: {out_path}", 3000)
        return
    QtWidgets.QMessageBox.warning(tile, "실패", "스크린샷 저장에 실패했습니다.")


def _frameset_output_dir(tile, path: str, duration_sec: int) -> tuple[str, str]:
    base_dir = os.path.dirname(path)
    base_name, _ = os.path.splitext(os.path.basename(path))
    save_root = os.path.join(base_dir, f"{base_name}_framesets")
    os.makedirs(save_root, exist_ok=True)
    cur_ms = max(0, int(tile.mediaplayer.get_time() or 0))
    stamp = tile._ms_to_hms(cur_ms).replace(":", "-")
    out_dir = os.path.join(save_root, f"{base_name}_{stamp}_{cur_ms:08d}_{duration_sec:02d}s")
    os.makedirs(out_dir, exist_ok=True)
    return base_name, out_dir


def _frame_time_ms(start_ms: int, duration_sec: int, frame_count: int, idx: int) -> int:
    if frame_count <= 1:
        return start_ms
    return start_ms + int(round((duration_sec * 1000 * idx) / float(frame_count - 1)))


def _capture_total_ms(cap, cv2_mod) -> int:
    fps = float(cap.get(cv2_mod.CAP_PROP_FPS) or 0.0)
    total_frames = float(cap.get(cv2_mod.CAP_PROP_FRAME_COUNT) or 0.0)
    if fps <= 1e-6 or total_frames <= 1.0:
        return 0
    return max(0, int(round((total_frames / fps) * 1000.0)))


def _save_cv2_frame(cap, cv2_mod, out_dir: str, idx: int, t_ms: int) -> str:
    cap.set(cv2_mod.CAP_PROP_POS_MSEC, max(0, int(t_ms)))
    ok_read, frame = cap.read()
    if not ok_read or frame is None:
        return ""
    file_path = os.path.join(out_dir, f"{idx + 1:04d}.jpg")
    cv2_mod.imwrite(file_path, frame, [int(cv2_mod.IMWRITE_JPEG_QUALITY), 95])
    return file_path if os.path.exists(file_path) else ""


def _save_frameset_cv2(tile, path: str, out_dir: str, duration_sec: int, frame_count: int) -> list[str]:
    saved_files: list[str] = []
    try:
        import cv2  # type: ignore
    except Exception:
        return saved_files
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return saved_files
    cur_ms = max(0, int(tile.mediaplayer.get_time() or 0))
    start_ms = max(0, cur_ms - int(duration_sec * 1000) // 2)
    try:
        total_ms = _capture_total_ms(cap, cv2)
        if total_ms > 0 and (start_ms + duration_sec * 1000) > total_ms:
            start_ms = max(0, total_ms - duration_sec * 1000)
        for idx in range(frame_count):
            t_ms = _frame_time_ms(start_ms, duration_sec, frame_count, idx)
            file_path = _save_cv2_frame(cap, cv2, out_dir, idx, t_ms)
            if file_path:
                saved_files.append(file_path)
    finally:
        try:
            cap.release()
        except Exception:
            pass
    return saved_files


def _save_frameset_pixmaps(tile, path: str, out_dir: str, duration_sec: int, frame_count: int) -> list[str]:
    saved_files: list[str] = []
    cur_ms = max(0, int(tile.mediaplayer.get_time() or 0))
    start_ms = max(0, cur_ms - int(duration_sec * 1000) // 2)
    for idx in range(frame_count):
        t_ms = _frame_time_ms(start_ms, duration_sec, frame_count, idx)
        try:
            pixmap = tile._get_frame_thumbnail_safe(path, int(t_ms), w=1280, h=720)
        except Exception:
            pixmap = None
        if pixmap is None or pixmap.isNull():
            continue
        file_path = os.path.join(out_dir, f"{idx + 1:04d}.jpg")
        try:
            if pixmap.save(file_path, "JPG"):
                saved_files.append(file_path)
        except Exception:
            pass
    return saved_files


def save_frame_set(tile):
    path = _current_existing_media_path(tile)
    if not path:
        QtWidgets.QMessageBox.information(tile, "알림", "프레임셋을 저장할 영상이 없습니다.")
        return
    if is_image_file_path(path):
        QtWidgets.QMessageBox.information(tile, "알림", "이미지에서는 프레임셋 저장을 지원하지 않습니다.")
        return
    duration_sec, ok = QtWidgets.QInputDialog.getInt(tile, "프레임셋 저장", "구간(초, 1~10):", 3, 1, 10, 1)
    if not ok:
        return
    frame_count = max(4, min(20, int(round(duration_sec * 2.0))))
    _base_name, out_dir = _frameset_output_dir(tile, path, duration_sec)
    saved_files = _save_frameset_cv2(tile, path, out_dir, duration_sec, frame_count)
    if not saved_files:
        saved_files = _save_frameset_pixmaps(tile, path, out_dir, duration_sec, frame_count)
    if saved_files:
        _tile_status_message(tile, f"프레임셋 저장: {len(saved_files)}장 | {out_dir}", 4000)
        return
    QtWidgets.QMessageBox.warning(tile, "실패", "프레임셋 저장에 실패했습니다.")
