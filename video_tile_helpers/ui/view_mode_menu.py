from PyQt6 import QtGui

from i18n import tr


def add_display_mode_menu(tile, menu):
    _add_mode_menu(
        tile,
        menu,
        title=tr(
            tile,
            "영상 출력 비율: {label}",
            label=tr(tile, tile.DISPLAY_MODE_LABELS.get(getattr(tile, "display_mode", "fit"), "최적화")),
        ),
        modes=tile.DISPLAY_MODES,
        current_mode=getattr(tile, "display_mode", "fit"),
        labels=tile.DISPLAY_MODE_LABELS,
        tooltips=tile.DISPLAY_MODE_TOOLTIPS,
        handler=tile.set_display_mode,
    )


def add_transform_mode_menu(tile, menu):
    _add_mode_menu(
        tile,
        menu,
        title=tr(
            tile,
            "영상 방향: {label}",
            label=tr(tile, tile.TRANSFORM_MODE_LABELS.get(getattr(tile, "transform_mode", "none"), "정방향")),
        ),
        modes=tile.TRANSFORM_MODES,
        current_mode=getattr(tile, "transform_mode", "none"),
        labels=tile.TRANSFORM_MODE_LABELS,
        tooltips=tile.TRANSFORM_MODE_TOOLTIPS,
        handler=tile.set_transform_mode,
    )


def _add_mode_menu(tile, menu, *, title, modes, current_mode, labels, tooltips, handler):
    submenu = menu.addMenu(title)
    group = QtGui.QActionGroup(submenu)
    group.setExclusive(True)
    for mode in modes:
        action = submenu.addAction(tr(tile, labels.get(mode, mode)))
        action.setCheckable(True)
        action.setChecked(mode == current_mode)
        action.setToolTip(tr(tile, tooltips.get(mode, "")))
        action.triggered.connect(lambda _checked=False, m=mode: handler(m))
        group.addAction(action)
