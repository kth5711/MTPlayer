import os

from PyQt6 import QtWidgets

from i18n import tr


def fit_media_size_from_context(tile):
    canvas = tile._canvas_host()
    if canvas is None or not hasattr(canvas, "fit_tile_window_to_media"):
        return
    if tile.current_media_pixel_size() is None:
        QtWidgets.QMessageBox.information(tile, tr(tile, "영상 크기 맞춤"), tr(tile, "현재 미디어 크기를 아직 확인하지 못했습니다."))
        return
    if not bool(canvas.fit_tile_window_to_media(tile)):
        QtWidgets.QMessageBox.information(tile, tr(tile, "영상 크기 맞춤"), tr(tile, "현재 미디어 크기에 맞출 수 없습니다."))


def trigger_mute_selected_tiles(tile):
    mainwin = tile._main_window()
    if mainwin is None or not hasattr(mainwin, "mute_selected_tiles"):
        return
    try:
        mainwin.mute_selected_tiles(None)
    except Exception:
        pass


def add_bookmark(tile):
    mainwin = tile._main_window()
    if mainwin is None or not hasattr(mainwin, "add_bookmark_from_tile"):
        return
    try:
        mainwin.add_bookmark_from_tile(tile)
    except Exception:
        pass


def open_url_stream_from_context(tile):
    mainwin = tile._main_window()
    if mainwin is None or not hasattr(mainwin, "_open_url_stream_into_tile"):
        return
    default_url = getattr(mainwin, "_last_stream_url", "") or ""
    text, ok = QtWidgets.QInputDialog.getText(
        tile,
        tr(tile, "URL/스트림 열기"),
        tr(tile, "URL 또는 스트림 주소를 입력하세요:"),
        QtWidgets.QLineEdit.EchoMode.Normal,
        default_url,
    )
    if not ok:
        return
    source = mainwin._normalize_url_stream_input(text) if hasattr(mainwin, "_normalize_url_stream_input") else str(text or "").strip()
    if not source:
        QtWidgets.QMessageBox.information(tile, tr(tile, "URL/스트림 열기"), tr(tile, "주소를 입력하세요."))
        return
    if mainwin._open_url_stream_into_tile(tile, source):
        mainwin._last_stream_url = source
        if hasattr(mainwin, "_push_recent_media"):
            mainwin._push_recent_media(source, kind="url")


def dialog_start_dir(tile) -> str:
    mainwin = tile._main_window()
    if mainwin is not None:
        return mainwin.config.get("last_dir", "") or os.path.expanduser("~")
    return os.path.expanduser("~")


def remember_dialog_dir(tile, path: str):
    if not path:
        return
    mainwin = tile._main_window()
    if mainwin is None:
        return
    mainwin.config["last_dir"] = path
    if hasattr(mainwin, "last_dir"):
        mainwin.last_dir = path


def jump_to_timecode_from_context(tile):
    if not _tile_has_seekable_media(tile):
        QtWidgets.QMessageBox.information(
            tile,
            tr(tile, "타임코드 이동"),
            tr(tile, "먼저 이 타일에 재생 중인 미디어를 열어 주세요."),
        )
        return
    default_value = _format_timecode_input(int(tile.current_playback_ms()))
    text, ok = QtWidgets.QInputDialog.getText(
        tile,
        tr(tile, "타임코드 이동"),
        tr(tile, "이동할 시간을 입력하세요 (HH:MM:SS 또는 MM:SS.mmm):"),
        QtWidgets.QLineEdit.EchoMode.Normal,
        default_value,
    )
    if not ok:
        return
    try:
        target_ms = _parse_timecode_ms(text)
    except ValueError:
        QtWidgets.QMessageBox.warning(
            tile,
            tr(tile, "타임코드 이동"),
            tr(tile, "잘못된 시간 형식입니다.\n예: 01:23 / 00:01:23 / 00:01:23.450"),
        )
        return
    try:
        was_playing = bool(tile.mediaplayer.is_playing())
    except Exception:
        was_playing = False
    tile.seek_ms(int(target_ms), play=was_playing, show_overlay=True)


