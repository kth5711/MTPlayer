from __future__ import annotations

import sys
from pathlib import Path

from PyQt6 import QtWidgets


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app_shell.app_icon import multi_play_app_icon


def main() -> int:
    output_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else SCRIPT_DIR / "MultiPlay.ico"
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    icon = multi_play_app_icon()
    pixmap = icon.pixmap(256, 256)
    if pixmap.isNull():
        raise RuntimeError("Failed to render application icon pixmap.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(output_path), "ICO"):
        raise RuntimeError(f"Failed to write icon file: {output_path}")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
