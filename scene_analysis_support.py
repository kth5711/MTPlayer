from __future__ import annotations

import importlib
from typing import Iterable

from PyQt6 import QtWidgets

from i18n import tr


SCENE_ANALYSIS_INSTALL_COMMAND = (
    r"powershell -ExecutionPolicy Bypass -File .\install\install_windows.ps1 -InstallSceneAnalysis"
)


def scene_analysis_button_tooltip(owner) -> str:
    return tr(owner, "씬변화 / 유사씬 분석 창 열기")


def open_scene_dialog(host) -> bool:
    try:
        opener = getattr(importlib.import_module("ffscene_cached"), "open_scene_dialog_with_options")
        opener(host)
        return True
    except ModuleNotFoundError as exc:
        missing = _missing_modules_from_exception(exc)
        if missing:
            _show_missing_dialog(host, missing)
            return False
        _show_import_error(host, exc)
        return False
    except Exception as exc:
        _show_import_error(host, exc)
        return False


def _missing_modules_from_exception(exc: BaseException) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()
    cur: BaseException | None = exc
    while cur is not None:
        if isinstance(cur, ModuleNotFoundError):
            name = str(getattr(cur, "name", "") or "").strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        cur = cur.__cause__ or cur.__context__
    return tuple(names)


def _show_missing_dialog(host, missing: Iterable[str]) -> None:
    modules = ", ".join(str(name) for name in missing)
    detail = "\n".join(
        (
            tr(host, "씬분석 옵션 패키지가 설치되지 않았습니다."),
            "",
            tr(host, "기본 플레이어는 정상 실행되며, 씬분석 기능만 추가 설치 후 사용할 수 있습니다."),
            tr(host, "누락 모듈: {modules}", modules=modules),
            tr(host, "설치 명령: {command}", command=SCENE_ANALYSIS_INSTALL_COMMAND),
        )
    )
    QtWidgets.QMessageBox.information(_dialog_parent(host), tr(host, "안내"), detail)


def _show_import_error(host, exc: Exception) -> None:
    QtWidgets.QMessageBox.critical(
        _dialog_parent(host),
        tr(host, "실패"),
        tr(host, "씬분석을 열지 못했습니다.\n\n{error}", error=str(exc) or exc.__class__.__name__),
    )


def _dialog_parent(host):
    return host if isinstance(host, QtWidgets.QWidget) else None
