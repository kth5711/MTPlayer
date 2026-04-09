import sys, os, shutil
from typing import List

# 실행 리소스 경로 (PyInstaller 빌드 후에는 sys._MEIPASS, 개발 중에는 프로젝트 루트)
if getattr(sys, 'frozen', False):
    RESOURCE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    RESOURCE_DIR = APP_DIR

# 기존 코드 호환용
BASE_DIR = RESOURCE_DIR
APP_NAME = "Multi-Play"


def _portable_root_dir() -> str:
    override = str(os.environ.get("MULTIPLAY_PORTABLE_ROOT", "") or "").strip()
    if override:
        return os.path.abspath(override)
    for marker_name in ("portable.mode", ".portable"):
        marker_path = os.path.join(APP_DIR, marker_name)
        if os.path.exists(marker_path):
            return APP_DIR
    return ""


def _user_data_dir() -> str:
    portable_root = _portable_root_dir()
    if portable_root:
        return os.path.join(portable_root, "config")
    if sys.platform == "win32":
        base = (
            os.environ.get("APPDATA")
            or os.environ.get("LOCALAPPDATA")
            or os.path.expanduser("~")
        )
        return os.path.join(base, APP_NAME)
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, APP_NAME)


def _legacy_config_candidates() -> List[str]:
    candidates = []
    for root in (APP_DIR, RESOURCE_DIR):
        if not root:
            continue
        path = os.path.join(root, "player_config.json")
        if path not in candidates:
            candidates.append(path)
    return candidates


def _migrate_legacy_config(target_path: str) -> None:
    if os.path.exists(target_path):
        return
    for legacy_path in _legacy_config_candidates():
        if legacy_path == target_path or not os.path.exists(legacy_path):
            continue
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy2(legacy_path, target_path)
            return
        except Exception:
            continue


def _prepend_env_path(path_value: str) -> None:
    path_text = str(path_value or "").strip()
    if not path_text or not os.path.isdir(path_text):
        return
    current = os.environ.get("PATH", "")
    parts = [part for part in current.split(os.pathsep) if part]
    norm_target = os.path.normcase(os.path.normpath(path_text))
    filtered = []
    for part in parts:
        try:
            norm_part = os.path.normcase(os.path.normpath(part))
        except Exception:
            norm_part = str(part or "")
        if norm_part == norm_target:
            continue
        filtered.append(part)
    os.environ["PATH"] = path_text + (os.pathsep + os.pathsep.join(filtered) if filtered else "")


def _default_vlc_runtime_dirs() -> List[str]:
    candidates = [
        os.path.join(RESOURCE_DIR, "vlc"),
        os.path.join(RESOURCE_DIR, "VideoLAN", "VLC"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "VideoLAN", "VLC"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "VideoLAN", "VLC"),
    ]
    out: List[str] = []
    seen = set()
    for path in candidates:
        norm = os.path.normcase(os.path.normpath(str(path or "").strip()))
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(path)
    return out


def _add_vlc_to_path():
    for vlc_dir in _default_vlc_runtime_dirs():
        if not os.path.isdir(vlc_dir):
            continue
        _prepend_env_path(vlc_dir)
        plugin_dir = os.path.join(vlc_dir, "plugins")
        if os.path.isdir(plugin_dir):
            os.environ.setdefault("VLC_PLUGIN_PATH", plugin_dir)
            break

_add_vlc_to_path()

def _default_config_path() -> str:
    path = os.path.join(_user_data_dir(), "player_config.json")
    _migrate_legacy_config(path)
    return path
