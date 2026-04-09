import weakref

from PyQt6 import QtWidgets

from scene_analysis.core.clip import ClipExportQueueWorker

from .export_common import _tile_export_message, _tile_status_message


def _tile_export_busy_changed(tile, busy: bool) -> None:
    tile._export_worker_busy = bool(busy)
    for name in ("btn_gif", "btn_clip"):
        btn = getattr(tile, name, None)
        if btn is not None:
            try:
                btn.setEnabled(not bool(busy))
            except Exception:
                pass


def _tile_job_meta(tile) -> dict:
    meta = getattr(tile, "_export_job_meta", None)
    if meta is None:
        tile._export_job_meta = {}
    return tile._export_job_meta


def _tile_export_finished(tile, result: dict) -> None:
    meta = dict(_tile_job_meta(tile).pop(int((result or {}).get("job_id") or 0), {}) or {})
    kind = str(meta.get("kind") or result.get("kind") or "").strip().lower()
    out_path = str((result or {}).get("out_path") or "")
    if kind == "gif":
        label = "GIF 저장"
    elif kind == "tile_audio_clip":
        label = "오디오 클립 저장"
    else:
        label = "클립 저장"
    _tile_status_message(tile, f"{label}: {out_path}", 4000)
    QtWidgets.QMessageBox.information(tile, "완료", f"{label}됨:\n{out_path}")


def _tile_export_failed(tile, payload: dict) -> None:
    meta = dict(_tile_job_meta(tile).pop(int((payload or {}).get("job_id") or 0), {}) or {})
    kind = str(meta.get("kind") or payload.get("kind") or "").strip().lower()
    err = str((payload or {}).get("error") or "알 수 없는 오류").strip()
    if err == "사용자 취소":
        _tile_status_message(tile, "내보내기 취소", 3000)
        return
    label = "GIF 생성 실패" if kind == "gif" else ("오디오 클립 생성 실패" if kind == "tile_audio_clip" else "클립 생성 실패")
    QtWidgets.QMessageBox.critical(tile, "실패", f"{label}: {err}")
    _tile_status_message(tile, label, 4000)


def _dispatch_tile_callback(tile_ref, callback, *args) -> None:
    tile = tile_ref()
    if tile is None:
        return
    callback(tile, *args)


def ensure_export_worker(tile):
    worker = getattr(tile, "_export_worker", None)
    try:
        if worker is not None and worker.isRunning():
            return worker
    except Exception:
        pass
    worker = ClipExportQueueWorker(tile)
    tile_ref = weakref.ref(tile)
    worker.message.connect(lambda text, ref=tile_ref: _dispatch_tile_callback(ref, _tile_export_message, text))
    worker.busy_changed.connect(lambda busy, ref=tile_ref: _dispatch_tile_callback(ref, _tile_export_busy_changed, busy))
    worker.job_finished.connect(lambda result, ref=tile_ref: _dispatch_tile_callback(ref, _tile_export_finished, result))
    worker.job_failed.connect(lambda payload, ref=tile_ref: _dispatch_tile_callback(ref, _tile_export_failed, payload))
    worker.start()
    tile._export_worker = worker
    tile._export_job_meta = {}
    tile._export_worker_busy = False
    return worker


def stop_export_worker(tile):
    worker = getattr(tile, "_export_worker", None)
    tile._export_worker = None
    if worker is None:
        return
    try:
        worker.stop()
    except Exception:
        pass
    try:
        worker.wait(2000)
    except Exception:
        pass
