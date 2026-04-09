import os
from typing import List, Optional

from PyQt6 import QtCore, QtWidgets
import vlc

from i18n import tr

from .support import MEDIA_FILE_EXTENSIONS


def append_media_paths(tile, paths: List[str]):
    files = [path for path in paths if os.path.isfile(path)]
    if not files:
        return
    should_autoplay = not tile.playlist
    for idx, path in enumerate(files):
        tile.add_to_playlist(path, play_now=(should_autoplay and idx == 0))
    tile._notify_playlist_changed()


def collect_video_files(tile, folder: str) -> List[str]:
    files: List[str] = []
    for root, dirs, filenames in os.walk(folder, topdown=True):
        dirs.sort()
        filenames.sort()
        for name in filenames:
            if os.path.splitext(name)[1].lower() in MEDIA_FILE_EXTENSIONS:
                path = os.path.join(root, name)
                if os.path.isfile(path):
                    files.append(path)
    return files


def normalize_media_path(path: str) -> str:
    return os.path.abspath(os.path.normpath(path))


def get_external_subtitle_for_path(tile, media_path: str) -> Optional[str]:
    if not media_path:
        return None
    return tile.external_subtitles.get(tile._normalize_media_path(media_path))


def pop_external_subtitle_for_path(tile, media_path: str) -> Optional[str]:
    if not media_path:
        return None
    return tile.external_subtitles.pop(tile._normalize_media_path(media_path), None)


def set_external_subtitle_for_path(
    tile,
    media_path: str,
    subtitle_path: Optional[str],
    *,
    overwrite: bool = False,
):
    if not media_path or not subtitle_path:
        return
    key = tile._normalize_media_path(media_path)
    if overwrite or key not in tile.external_subtitles:
        tile.external_subtitles[key] = subtitle_path


def current_playlist_path(tile) -> Optional[str]:
    if tile.playlist and 0 <= tile.current_index < len(tile.playlist):
        path = tile.playlist[tile.current_index]
        if os.path.exists(path):
            return path
    return tile._current_media_path()


def open_subtitle_file(tile):
    media_path = tile._current_playlist_path()
    if not media_path:
        QtWidgets.QMessageBox.warning(tile, tr(tile, "안내"), tr(tile, "먼저 이 타일에 영상을 열어 주세요."))
        return
    start_dir = tile._dialog_start_dir()
    subtitle_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        tile,
        tr(tile, "자막 파일 선택"),
        start_dir,
        "Subtitle Files (*.srt *.ass *.ssa *.vtt *.sub *.smi *.txt);;All Files (*)",
    )
    if not subtitle_path:
        return
    tile._remember_dialog_dir(os.path.dirname(subtitle_path))
    tile.external_subtitles[tile._normalize_media_path(media_path)] = subtitle_path
    applied = tile._apply_external_subtitle_to_player(subtitle_path)
    tile.refresh_track_menus()
    if not applied:
        QtWidgets.QMessageBox.information(
            tile,
            tr(tile, "안내"),
            tr(tile, "자막 파일을 저장했습니다. 같은 영상을 다시 재생할 때 자동 적용됩니다."),
        )


def apply_external_subtitle_to_player(tile, subtitle_path: str) -> bool:
    subtitle_path = os.path.abspath(subtitle_path)
    if not os.path.isfile(subtitle_path):
        return False
    try:
        result = tile.mediaplayer.video_set_subtitle_file(subtitle_path)
        if result in (0, None):
            return True
    except Exception:
        pass
    try:
        slave_type = getattr(getattr(vlc, "MediaSlaveType", None), "subtitle", 1)
        subtitle_uri = QtCore.QUrl.fromLocalFile(subtitle_path).toString()
        result = tile.mediaplayer.add_slave(slave_type, subtitle_uri, True)
        if result in (0, None, True):
            return True
    except Exception:
        pass
    return False


def apply_saved_subtitle_option(tile, media, media_path: str):
    if media is None or not media_path:
        return
    subtitle_path = tile.external_subtitles.get(tile._normalize_media_path(media_path))
    if not subtitle_path or not os.path.isfile(subtitle_path):
        return
    try:
        media.add_option(f":sub-file={subtitle_path}")
    except Exception:
        pass


def add_to_playlist(tile, path: str, play_now: bool = False):
    added = False
    if path not in tile.playlist:
        tile.playlist.append(path)
        added = True
    if play_now:
        if not tile.set_media(path):
            if added:
                try:
                    tile.playlist.remove(path)
                except ValueError:
                    pass
            tile._update_add_button()
            return False
        tile.current_index = tile.playlist.index(path)
        tile.play()
    tile._update_add_button()
    return True


def prepend_files_to_playlist_and_play(tile, files: List[str]) -> bool:
    ordered_files: List[str] = []
    seen = set()
    for path in files:
        if not path or path in seen:
            continue
        seen.add(path)
        ordered_files.append(path)
    if not ordered_files:
        return False

    existing_playlist = [path for path in tile.playlist if path not in seen]
    tile.playlist = ordered_files + existing_playlist
    play_path = ordered_files[0]
    tile.current_index = tile.playlist.index(play_path)
    if not tile.set_media(play_path):
        return False
    tile.play()
    tile._update_add_button()
    tile._notify_playlist_changed()
    return True
