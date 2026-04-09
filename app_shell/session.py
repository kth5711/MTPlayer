import json
import os
import tempfile
from typing import Any, Dict, Optional

from PyQt6 import QtCore


def rect_to_data(rect: Optional[QtCore.QRect]) -> Optional[Dict[str, int]]:
    if rect is None:
        return None
    try:
        return {
            "x": int(rect.x()),
            "y": int(rect.y()),
            "w": int(rect.width()),
            "h": int(rect.height()),
        }
    except Exception:
        return None


def rect_from_data(data: Any) -> Optional[QtCore.QRect]:
    if not isinstance(data, dict):
        return None
    try:
        rect = QtCore.QRect(
            int(data.get("x", 0)),
            int(data.get("y", 0)),
            int(data.get("w", 0)),
            int(data.get("h", 0)),
        )
    except Exception:
        return None
    if rect.width() <= 0 or rect.height() <= 0:
        return None
    return rect


class SessionManager:
    def __init__(self, config_path: str):
        self.config_path = config_path

    def load(self, path: Optional[str] = None) -> Dict[str, Any]:
        target_path = path or self.config_path
        try:
            if os.path.exists(target_path):
                with open(target_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as exc:
            print("설정 로드 실패:", exc)
        return {}

    def save(self, data: Dict[str, Any], path: Optional[str] = None, *, pretty: bool = True):
        target_path = path or self.config_path
        tmp_path = ""
        try:
            cfg_dir = os.path.dirname(target_path) or "."
            os.makedirs(cfg_dir, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(prefix="player_config_", suffix=".tmp", dir=cfg_dir)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(
                    data,
                    f,
                    ensure_ascii=False,
                    indent=2 if pretty else None,
                    separators=None if pretty else (",", ":"),
                )
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, target_path)
            tmp_path = ""
        except Exception as exc:
            print("설정 저장 실패:", exc)
        finally:
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
