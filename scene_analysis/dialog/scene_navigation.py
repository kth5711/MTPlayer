import logging

from PyQt6 import QtCore

from .preview_items import SCENE_ROLE_GROUP_START_MS


logger = logging.getLogger(__name__)


def go_current(dialog) -> None:
    item = dialog.listw.currentItem()
    if not item:
        return
    timestamp_ms = _scene_anchor_ms(item)
    try:
        back = int(dialog.spn_back.value())
    except (AttributeError, RuntimeError, TypeError, ValueError):
        logger.debug("go_current back-step read failed", exc_info=True)
        back = 500
    seek_to = max(timestamp_ms - back, 0)

    try:
        is_playing = False
        if hasattr(dialog.host, "mediaplayer") and hasattr(dialog.host.mediaplayer, "is_playing"):
            is_playing = dialog.host.mediaplayer.is_playing()
        dialog.host.seek_ms(seek_to, play=is_playing)
    except Exception:
        logger.warning("go_current precise seek failed; retrying play=True fallback", exc_info=True)
        dialog.host.seek_ms(seek_to, play=True)


def _scene_anchor_ms(item) -> int:
    try:
        start_ms = int(item.data(SCENE_ROLE_GROUP_START_MS) or -1)
        if start_ms >= 0:
            return start_ms
        return int(item.data(QtCore.Qt.ItemDataRole.UserRole) or 0)
    except Exception:
        return 0
