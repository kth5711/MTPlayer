import os
import time
from typing import List, Tuple

from PyQt6 import QtWidgets

from .export_common import _available_ffmpeg_bin, _existing_scene_path, _show_scene_busy_message
from .export_controls import on_clip_worker_busy_changed
from .export_selection import selected_clip_ranges_for_save, selected_grouped_scene_clip_ranges


def _ask_scene_clip_options(dialog):
    popup = QtWidgets.QDialog(dialog)
    popup.setWindowTitle("선택구간 클립 옵션")
    layout = QtWidgets.QFormLayout(popup)
    chk_encode = QtWidgets.QCheckBox("인코딩 모드 (체크시 재인코딩)")
    chk_encode.setChecked(True)
    fps_edit = QtWidgets.QLineEdit("0")
    scale_edit = QtWidgets.QLineEdit("0")
    br_edit = QtWidgets.QLineEdit("")
    layout.addRow(chk_encode)
    layout.addRow("FPS (0=원본):", fps_edit)
    layout.addRow("너비 (0=원본):", scale_edit)
    layout.addRow("비트레이트 (kbps, 비우면 기본):", br_edit)
    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
    )
    layout.addWidget(buttons)
    buttons.accepted.connect(popup.accept)
    buttons.rejected.connect(popup.reject)
    if popup.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None
    return (
        bool(chk_encode.isChecked()),
        int(fps_edit.text()) if fps_edit.text().strip().isdigit() else 0,
        int(scale_edit.text()) if scale_edit.text().strip().isdigit() else 0,
        br_edit.text().strip(),
    )


def _clip_export_worker(dialog):
    worker = getattr(dialog, "clip_worker", None)
    if worker is None or (not worker.isRunning()):
        raise RuntimeError("클립 워커가 실행 중이 아닙니다.")
    return worker


def _clip_export_payload(dialog, kind: str, clip_ranges: List[Tuple[int, int]], mode_label: str, source: str, clip_options=None) -> dict:
    path = _existing_scene_path(dialog)
    if not path:
        raise RuntimeError("현재 영상 경로를 찾을 수 없습니다.")
    ffbin = _available_ffmpeg_bin(dialog)
    if not ffbin:
        raise RuntimeError("ffmpeg를 찾을 수 없습니다.")
    normalized = [(int(st), int(ed)) for st, ed in (clip_ranges or []) if int(ed) > int(st)]
    if not normalized:
        raise RuntimeError("유효한 클립 구간이 없습니다.")
    payload = {
        "kind": str(kind or "ranges").strip().lower(),
        "source": str(source or "manual").strip().lower() or "manual",
        "mode_label": str(mode_label or "클립"),
        "current_path": path,
        "ffbin": ffbin,
        "clip_ranges": normalized,
    }
    if clip_options is not None:
        payload.update(
            {
                "encode": bool(clip_options[0]),
                "fps": max(0, int(clip_options[1])),
                "scale": max(0, int(clip_options[2])),
                "bitrate": str(clip_options[3] or "").strip(),
            }
        )
    return payload


def _set_clip_export_queued_status(dialog, payload: dict) -> None:
    queued = len(payload["clip_ranges"])
    status = (
        f"{payload['mode_label']} 클립 작업 큐 등록: 병합 1개"
        if payload["kind"] == "merge"
        else f"{payload['mode_label']} 클립 작업 큐 등록: {queued}개"
    )
    dialog.lbl_status.setText(status)
    on_clip_worker_busy_changed(dialog, True)


def enqueue_clip_export_job(
    dialog,
    kind: str,
    clip_ranges: List[Tuple[int, int]],
    mode_label: str,
    source: str = "manual",
    clip_options=None,
) -> int:
    worker = _clip_export_worker(dialog)
    payload = _clip_export_payload(dialog, kind, clip_ranges, mode_label, source, clip_options=clip_options)
    job_id = int(worker.enqueue(payload))
    dialog._clip_job_meta[job_id] = {
        "source": payload["source"],
        "kind": payload["kind"],
        "mode_label": payload["mode_label"],
    }
    _set_clip_export_queued_status(dialog, payload)
    return job_id


def _finished_meta(dialog, result: dict) -> Tuple[str, str, str]:
    job_id = int((result or {}).get("job_id") or 0)
    meta = dict(dialog._clip_job_meta.pop(job_id, {}) or {})
    source = str(meta.get("source") or result.get("source") or "manual").strip().lower()
    kind = str(meta.get("kind") or result.get("kind") or "ranges").strip().lower()
    mode_label = str(meta.get("mode_label") or result.get("mode_label") or "클립").strip()
    return source, kind, mode_label


def _handle_finished_gif(dialog, result: dict, source: str, mode_label: str) -> None:
    out_path = str((result or {}).get("out_path") or "")
    out_name = os.path.basename(out_path) if out_path else ""
    dialog.lbl_status.setText(f"{mode_label} 저장: {out_name or '완료'}")
    if source != "auto":
        QtWidgets.QMessageBox.information(dialog, "완료", f"GIF 저장 완료:\n{out_path}")


def _has_nonempty_output(path: str) -> bool:
    try:
        return bool(path) and os.path.exists(path) and os.path.getsize(path) > 0
    except Exception:
        return False


def _has_output_path(path: str) -> bool:
    try:
        return bool(path) and os.path.exists(path)
    except Exception:
        return False


def _wait_for_nonempty_output(path: str, timeout_ms: int = 1500, interval_ms: int = 50) -> bool:
    if _has_nonempty_output(path):
        return True
    deadline = time.time() + (max(0, int(timeout_ms)) / 1000.0)
    sleep_s = max(0.01, int(interval_ms) / 1000.0)
    while time.time() < deadline:
        time.sleep(sleep_s)
        if _has_nonempty_output(path):
            return True
    return _has_nonempty_output(path)


