from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets


class BookmarkSlider(QtWidgets.QSlider):
    _LOCAL_SPREAD_ACTIVATION_PX = 18
    _LOCAL_SPREAD_CLUSTER_GAP_PX = 8
    _LOCAL_SPREAD_SPACING_PX = 14
    _LOCAL_SPREAD_RANGE_PADDING_PX = 10

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._bookmark_positions: tuple[int, ...] = ()
        self._selected_bookmark_positions: tuple[int, ...] = ()
        self._bookmark_length_ms = 0
        self._bookmark_visible = True
        self._bookmark_state = self._selected_state = None
        self._local_spread_active = False
        self._local_spread_hover_x: Optional[int] = None
        self._local_spread_state = None

    def set_bookmark_marks(self, positions_ms, *, length_ms: int = 0, visible: bool = True):
        normalized = tuple(sorted({max(0, int(ms)) for ms in (positions_ms or [])}))
        state = (normalized, max(0, int(length_ms)), bool(visible))
        if state == self._bookmark_state:
            return
        self._bookmark_state = state
        self._bookmark_positions = normalized
        self._bookmark_length_ms = max(0, int(length_ms))
        self._bookmark_visible = bool(visible)
        self.update()

    def clear_bookmark_marks(self):
        self.set_bookmark_marks((), length_ms=0, visible=False)

    def set_selected_bookmark_positions(self, positions_ms):
        normalized = tuple(sorted({max(0, int(ms)) for ms in (positions_ms or [])}))
        if normalized == self._selected_state:
            return
        self._selected_state = normalized
        self._selected_bookmark_positions = normalized
        self.update()

    def set_local_spread_state(self, active: bool, hover_x: Optional[int] = None):
        hover_value = int(hover_x) if hover_x is not None else None
        state = (bool(active), hover_value)
        if state == self._local_spread_state:
            return
        self._local_spread_state = state
        self._local_spread_active = bool(active)
        self._local_spread_hover_x = hover_value
        self.update()

    def _groove_rect(self) -> QtCore.QRect:
        option = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(option)
        groove = self.style().subControlRect(
            QtWidgets.QStyle.ComplexControl.CC_Slider,
            option,
            QtWidgets.QStyle.SubControl.SC_SliderGroove,
            self,
        )
        if groove.isNull() or groove.width() <= 1:
            groove = self.rect().adjusted(8, max(1, self.height() // 2 - 4), -8, -max(1, self.height() // 2 - 4))
        return groove

    def _spread_draw_positions_for_cluster(
        self,
        cluster: list[tuple[int, int, int]],
        groove: QtCore.QRect,
    ) -> Optional[list[int]]:
        spread_count = len(cluster)
        if spread_count < 2:
            return None
        cluster_center = int(round(sum(item[1] for item in cluster) / float(max(1, spread_count))))
        available_span = max(6, groove.right() - groove.left())
        max_spacing = max(1, available_span // max(1, spread_count - 1))
        spacing = max(1, min(self._LOCAL_SPREAD_SPACING_PX, int(max_spacing)))
        required_span = spacing * max(0, spread_count - 1)
        current_span = cluster[-1][1] - cluster[0][1]
        if current_span >= required_span:
            return None

        start_x = int(round(cluster_center - (required_span / 2.0)))
        draw_positions = [start_x + idx * spacing for idx in range(spread_count)]
        shift = 0
        if draw_positions[0] < groove.left():
            shift = groove.left() - draw_positions[0]
        if draw_positions[-1] + shift > groove.right():
            shift += groove.right() - (draw_positions[-1] + shift)
        return [int(x + shift) for x in draw_positions]

    def _local_spread_clusters(
        self,
        layout: list[tuple[int, int, int]],
        groove: QtCore.QRect,
    ) -> list[tuple[int, int, list[int]]]:
        clusters: list[tuple[int, int, list[int]]] = []
        idx = 0
        while idx < len(layout):
            end = idx
            while end + 1 < len(layout) and abs(layout[end + 1][1] - layout[end][1]) <= self._LOCAL_SPREAD_CLUSTER_GAP_PX:
                end += 1
            if end > idx:
                cluster = layout[idx : end + 1]
                draw_positions = self._spread_draw_positions_for_cluster(cluster, groove)
                if draw_positions:
                    clusters.append((idx, end, draw_positions))
            idx = end + 1
        return clusters

    def _base_bookmark_layout(self, groove: QtCore.QRect) -> list[tuple[int, int, int]]:
        span = max(1, groove.width() - 1)
        layout: list[tuple[int, int, int]] = []
        for ms in self._bookmark_positions:
            ratio = max(0.0, min(1.0, float(ms) / float(self._bookmark_length_ms)))
            marker_x = groove.left() + int(round(ratio * span))
            layout.append((int(ms), int(marker_x), int(marker_x)))
        return layout

    def _choose_spread_cluster(
        self,
        layout: list[tuple[int, int, int]],
        clusters: list[tuple[int, int, list[int]]],
        hover_x: int,
    ) -> Optional[tuple[int, int, list[int]]]:
        containing_clusters: list[tuple[float, int, int, list[int]]] = []
        for start_idx, end_idx, draw_positions in clusters:
            draw_start = min(int(draw_positions[0]), int(draw_positions[-1]))
            draw_end = max(int(draw_positions[0]), int(draw_positions[-1]))
            padding = max(0, int(self._LOCAL_SPREAD_RANGE_PADDING_PX))
            if draw_start - padding <= hover_x <= draw_end + padding:
                center = (draw_start + draw_end) / 2.0
                containing_clusters.append((abs(float(hover_x) - center), start_idx, end_idx, draw_positions))
        if containing_clusters:
            containing_clusters.sort(key=lambda item: item[0])
            _dist, start_idx, end_idx, draw_positions = containing_clusters[0]
            return start_idx, end_idx, draw_positions
        nearest_index = min(range(len(layout)), key=lambda idx: abs(layout[idx][1] - hover_x))
        nearest_distance = abs(layout[nearest_index][1] - hover_x)
        if nearest_distance > self._LOCAL_SPREAD_ACTIVATION_PX:
            return None
        for start_idx, end_idx, draw_positions in clusters:
            if start_idx <= nearest_index <= end_idx:
                return start_idx, end_idx, draw_positions
        return None

    def _bookmark_marker_layout(self) -> list[tuple[int, int, int]]:
        if (
            self.orientation() != QtCore.Qt.Orientation.Horizontal
            or not self._bookmark_positions
            or self._bookmark_length_ms <= 0
        ):
            return []
        groove = self._groove_rect()
        layout = self._base_bookmark_layout(groove)
        if not self._local_spread_active or self._local_spread_hover_x is None or len(layout) < 2:
            return layout
        clusters = self._local_spread_clusters(layout, groove)
        chosen_cluster = self._choose_spread_cluster(layout, clusters, int(self._local_spread_hover_x))
        if chosen_cluster is None:
            return layout
        start_idx, end_idx, draw_positions = chosen_cluster
        expanded_layout = list(layout)
        for offset, draw_x in enumerate(draw_positions):
            ms_value, actual_x, _ = layout[start_idx + offset]
            expanded_layout[start_idx + offset] = (ms_value, actual_x, int(draw_x))
        return expanded_layout

    def bookmark_positions_near_x(self, x: int, tolerance_px: int = 6) -> list[int]:
        layout = self._bookmark_marker_layout()
        if not layout:
            return []
        hits: list[int] = []
        best_distance = None
        for ms, _actual_x, draw_x in layout:
            distance = abs(int(x) - int(draw_x))
            if distance > max(2, int(tolerance_px)):
                continue
            if best_distance is None or distance < best_distance:
                hits = [ms]
                best_distance = distance
            elif distance == best_distance:
                hits.append(ms)
        return hits

    def bookmark_x_for_ms(self, position_ms: int) -> Optional[int]:
        for ms, _actual_x, draw_x in self._bookmark_marker_layout():
            if int(ms) == int(position_ms):
                return int(draw_x)
        return None

    def paintEvent(self, event: QtGui.QPaintEvent):
        super().paintEvent(event)
        layout = self._bookmark_marker_layout()
        if not layout or not self._bookmark_visible:
            return
        groove = self._groove_rect()
        top = max(self.rect().top() + 1, groove.top() - 3)
        bottom = min(self.rect().bottom() - 1, groove.bottom() + 3)

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)
        selected_positions = set(self._selected_bookmark_positions)
        for ms, actual_x, draw_x in layout:
            if draw_x != actual_x:
                guide_pen = QtGui.QPen(QtGui.QColor("#6e6e6e"))
                guide_pen.setWidth(1)
                painter.setPen(guide_pen)
                painter.drawLine(int(actual_x), groove.center().y(), int(draw_x), top)
            if ms in selected_positions:
                pen = QtGui.QPen(QtGui.QColor("#4dd9ff"))
                pen.setWidth(3)
            else:
                pen = QtGui.QPen(QtGui.QColor("#f2b233"))
                pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(int(draw_x), top, int(draw_x), bottom)
