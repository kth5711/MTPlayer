from typing import Dict
from PyQt6 import QtCore, QtGui, QtWidgets

class KeyCaptureEdit(QtWidgets.QLineEdit):
    """키 시퀀스 캡처용. 눌린 조합을 'Ctrl+Shift+A' 형태로 기록."""
    sequenceChanged = QtCore.pyqtSignal(str)

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        mods = []
        m = e.modifiers()
        if m & QtCore.Qt.KeyboardModifier.ControlModifier: mods.append("Ctrl")
        if m & QtCore.Qt.KeyboardModifier.ShiftModifier: mods.append("Shift")
        if m & QtCore.Qt.KeyboardModifier.AltModifier: mods.append("Alt")
        if m & QtCore.Qt.KeyboardModifier.MetaModifier: mods.append("Meta")
        is_keypad = bool(m & QtCore.Qt.KeyboardModifier.KeypadModifier)

        key = e.key()
        # 필터링(Shift 자체 같은 Mod 키는 제외)
        if key in (QtCore.Qt.Key.Key_Control, QtCore.Qt.Key.Key_Shift,
                   QtCore.Qt.Key.Key_Alt, QtCore.Qt.Key.Key_Meta):
            combo = "+".join(mods) if mods else ""
        else:
            kmin = int(QtCore.Qt.Key.Key_0)
            kmax = int(QtCore.Qt.Key.Key_9)
            ikey = int(key)
            if kmin <= ikey <= kmax:
                digit = str(ikey - kmin)
                keyname = f"Num{digit}" if is_keypad else digit
            else:
                keyname = QtGui.QKeySequence(key).toString()
                if is_keypad and len(keyname) == 1 and keyname.isdigit():
                    keyname = f"Num{keyname}"
            combo = "+".join(mods + [keyname]) if keyname else "+".join(mods)

        self.setText(combo)
        self.sequenceChanged.emit(combo)

class ShortcutDialog(QtWidgets.QDialog):
    """단축키 테이블 편집(키 캡처)"""
    DEFAULTS: Dict[str, str] = {
        "재생/일시정지": "Space",
        "다음 영상": "Right",
        "이전 영상": "Left",
        "10초 앞으로": "Shift+Right",
        "10초 뒤로": "Shift+Left",
        "1초 앞으로": "Ctrl+Right",
        "1초 뒤로": "Ctrl+Left",
        "영상 열기": "O",
        "영상 새 타일로 열기": "Ctrl+O",
        "폴더 열기": "P",
        "플레이리스트 창 토글": "L",
        "책갈피 창 토글": "B",
        "영상만 보기": "Ctrl+H",
        "볼륨 증가": "Up",
        "볼륨 감소": "Down",
        "음소거": "M",
        "선택 타일 음소거": "Ctrl+M",
        "타일 전체선택/해제": "`",
        "배속 증가": "]",
        "배속 감소": "[",
        "구간 A~B 토글": "A",
        "반복 재생 토글": "Shift+R",
        "영상 출력 비율 토글": "D",
        "클립 생성": "C",
        "GIF 생성": "G"
    }
    for n in range(1, 10):
        DEFAULTS[f"화면 전환 {n}"] = f"Num{n}"
        DEFAULTS[f"화면 선택 {n}"] = str(n)
        DEFAULTS[f"화면 다중선택 {n}"] = f"Ctrl+{n}"

    def __init__(self, current: Dict[str, str] | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("단축키 설정")
        self.resize(560, 520)
        self._map = dict(self.DEFAULTS)
        if current: self._map.update(current)

        v = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["기능", "키"])
        self.table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self.table)

        rows = sorted(self._map.items(), key=lambda x: x[0])
        self.table.setRowCount(len(rows))
        for r, (name, key) in enumerate(rows):
            it0 = QtWidgets.QTableWidgetItem(name)
            it0.setFlags(it0.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            edit = KeyCaptureEdit(); edit.setText(key)
            self.table.setItem(r, 0, it0)
            self.table.setCellWidget(r, 1, edit)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Save |
                                          QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def get_shortcuts(self) -> Dict[str, str]:
        out = {}
        for r in range(self.table.rowCount()):
            name = self.table.item(r, 0).text()
            edit = self.table.cellWidget(r, 1)
            key = edit.text().strip()
            out[name] = key
        return out
