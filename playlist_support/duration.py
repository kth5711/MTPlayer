from typing import Any, Optional

from .duration_worker import _probe_duration_ms_sync


def duration_cache_signature(main, path: str) -> tuple[int, int]:
    try:
        st = __import__("os").stat(path)
        return (int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))), int(st.st_size))
    except Exception:
        return (0, 0)


def format_duration_ms(main, ms: int) -> str:
    total_seconds = max(0, int(ms) // 1000)
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"


def probe_duration_ms(main, path: str) -> Optional[int]:
    return _probe_duration_ms_sync(path)


def on_playlist_duration_ready(main, path: str, sig: Any, duration_ms: Any):
    sig_key = _signature_key(sig)
    pending = _pending_duration_jobs(main)
    if pending.get(path) == sig_key:
        pending.pop(path, None)
    current_sig = main._duration_cache_signature(path)
    if current_sig != sig_key:
        return
    duration_value = _duration_value(duration_ms)
    duration_text = main._format_duration_ms(duration_value) if duration_value is not None else ""
    cache = _duration_cache(main)
    cached = cache.get(path)
    if cached and cached[0] == current_sig and cached[1] == duration_value and cached[2] == duration_text:
        return
    cache[path] = (current_sig, duration_value, duration_text)
    main.request_playlist_refresh(force=True, delay_ms=60)


def _signature_key(sig: Any) -> tuple[int, int]:
    try:
        return (int(sig[0]), int(sig[1]))
    except Exception:
        return (0, 0)


def _duration_value(duration_ms: Any) -> Optional[int]:
    try:
        return int(duration_ms) if duration_ms is not None else None
    except Exception:
        return None


def playlist_duration_info(main, path: str) -> tuple[Optional[int], str]:
    cache = _duration_cache(main)
    sig = main._duration_cache_signature(path)
    cached = cache.get(path)
    if cached and cached[0] == sig:
        return cached[1], cached[2]
    if _queue_duration_probe(main, path, sig):
        return None, ""
    duration_ms = main._probe_duration_ms(path)
    duration_text = main._format_duration_ms(duration_ms) if duration_ms is not None else ""
    cache[path] = (sig, duration_ms, duration_text)
    _trim_duration_cache(cache)
    return duration_ms, duration_text


def _duration_cache(main):
    cache = getattr(main, "_playlist_duration_cache", None)
    if cache is None:
        main._playlist_duration_cache = {}
        cache = main._playlist_duration_cache
    return cache


def _pending_duration_jobs(main):
    pending = getattr(main, "_playlist_duration_pending", None)
    if pending is None:
        main._playlist_duration_pending = {}
        pending = main._playlist_duration_pending
    return pending


def _queue_duration_probe(main, path: str, sig: tuple[int, int]) -> bool:
    worker = getattr(main, "_playlist_duration_worker", None)
    try:
        worker_running = bool(worker is not None and worker.isRunning())
    except Exception:
        worker_running = False
    if not worker_running:
        return False
    pending = _pending_duration_jobs(main)
    if pending.get(path) != sig:
        pending[path] = sig
        worker.add_job(path, sig)
    return True


def _trim_duration_cache(cache):
    if len(cache) <= 4096:
        return
    try:
        cache.pop(next(iter(cache)), None)
    except Exception:
        pass
