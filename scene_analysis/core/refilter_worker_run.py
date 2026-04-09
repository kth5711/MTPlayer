from __future__ import annotations

from typing import Any, Callable, List, Optional


def run_scene_similarity_impl(
    worker_cls,
    video_path: str,
    scene_ms: List[int],
    sample_image_paths: List[str],
    *,
    progress_cb: Optional[Callable[[int], None]] = None,
    message_cb: Optional[Callable[[str], None]] = None,
    cancel_cb: Optional[Callable[[], bool]] = None,
    **worker_kwargs,
) -> List[tuple[int, float]]:
    worker = worker_cls(video_path, scene_ms, sample_image_paths, **worker_kwargs)
    result: dict[str, Any] = {}
    _connect_scene_similarity_callbacks(worker, result, progress_cb, message_cb)
    _wrap_scene_similarity_cancel(worker, cancel_cb)
    worker.run()
    error = str(result.get("error") or "").strip()
    if error:
        raise RuntimeError(error)
    return [(int(ms), float(sim)) for ms, sim in (result.get("pairs") or [])]


def _connect_scene_similarity_callbacks(worker, result, progress_cb, message_cb):
    if callable(progress_cb):
        worker.progress.connect(lambda v: progress_cb(int(v)))
    if callable(message_cb):
        worker.message.connect(lambda text: message_cb(str(text or "")))
    worker.finished_ok.connect(lambda pairs: result.setdefault("pairs", list(pairs or [])))
    worker.finished_err.connect(lambda msg: result.setdefault("error", str(msg or "")))


def _wrap_scene_similarity_cancel(worker, cancel_cb):
    if not callable(cancel_cb):
        return
    orig_raise = worker._raise_if_cancelled

    def _raise_if_cancelled_with_external():
        try:
            if bool(cancel_cb()):
                worker.cancel()
        except Exception:
            pass
        orig_raise()

    worker._raise_if_cancelled = _raise_if_cancelled_with_external  # type: ignore[assignment]


__all__ = ["run_scene_similarity_impl"]