def sync_other_tiles_to_this_timecode(tile):
    if not _tile_has_seekable_media(tile):
        QtWidgets.QMessageBox.information(
            tile,
            tr(tile, "이 타일 기준 전체 동기화"),
            tr(tile, "먼저 이 타일에 재생 중인 미디어를 열어 주세요."),
        )
        return
    canvas = tile._canvas_host()
    if canvas is None:
        return
    try:
        source_ms = int(tile.current_playback_ms())
    except Exception:
        source_ms = 0
    try:
        source_playing = bool(tile.mediaplayer.is_playing())
    except Exception:
        source_playing = False
    source_rate = float(getattr(tile, "playback_rate", 1.0) or 1.0)
    synced = 0
    for other in list(getattr(canvas, "tiles", []) or []):
        if other is tile or not _tile_has_seekable_media(other):
            continue
        _apply_tile_playback_rate(other, source_rate)
        try:
            other.seek_ms(int(source_ms), play=source_playing, show_overlay=False)
            synced += 1
        except Exception:
            continue
    if synced <= 0:
        QtWidgets.QMessageBox.information(
            tile,
            tr(tile, "이 타일 기준 전체 동기화"),
            tr(tile, "동기화할 다른 미디어 타일이 없습니다."),
        )
        return
    show_overlay = getattr(tile, "_show_status_overlay", None)
    if callable(show_overlay):
        show_overlay(tr(tile, "전체 동기화: {count}개", count=synced), timeout_ms=1400)


def open_focus_review_from_context(tile):
    if not _tile_has_local_video_file(tile):
        QtWidgets.QMessageBox.information(
            tile,
            tr(tile, "포커스 검토"),
            tr(tile, "로컬 영상 파일에서만 포커스 검토를 사용할 수 있습니다."),
        )
        return
    window = getattr(tile, "_focus_review_window", None)
    if window is not None:
        try:
            window.refresh_snapshot_from_tile()
            window.show()
            window.raise_()
            window.activateWindow()
            return
        except RuntimeError:
            tile._focus_review_window = None
    from canvas_support.focus_review_window import FocusReviewWindow

    window = FocusReviewWindow(tile)
    tile._focus_review_window = window
    window.destroyed.connect(lambda *_args, target=tile: setattr(target, "_focus_review_window", None))
    window.show()
    window.raise_()
    window.activateWindow()


def _tile_has_seekable_media(tile) -> bool:
    if bool(getattr(tile, "is_static_image", lambda: False)()):
        return False
    try:
        if tile.mediaplayer.get_media() is not None:
            return True
    except Exception:
        pass
    return bool(getattr(tile, "playlist", None))


def _tile_has_local_video_file(tile) -> bool:
    if not _tile_has_seekable_media(tile):
        return False
    try:
        path = str(tile._current_playlist_path() or "").strip()
    except Exception:
        return False
    return bool(path) and os.path.isfile(path)


def _format_timecode_input(ms: int) -> str:
    total_ms = max(0, int(ms))
    total_seconds, millis = divmod(total_ms, 1000)
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    base = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    if millis <= 0:
        return base
    return f"{base}.{millis:03d}"


def _parse_timecode_ms(text: str) -> int:
    raw = str(text or "").strip().replace(",", ".")
    if not raw:
        raise ValueError("empty")
    if ":" not in raw:
        seconds_value = float(raw)
        if seconds_value < 0:
            raise ValueError("negative")
        return int(round(seconds_value * 1000.0))
    parts = raw.split(":")
    if len(parts) > 3:
        raise ValueError("too many parts")
    try:
        seconds_value = float(parts[-1])
        minutes_value = int(parts[-2]) if len(parts) >= 2 else 0
        hours_value = int(parts[-3]) if len(parts) >= 3 else 0
    except Exception as exc:
        raise ValueError("invalid") from exc
    if min(seconds_value, float(minutes_value), float(hours_value)) < 0:
        raise ValueError("negative")
    total_ms = int(round((hours_value * 3600.0 + minutes_value * 60.0 + seconds_value) * 1000.0))
    return max(0, total_ms)


def _apply_tile_playback_rate(tile, rate: float) -> None:
    normalized = max(0.1, min(8.0, float(rate or 1.0)))
    tile.playback_rate = normalized
    try:
        tile.mediaplayer.set_rate(normalized)
    except Exception:
        pass
    label = getattr(tile, "lbl_rate", None)
    if label is not None:
        label.setText(tr(tile, "배속: {rate:.1f}x", rate=normalized))
        label.setStyleSheet("color: red; font-weight: bold;" if abs(normalized - 1.0) > 1e-6 else "")
