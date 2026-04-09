from PyQt6 import QtCore, QtGui


_APP_ICON: QtGui.QIcon | None = None


def multi_play_app_icon() -> QtGui.QIcon:
    global _APP_ICON
    if _APP_ICON is None:
        _APP_ICON = _build_multi_play_app_icon()
    return _APP_ICON


def _build_multi_play_app_icon() -> QtGui.QIcon:
    icon = QtGui.QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256):
        icon.addPixmap(_draw_icon_pixmap(size))
    return icon


def _draw_icon_pixmap(size: int) -> QtGui.QPixmap:
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)

    frame_inset = max(0.5, size * 0.03)
    rect = QtCore.QRectF(frame_inset, frame_inset, size - frame_inset * 2.0, size - frame_inset * 2.0)
    radius = max(4.0, size * 0.2)

    bg = QtGui.QLinearGradient(rect.topLeft(), rect.bottomRight())
    bg.setColorAt(0.0, QtGui.QColor("#11172c"))
    bg.setColorAt(0.5, QtGui.QColor("#0c1020"))
    bg.setColorAt(1.0, QtGui.QColor("#070b16"))
    painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 24), max(1.0, size * 0.022)))
    painter.setBrush(QtGui.QBrush(bg))
    painter.drawRoundedRect(rect, radius, radius)

    highlight_rect = QtCore.QRectF(
        rect.left() + size * 0.08,
        rect.top() + size * 0.06,
        rect.width() * 0.84,
        rect.height() * 0.38,
    )
    highlight = QtGui.QRadialGradient(highlight_rect.center(), highlight_rect.width() * 0.62)
    highlight.setColorAt(0.0, QtGui.QColor(72, 88, 170, 36))
    highlight.setColorAt(1.0, QtGui.QColor(72, 88, 170, 0))
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(QtGui.QBrush(highlight))
    painter.drawEllipse(highlight_rect)

    grid_inset_x = max(1.5, size * 0.12)
    grid_inset_top = max(1.5, size * 0.14)
    grid_inset_bottom = max(1.5, size * 0.145)
    grid_gap = max(1.0, size * 0.024)
    usable_w = max(1.0, rect.width() - grid_inset_x * 2.0 - grid_gap)
    usable_h = max(1.0, rect.height() - grid_inset_top - grid_inset_bottom - grid_gap)
    tile_w = usable_w / 2.0
    tile_h = usable_h / 2.0
    tile_radius = max(2.5, size * 0.075)
    grid_left = rect.left() + grid_inset_x
    grid_top = rect.top() + grid_inset_top
    tile_positions = (
        QtCore.QPointF(grid_left, grid_top),
        QtCore.QPointF(grid_left + tile_w + grid_gap, grid_top),
        QtCore.QPointF(grid_left, grid_top + tile_h + grid_gap),
        QtCore.QPointF(grid_left + tile_w + grid_gap, grid_top + tile_h + grid_gap),
    )
    tile_gradients = (
        ("#12284f", "#0d1630", "#5cb4ff"),
        ("#31124e", "#180f34", "#e177ff"),
        ("#10234b", "#10162e", "#4b8fff"),
        ("#28134a", "#150f35", "#8d57ff"),
    )
    for point, colors in zip(tile_positions, tile_gradients):
        tile_rect = QtCore.QRectF(point.x(), point.y(), tile_w, tile_h)
        tile_bg = QtGui.QLinearGradient(tile_rect.topLeft(), tile_rect.bottomRight())
        tile_bg.setColorAt(0.0, QtGui.QColor(colors[0]))
        tile_bg.setColorAt(1.0, QtGui.QColor(colors[1]))
        painter.setPen(QtGui.QPen(QtGui.QColor(colors[2]), max(1.0, size * 0.014)))
        painter.setBrush(QtGui.QBrush(tile_bg))
        painter.drawRoundedRect(tile_rect, tile_radius, tile_radius)

    center_x = rect.center().x()
    center_y = rect.center().y()
    ring_radius = size * 0.21
    glow_radius = ring_radius * 1.34
    glow = QtGui.QRadialGradient(QtCore.QPointF(center_x, center_y), glow_radius)
    glow.setColorAt(0.0, QtGui.QColor(108, 150, 255, 54))
    glow.setColorAt(0.45, QtGui.QColor(176, 89, 255, 38))
    glow.setColorAt(1.0, QtGui.QColor(176, 89, 255, 0))
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(QtGui.QBrush(glow))
    painter.drawEllipse(QtCore.QPointF(center_x, center_y), glow_radius, glow_radius)

    ring_pen = QtGui.QPen()
    ring_pen.setWidthF(max(1.0, size * 0.032))
    ring_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    ring_pen.setBrush(QtGui.QBrush(QtGui.QColor(34, 42, 82, 200)))
    painter.setPen(ring_pen)
    painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QtCore.QPointF(center_x, center_y), ring_radius, ring_radius)

    neon_ring = QtGui.QConicalGradient(QtCore.QPointF(center_x, center_y), -40.0)
    neon_ring.setColorAt(0.00, QtGui.QColor("#7e5bff"))
    neon_ring.setColorAt(0.20, QtGui.QColor("#f18dff"))
    neon_ring.setColorAt(0.48, QtGui.QColor("#a461ff"))
    neon_ring.setColorAt(0.72, QtGui.QColor("#5db6ff"))
    neon_ring.setColorAt(1.00, QtGui.QColor("#7e5bff"))
    ring_pen.setBrush(QtGui.QBrush(neon_ring))
    ring_pen.setWidthF(max(1.0, size * 0.026))
    painter.setPen(ring_pen)
    painter.drawEllipse(QtCore.QPointF(center_x, center_y), ring_radius, ring_radius)

    inner_disc = QtCore.QRectF(
        center_x - ring_radius * 0.78,
        center_y - ring_radius * 0.78,
        ring_radius * 1.56,
        ring_radius * 1.56,
    )
    disc_fill = QtGui.QRadialGradient(inner_disc.center(), ring_radius * 0.98)
    disc_fill.setColorAt(0.0, QtGui.QColor("#1a2040"))
    disc_fill.setColorAt(1.0, QtGui.QColor("#0a0d18"))
    painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 18), max(1.0, size * 0.012)))
    painter.setBrush(QtGui.QBrush(disc_fill))
    painter.drawEllipse(inner_disc)

    play_w = ring_radius * 0.92
    play_h = ring_radius * 0.98
    left = center_x - play_w * 0.3
    top = center_y - play_h * 0.5
    play_path = QtGui.QPainterPath()
    play_path.moveTo(left, top)
    play_path.lineTo(left, top + play_h)
    play_path.lineTo(left + play_w, top + play_h * 0.5)
    play_path.closeSubpath()
    play_fill = QtGui.QLinearGradient(QtCore.QPointF(left, top), QtCore.QPointF(left + play_w, top + play_h))
    play_fill.setColorAt(0.0, QtGui.QColor("#ffffff"))
    play_fill.setColorAt(0.7, QtGui.QColor("#f5f6ff"))
    play_fill.setColorAt(1.0, QtGui.QColor("#d7e6ff"))
    painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 235), max(1.0, size * 0.016)))
    painter.setBrush(QtGui.QBrush(play_fill))
    painter.drawPath(play_path)

    beam_rect = QtCore.QRectF(
        rect.left() + size * 0.18,
        rect.bottom() - size * 0.13,
        rect.width() * 0.64,
        max(2.0, size * 0.03),
    )
    beam = QtGui.QLinearGradient(beam_rect.topLeft(), beam_rect.topRight())
    beam.setColorAt(0.0, QtGui.QColor(79, 124, 255, 0))
    beam.setColorAt(0.25, QtGui.QColor(79, 124, 255, 180))
    beam.setColorAt(0.5, QtGui.QColor(171, 92, 255, 220))
    beam.setColorAt(0.75, QtGui.QColor(120, 84, 255, 180))
    beam.setColorAt(1.0, QtGui.QColor(120, 84, 255, 0))
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(QtGui.QBrush(beam))
    painter.drawRoundedRect(beam_rect, beam_rect.height() * 0.5, beam_rect.height() * 0.5)

    painter.end()
    return pixmap
