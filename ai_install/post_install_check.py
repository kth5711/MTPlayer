from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run_capture(cmd: list[str]) -> dict:
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return {
            "ok": True,
            "returncode": int(proc.returncode),
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
        }


def module_exists(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def command_succeeded(result: dict) -> bool:
    return bool(result.get("ok")) and int(result.get("returncode", -1)) == 0


def decode_version_text(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value or "").strip()


def import_qt_widgets():
    from PyQt6 import QtWidgets  # type: ignore

    return "PyQt6", QtWidgets


def load_manifest(script_root: Path) -> dict:
    manifest_path = script_root / "install_manifest.json"
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def import_groups(manifest: dict) -> tuple[list[str], list[str], list[str]]:
    core = list(manifest.get("validation_imports_core") or ["PyQt6", "vlc", "yt_dlp"])
    scene = list(manifest.get("validation_imports_scene_analysis") or [])
    optional = list(manifest.get("validation_imports_scene_analysis_optional") or [])
    return core, scene, optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default="")
    return parser.parse_args()


def build_report(project_root: Path) -> dict:
    return {
        "python_executable": sys.executable,
        "project_root": str(project_root),
        "imports": {"core": {}, "scene_analysis": {}, "scene_analysis_optional": {}},
        "scene_analysis": {"available": False, "missing": [], "optional_missing": []},
        "ffmpeg": {},
        "vlc": {},
        "torch": {},
        "main_import": {"ok": False, "error": ""},
        "runtime_smoke": {"ok": False, "qt_api": "", "error": ""},
    }


def collect_import_report(
    report: dict,
    core_imports: list[str],
    scene_imports: list[str],
    optional_scene_imports: list[str],
) -> None:
    for name in core_imports:
        report["imports"]["core"][name] = module_exists(name)
    for name in scene_imports:
        report["imports"]["scene_analysis"][name] = module_exists(name)
    for name in optional_scene_imports:
        report["imports"]["scene_analysis_optional"][name] = module_exists(name)

    missing_scene = [name for name, ok in report["imports"]["scene_analysis"].items() if not ok]
    missing_optional_scene = [
        name for name, ok in report["imports"]["scene_analysis_optional"].items() if not ok
    ]
    report["scene_analysis"] = {
        "available": bool(scene_imports) and not missing_scene,
        "missing": missing_scene,
        "optional_missing": missing_optional_scene,
    }


def collect_ffmpeg_report(report: dict) -> None:
    try:
        from scene_analysis.core.media import resolve_ffmpeg_bin  # type: ignore

        ffmpeg_bin = resolve_ffmpeg_bin("")
        report["ffmpeg"]["path"] = ffmpeg_bin
        report["ffmpeg"]["version"] = run_capture([ffmpeg_bin, "-hide_banner", "-version"])
        report["ffmpeg"]["encoders"] = run_capture([ffmpeg_bin, "-hide_banner", "-encoders"])
        report["ffmpeg"]["hwaccels"] = run_capture([ffmpeg_bin, "-hide_banner", "-hwaccels"])
        version_text = (
            report["ffmpeg"]["version"].get("stdout", "")
            + "\n"
            + report["ffmpeg"]["version"].get("stderr", "")
        )
        encoder_text = (
            report["ffmpeg"]["encoders"].get("stdout", "")
            + "\n"
            + report["ffmpeg"]["encoders"].get("stderr", "")
        )
        report["ffmpeg"]["ok"] = command_succeeded(report["ffmpeg"]["version"]) and (
            "ffmpeg version" in version_text.lower()
        )
        report["ffmpeg"]["has_libx264"] = "libx264" in encoder_text
        report["ffmpeg"]["has_aac"] = " aac " in (" " + encoder_text + " ")
    except Exception as exc:
        report["ffmpeg"] = {
            "ok": False,
            "error": str(exc),
        }


def collect_vlc_report(report: dict) -> None:
    try:
        import app_shell.config  # type: ignore  # noqa: F401
    except Exception:
        pass

    instance = None
    try:
        import vlc  # type: ignore

        version = ""
        try:
            version = decode_version_text(vlc.libvlc_get_version())
        except Exception:
            version = ""
        instance = vlc.Instance("--no-video-title-show")
        report["vlc"] = {
            "found": True,
            "instance_ok": instance is not None,
            "version": version,
            "error": "",
        }
    except Exception as exc:
        report["vlc"] = {
            "found": module_exists("vlc"),
            "instance_ok": False,
            "version": "",
            "error": str(exc),
        }
    finally:
        if instance is not None:
            try:
                release = getattr(instance, "release", None)
                if callable(release):
                    release()
            except Exception:
                pass


def collect_torch_report(report: dict) -> None:
    try:
        import torch  # type: ignore

        report["torch"] = {
            "found": True,
            "version": getattr(torch, "__version__", None),
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_version": getattr(torch.version, "cuda", None),
            "device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
        }
    except Exception as exc:
        report["torch"] = {
            "found": False,
            "error": str(exc),
        }


def collect_main_import_report(report: dict) -> None:
    try:
        import main  # type: ignore  # noqa: F401

        report["main_import"] = {"ok": True, "error": ""}
    except Exception as exc:
        report["main_import"] = {"ok": False, "error": str(exc)}


def collect_runtime_smoke_report(report: dict) -> None:
    try:
        qt_api, QtWidgets = import_qt_widgets()
        report["runtime_smoke"]["qt_api"] = qt_api
    except Exception as exc:
        report["runtime_smoke"]["error"] = str(exc)
        return

    app = None
    created_app = False
    window = None
    try:
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication([])
            created_app = True

        import main as main_module  # type: ignore

        with tempfile.TemporaryDirectory(prefix="multi_play_smoke_") as tmpdir:
            config_path = Path(tmpdir) / "player_config.json"
            window = main_module.MainWin(config_path=str(config_path))
            try:
                app.processEvents()
            except Exception:
                pass
            try:
                window.close()
            except Exception:
                pass
            try:
                window.deleteLater()
            except Exception:
                pass
            try:
                app.processEvents()
            except Exception:
                pass
        report["runtime_smoke"]["ok"] = True
    except Exception as exc:
        report["runtime_smoke"]["error"] = str(exc)
    finally:
        if window is not None:
            try:
                window.close()
            except Exception:
                pass
        if created_app and app is not None:
            try:
                app.quit()
            except Exception:
                pass


def emit_report(report: dict, json_out: str) -> None:
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if json_out:
        out_path = Path(json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"Wrote verification report to {out_path}")
        return
    print(text)


def report_exit_code(report: dict) -> int:
    if not report["main_import"]["ok"]:
        return 1
    if not report.get("vlc", {}).get("instance_ok", False):
        return 2
    if not report.get("ffmpeg", {}).get("ok", False):
        return 3
    if report.get("ffmpeg", {}).get("has_libx264") is False:
        return 4
    if report.get("ffmpeg", {}).get("has_aac") is False:
        return 5
    if not report.get("runtime_smoke", {}).get("ok", False):
        return 6
    return 0


def main() -> int:
    args = parse_args()

    script_root = Path(__file__).resolve().parent
    project_root = script_root.parent
    manifest = load_manifest(script_root)
    core_imports, scene_imports, optional_scene_imports = import_groups(manifest)
    sys.path.insert(0, str(project_root))

    report = build_report(project_root)
    collect_import_report(report, core_imports, scene_imports, optional_scene_imports)
    collect_ffmpeg_report(report)
    collect_vlc_report(report)
    collect_torch_report(report)
    collect_main_import_report(report)
    collect_runtime_smoke_report(report)
    emit_report(report, args.json_out)
    return report_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
