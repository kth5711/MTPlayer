from typing import List, Optional
import logging

from PyQt6 import QtCore, QtGui, QtWidgets

from scene_analysis.core.similarity import _imread_bgr


logger = logging.getLogger(__name__)


def sample_preview_pixmap(dialog, path: str, w: int = 96, h: int = 60) -> Optional[QtGui.QPixmap]:
    pixmap = QtGui.QPixmap(path or "")
    if pixmap is None or pixmap.isNull():
        pixmap = _cv2_preview_pixmap(path)
    if pixmap is None or pixmap.isNull():
        return None
    try:
        return pixmap.scaled(
            w,
            h,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
    except RuntimeError:
        logger.debug("sample preview pixmap scaling skipped", exc_info=True)
        return pixmap


def update_ref_image_text(dialog) -> None:
    paths = list(dialog.sample_image_paths or [])
    dialog.lst_ref_img.clear()
    if not paths:
        _add_empty_sample_placeholder(dialog)
        dialog._update_ref_image_actions()
        return
    for path in paths:
        dialog.lst_ref_img.addItem(_sample_list_item(dialog, path))
    dialog._update_ref_image_actions()


def selected_ref_image_paths(dialog) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in list(dialog.lst_ref_img.selectedItems() or []):
        try:
            path = str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "").strip()
        except (RuntimeError, TypeError, ValueError):
            logger.debug("selected ref image path read failed", exc_info=True)
            path = ""
        if not path or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def update_ref_image_actions(dialog) -> None:
    paths = list(getattr(dialog, "sample_image_paths", []) or [])
    selected = dialog._selected_ref_image_paths() if hasattr(dialog, "lst_ref_img") else []
    if hasattr(dialog, "btn_clear_ref"):
        dialog.btn_clear_ref.setEnabled(bool(paths) and bool(dialog.lst_ref_img.isEnabled()))
    if hasattr(dialog, "btn_remove_ref"):
        dialog.btn_remove_ref.setEnabled(bool(selected) and bool(dialog.lst_ref_img.isEnabled()))


def _cv2_preview_pixmap(path: str) -> Optional[QtGui.QPixmap]:
    image_bgr = _imread_bgr(path or "")
    if image_bgr is None:
        return None
    try:
        import cv2  # type: ignore

        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        fmt_container = getattr(QtGui.QImage, "Format", None)
        if fmt_container is not None and hasattr(fmt_container, "Format_RGB888"):
            image = QtGui.QImage(
                rgb.data,
                width,
                height,
                channels * width,
                fmt_container.Format_RGB888,
            ).copy()
        else:
            image = QtGui.QImage(
                rgb.data,
                width,
                height,
                channels * width,
                QtGui.QImage.Format_RGB888,
            ).copy()
        return QtGui.QPixmap.fromImage(image)
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        logger.debug("sample preview pixmap build from cv2 failed", exc_info=True)
        return None


def _add_empty_sample_placeholder(dialog) -> None:
    item = QtWidgets.QListWidgetItem("샘플 이미지 없음\n[샘플 추가]로 선택")
    item.setSizeHint(QtCore.QSize(132, 68))
    try:
        item_flag_container = getattr(QtCore.Qt, "ItemFlag", None)
        non_selectable = (
            item_flag_container.ItemIsSelectable
            if item_flag_container is not None
            else QtCore.Qt.ItemIsSelectable
        )
        item.setFlags(item.flags() & ~non_selectable)
    except RuntimeError:
        logger.debug("sample placeholder item flag update skipped", exc_info=True)
    dialog.lst_ref_img.addItem(item)


def _sample_list_item(dialog, path: str):
    item = QtWidgets.QListWidgetItem("")
    item.setToolTip(path)
    item.setSizeHint(QtCore.QSize(104, 68))
    item.setData(QtCore.Qt.ItemDataRole.UserRole, path)
    pixmap = dialog._sample_preview_pixmap(path, w=96, h=60)
    if pixmap is not None and not pixmap.isNull():
        item.setIcon(QtGui.QIcon(pixmap))
    else:
        item.setText("로드 실패")
    return item
