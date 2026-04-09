import os
import subprocess
import sys

from PyQt6 import QtCore, QtWidgets

from i18n import tr
from video_tile_helpers.support import MEDIA_FILE_EXTENSIONS, media_file_dialog_filter


def tile_idx_from_selection(main):
    items = main.playlist_widget.selectedItems()
    if not items:
        tiles = main.canvas.get_selected_tiles()
        return main.canvas.tiles.index(tiles[0]) if tiles else 0
    for item in items:
        meta = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(meta, dict) and meta.get("type") in {"file", "bookmark"}:
            return int(meta["tile_idx"])
    meta = items[0].data(0, QtCore.Qt.ItemDataRole.UserRole)
    return int(meta["tile_idx"]) if isinstance(meta, dict) and meta.get("type") == "tile" else 0


def on_playlist_context_menu(main, pos):
    tree = main.playlist_widget
    _sync_context_menu_selection(tree, pos)
    menu, actions = _build_playlist_context_menu(main)
    _apply_playlist_context_action_state(tree.selectedItems(), actions)
    selected = menu.exec(tree.mapToGlobal(pos))
    _run_playlist_context_action(main, selected, actions)


def _sync_context_menu_selection(tree, pos):
    item = tree.itemAt(pos)
    if item is not None and not item.isSelected():
        tree.clearSelection()
        item.setSelected(True)
        tree.setCurrentItem(item)


def _build_playlist_context_menu(main):
    menu = QtWidgets.QMenu(main)
    actions = {
        "open": menu.addAction(tr(main, "파일 열기")),
        "folder": menu.addAction(tr(main, "폴더 열기")),
    }
    menu.addSeparator()
    actions["delete"] = menu.addAction(tr(main, "리스트삭제"))
    actions["trash"] = menu.addAction(tr(main, "휴지통으로"))
    menu.addSeparator()
    actions["explorer"] = menu.addAction(tr(main, "폴더 열기(경로)"))
    return menu, actions


def _apply_playlist_context_action_state(items, actions):
    has_file = _selected_meta_type(items, {"file"})
    has_path_item = _selected_meta_type(items, {"file", "bookmark"})
    if not has_path_item:
        actions["delete"].setEnabled(False)
    if not has_file:
        actions["delete"].setEnabled(False)
        actions["trash"].setEnabled(False)
    if not has_path_item:
        actions["explorer"].setEnabled(False)


def _selected_meta_type(items, kinds: set[str]) -> bool:
    for item in items:
        meta = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(meta, dict) and meta.get("type") in kinds:
            return True
    return False


def _run_playlist_context_action(main, selected, actions):
    if selected is None:
        return
    if selected is actions["open"]:
        main._pl_open_files_into_tile()
    elif selected is actions["folder"]:
        main._pl_open_folder_into_tile()
    elif selected is actions["delete"]:
        main._pl_delete_selected(trash=False)
    elif selected is actions["trash"]:
        main._pl_delete_selected(trash=True)
    elif selected is actions["explorer"]:
        main._pl_open_selected_in_explorer()


def pl_open_files_into_tile(main):
    tile_index = main._tile_idx_from_selection()
    start_dir = main.config.get("last_dir", "") or ""
    paths, _ = QtWidgets.QFileDialog.getOpenFileNames(main, tr(main, "영상 열기"), start_dir, media_file_dialog_filter())
    if not paths:
        return
    main.config["last_dir"] = os.path.dirname(paths[0])
    if hasattr(main, "_push_recent_media_many"):
        main._push_recent_media_many(paths, kind="path")
    _append_paths_to_tile_playlist(main.canvas.tiles[tile_index], paths)
    main.update_playlist()


def _append_paths_to_tile_playlist(tile, paths):
    for path in paths:
        try:
            tile.add_to_playlist(path, play_now=False)
        except Exception:
            pass


def pl_open_folder_into_tile(main):
    tile_index = main._tile_idx_from_selection()
    start_dir = main.config.get("last_dir", "") or ""
    folder = QtWidgets.QFileDialog.getExistingDirectory(main, tr(main, "폴더 열기"), start_dir)
    if not folder:
        return
    main.config["last_dir"] = folder
    files = _sorted_media_files_in_folder(folder)
    if not files:
        return
    _append_paths_to_tile_playlist(main.canvas.tiles[tile_index], files)
    main.update_playlist()


def _sorted_media_files_in_folder(folder: str):
    files = [os.path.join(folder, name) for name in os.listdir(folder) if os.path.splitext(name)[1].lower() in MEDIA_FILE_EXTENSIONS]
    files.sort()
    return files


def pl_open_selected_in_explorer(main):
    for item in main.playlist_widget.selectedItems():
        meta = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(meta, dict) and meta.get("type") in {"file", "bookmark"}:
            _open_path_in_explorer(os.path.abspath(meta["path"]))
            return


def _open_path_in_explorer(path: str):
    path = os.path.normpath(os.path.abspath(str(path or "")))
    folder = os.path.dirname(path)
    try:
        if sys.platform.startswith("win"):
            if os.path.isfile(path):
                if _run_windows_explorer_select(path):
                    return
                if folder and os.path.isdir(folder):
                    os.startfile(folder)
            elif os.path.isdir(path):
                os.startfile(path)
            elif folder and os.path.isdir(folder):
                os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.run(["open", "-R", path], check=False) if os.path.exists(path) else subprocess.run(["open", folder], check=False)
        elif folder:
            subprocess.run(["xdg-open", folder], check=False)
    except Exception:
        pass


def _run_windows_explorer_select(path: str) -> bool:
    try:
        proc = subprocess.run(["explorer.exe", "/select,", path], check=False)
        return int(getattr(proc, "returncode", 1) or 0) == 0
    except Exception:
        return False
