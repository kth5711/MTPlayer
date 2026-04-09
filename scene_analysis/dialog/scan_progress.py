import time


def refresh_scan_progress_text(dialog) -> None:
    if not bool(getattr(dialog, "_scan_progress_active", False)):
        return
    started = float(getattr(dialog, "_scan_started_at", 0.0) or 0.0)
    if started <= 0.0:
        return
    elapsed = max(0, int(time.monotonic() - started))
    dialog.progress.setFormat(f"%p% | {dialog._format_elapsed_tag(elapsed)}")


def set_scan_progress_active(dialog, active: bool) -> None:
    enabled = bool(active)
    dialog._scan_progress_active = enabled
    if enabled:
        dialog._scan_started_at = float(time.monotonic())
        dialog._refresh_scan_progress_text()
        if hasattr(dialog, "_scan_elapsed_timer"):
            dialog._scan_elapsed_timer.start()
        return
    if hasattr(dialog, "_scan_elapsed_timer"):
        dialog._scan_elapsed_timer.stop()
    dialog.progress.setFormat("%p%")
    dialog._scan_started_at = 0.0
