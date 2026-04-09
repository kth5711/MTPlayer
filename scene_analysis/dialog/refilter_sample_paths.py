from typing import List
import logging
import os

from PyQt6 import QtWidgets

from scene_analysis.core.cache import _normalize_sample_paths, _normalize_sample_texts
from scene_analysis.core.similarity import _normalize_adapter_path


logger = logging.getLogger(__name__)


def sample_last_dir(dialog) -> str:
    directory = _sample_last_dir_from_config(dialog)
    if directory:
        return directory
    directory = _sample_last_dir_from_host(dialog)
    if directory:
        return directory
    directory = _sample_last_dir_from_samples(dialog)
    if directory:
        return directory
    directory = _sample_last_dir_from_current_path(dialog)
    if directory:
        return directory
    return os.path.expanduser("~")


def store_sample_last_dir(dialog, folder: str) -> None:
    directory = _normalized_existing_dir(folder)
    if not directory:
        return
    _save_sample_last_dir_to_host(dialog, directory)
    _save_sample_last_dir_to_config(dialog, directory)


def pick_ref_image(dialog) -> None:
    start_dir = dialog._sample_last_dir()
    files, _ = QtWidgets.QFileDialog.getOpenFileNames(
        dialog,
        "샘플 이미지 추가(복수 가능)",
        start_dir,
        "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
    )
    if not files:
        return
    existing = list(getattr(dialog, "sample_image_paths", []) or [])
    picked = [str(path) for path in files if str(path or "").strip()]
    dialog.sample_image_paths = _normalize_sample_paths(existing + picked)
    _store_first_sample_dir(dialog, files)
    dialog._update_ref_image_text()


def clear_ref_images(dialog) -> None:
    dialog.sample_image_paths = []
    dialog._update_ref_image_text()


def delete_selected_ref_images(dialog) -> None:
    selected = set(dialog._selected_ref_image_paths())
    if not selected:
        return
    dialog.sample_image_paths = [
        path
        for path in list(getattr(dialog, "sample_image_paths", []) or [])
        if str(path) not in selected
    ]
    dialog._update_ref_image_text()


def current_sample_texts(dialog) -> List[str]:
    text = ""
    try:
        text = str(dialog.edt_ref_text.toPlainText() or "")
    except RuntimeError:
        logger.debug("sample text extraction failed", exc_info=True)
    return _normalize_sample_texts([text])


def pick_siglip_adapter(dialog) -> None:
    start_dir = str(dialog.edt_siglip_adapter.text() or "").strip()
    picked = QtWidgets.QFileDialog.getExistingDirectory(
        dialog,
        "SigLIP2 LoRA 어댑터 폴더 선택",
        start_dir,
    )
    if picked:
        dialog.edt_siglip_adapter.setText(_normalize_adapter_path(picked))


def _sample_last_dir_from_config(dialog) -> str:
    try:
        main_window = dialog.host.window() if hasattr(dialog.host, "window") else None
    except (AttributeError, RuntimeError):
        logger.debug("sample_last_dir window lookup failed", exc_info=True)
        main_window = None
    try:
        config = getattr(main_window, "config", None)
        if isinstance(config, dict):
            directory = str(config.get("sample_last_dir") or "").strip()
            if directory and os.path.isdir(directory):
                return directory
    except (AttributeError, RuntimeError, TypeError, ValueError):
        logger.debug("sample_last_dir config lookup failed", exc_info=True)
    return ""


def _sample_last_dir_from_host(dialog) -> str:
    try:
        directory = str(getattr(dialog.host, "sample_last_dir", "") or "").strip()
        if directory and os.path.isdir(directory):
            return directory
    except (AttributeError, RuntimeError, TypeError, ValueError):
        logger.debug("sample_last_dir host lookup failed", exc_info=True)
    return ""


def _sample_last_dir_from_samples(dialog) -> str:
    paths = list(getattr(dialog, "sample_image_paths", []) or [])
    if not paths:
        return ""
    try:
        directory = os.path.dirname(os.path.abspath(str(paths[0])))
        if directory and os.path.isdir(directory):
            return directory
    except (OSError, TypeError, ValueError):
        logger.debug("sample_last_dir image-path fallback failed", exc_info=True)
    return ""


def _sample_last_dir_from_current_path(dialog) -> str:
    try:
        current_path = str(getattr(dialog, "current_path", "") or "").strip()
        if current_path:
            directory = os.path.dirname(os.path.abspath(current_path))
            if directory and os.path.isdir(directory):
                return directory
    except (OSError, TypeError, ValueError):
        logger.debug("sample_last_dir current-path fallback failed", exc_info=True)
    return ""


def _normalized_existing_dir(folder: str) -> str:
    directory = str(folder or "").strip()
    if not directory:
        return ""
    try:
        directory = os.path.abspath(directory)
    except (OSError, TypeError, ValueError):
        logger.debug("sample_last_dir absolute-path normalization failed", exc_info=True)
        return ""
    return directory if os.path.isdir(directory) else ""


def _save_sample_last_dir_to_host(dialog, directory: str) -> None:
    try:
        dialog.host.sample_last_dir = directory
    except (AttributeError, RuntimeError, TypeError):
        logger.debug("sample_last_dir host save skipped", exc_info=True)


def _save_sample_last_dir_to_config(dialog, directory: str) -> None:
    try:
        main_window = dialog.host.window() if hasattr(dialog.host, "window") else None
        config = getattr(main_window, "config", None)
        if isinstance(config, dict):
            config["sample_last_dir"] = directory
    except (AttributeError, RuntimeError, TypeError):
        logger.debug("sample_last_dir config save skipped", exc_info=True)


def _store_first_sample_dir(dialog, files) -> None:
    first_path = str(files[0] or "").strip() if files else ""
    if not first_path:
        return
    folder = os.path.dirname(first_path)
    dialog._store_sample_last_dir(folder)