def _wait_for_output_path(path: str, timeout_ms: int = 3000, interval_ms: int = 50) -> bool:
    if _has_output_path(path):
        return True
    deadline = time.time() + (max(0, int(timeout_ms)) / 1000.0)
    sleep_s = max(0.01, int(interval_ms) / 1000.0)
    while time.time() < deadline:
        time.sleep(sleep_s)
        if _has_output_path(path):
            return True
    return _has_output_path(path)


def _handle_finished_merge(dialog, result: dict, source: str, mode_label: str) -> None:
    out_path = str((result or {}).get("out_path") or "")
    if source == "auto":
        dialog.lbl_status.setText(f"{mode_label} 클립 저장: 1/1개 | {out_path}")
        return
    QtWidgets.QMessageBox.information(dialog, "완료", f"클립 병합 저장 완료:\n{out_path}")


def _handle_finished_ranges(dialog, result: dict, source: str, mode_label: str) -> None:
    ok_cnt = int((result or {}).get("ok_cnt") or 0)
    total_cnt = int((result or {}).get("total_cnt") or 0)
    save_dir = str((result or {}).get("save_dir") or "")
    ok_files = list((result or {}).get("ok_files") or [])
    fail_msgs = list((result or {}).get("fail_msgs") or [])
    if source == "auto":
        suffix = " (일부 실패)" if fail_msgs else ""
        dialog.lbl_status.setText(f"{mode_label} 클립 저장: {ok_cnt}/{total_cnt}개 성공{suffix} | {save_dir}")
        return
    if ok_cnt <= 0:
        msg = "클립 생성 실패"
        if fail_msgs:
            msg = f"{msg}\n\n{fail_msgs[0]}"
        QtWidgets.QMessageBox.warning(dialog, "실패", msg)
        return
    if fail_msgs:
        QtWidgets.QMessageBox.warning(dialog, "부분 완료", f"클립 저장: {ok_cnt}/{total_cnt}개 성공\n\n실패 예시:\n{fail_msgs[0]}")
        return
    done_path = ok_files[0] if ok_files and len(ok_files) == 1 else save_dir
    QtWidgets.QMessageBox.information(dialog, "완료", f"클립 저장 완료:\n{done_path}")


def on_clip_job_finished(dialog, result: dict) -> None:
    source, kind, mode_label = _finished_meta(dialog, result)
    if kind == "gif":
        _handle_finished_gif(dialog, result, source, mode_label)
        return
    if kind == "merge":
        _handle_finished_merge(dialog, result, source, mode_label)
        return
    _handle_finished_ranges(dialog, result, source, mode_label)


def on_clip_job_failed(dialog, payload: dict) -> None:
    source, kind, mode_label = _finished_meta(dialog, payload or {})
    out_path = str((payload or {}).get("out_path") or "")
    if (kind == "gif" and _wait_for_output_path(out_path)) or _wait_for_nonempty_output(out_path):
        if kind == "gif":
            _handle_finished_gif(dialog, payload or {}, source, mode_label)
            return
        if kind == "merge":
            _handle_finished_merge(dialog, payload or {}, source, mode_label)
            return
    err = str((payload or {}).get("error") or "알 수 없는 오류").strip()
    if source == "auto":
        dialog.lbl_status.setText(f"{mode_label} 실패: {err}")
        return
    if err == "사용자 취소":
        dialog.lbl_status.setText("클립 작업 취소")
        return
    fail_label = "GIF 생성 실패" if kind == "gif" else "클립 생성 실패"
    QtWidgets.QMessageBox.warning(dialog, "실패", f"{fail_label}: {err}")


def _warn_scene_clip_selection_required(dialog) -> None:
    QtWidgets.QMessageBox.information(
        dialog,
        "알림",
        "클립 저장 대상을 선택하세요.\n- 구간묶음 씬 선택(직행 결과 구간 묶기)\n- 또는 프레임셋/씬 결과에서 서로 다른 2개 시점 선택",
    )


def save_selected_scene_range_clip(dialog) -> None:
    if _show_scene_busy_message(dialog):
        return
    if not _existing_scene_path(dialog):
        QtWidgets.QMessageBox.warning(dialog, "오류", "현재 영상 경로를 찾을 수 없습니다.")
        return
    clip_ranges = selected_clip_ranges_for_save(dialog)
    if not clip_ranges:
        _warn_scene_clip_selection_required(dialog)
        return
    grouped_ranges = selected_grouped_scene_clip_ranges(dialog)
    merge_grouped = bool(
        grouped_ranges
        and len(grouped_ranges) >= 2
        and bool(dialog.chk_scene_clip_merge.isChecked() if hasattr(dialog, "chk_scene_clip_merge") else False)
    )
    clip_options = _ask_scene_clip_options(dialog)
    if clip_options is None:
        return
    try:
        if merge_grouped:
            enqueue_clip_export_job(
                dialog,
                "merge",
                grouped_ranges,
                mode_label="구간묶음합치기",
                source="manual",
                clip_options=clip_options,
            )
            return
        mode_label = "구간묶음" if grouped_ranges else "수동구간"
        enqueue_clip_export_job(
            dialog,
            "ranges",
            clip_ranges,
            mode_label=mode_label,
            source="manual",
            clip_options=clip_options,
        )
    except Exception as e:
        fail_label = "클립 병합 실패" if merge_grouped else "클립 생성 실패"
        QtWidgets.QMessageBox.warning(dialog, "실패", f"{fail_label}: {e}")
