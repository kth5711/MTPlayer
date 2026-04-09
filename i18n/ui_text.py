from __future__ import annotations

from typing import Any

from .ui_text_catalog_main import EN_UI_TEXT_MAIN
from .ui_text_catalog_main_ja import JA_UI_TEXT_MAIN
from .ui_text_catalog_main_zh import ZH_UI_TEXT_MAIN
from .ui_text_catalog_media import EN_UI_TEXT_MEDIA
from .ui_text_catalog_media_ja import JA_UI_TEXT_MEDIA
from .ui_text_catalog_media_zh import ZH_UI_TEXT_MEDIA
from .ui_text_catalog_scene import EN_UI_TEXT_SCENE
from .ui_text_catalog_scene_ja import JA_UI_TEXT_SCENE
from .ui_text_catalog_scene_zh import ZH_UI_TEXT_SCENE


SUPPORTED_UI_LANGUAGES = ("ko", "en", "ja", "zh")

LANGUAGE_NAMES = {
    "ko": "한국어",
    "en": "English",
    "ja": "日本語",
    "zh": "中文",
}

EN_UI_TEXT = {}
EN_UI_TEXT.update(EN_UI_TEXT_MAIN)
EN_UI_TEXT.update(EN_UI_TEXT_MEDIA)
EN_UI_TEXT.update(EN_UI_TEXT_SCENE)

JA_UI_TEXT = dict(EN_UI_TEXT)
JA_UI_TEXT.update(JA_UI_TEXT_MAIN)
JA_UI_TEXT.update(JA_UI_TEXT_MEDIA)
JA_UI_TEXT.update(JA_UI_TEXT_SCENE)

ZH_UI_TEXT = dict(EN_UI_TEXT)
ZH_UI_TEXT.update(ZH_UI_TEXT_MAIN)
ZH_UI_TEXT.update(ZH_UI_TEXT_MEDIA)
ZH_UI_TEXT.update(ZH_UI_TEXT_SCENE)

TRANSLATION_TABLES = {
    "en": EN_UI_TEXT,
    "ja": JA_UI_TEXT,
    "zh": ZH_UI_TEXT,
}


def normalize_ui_language(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("ja") or text.startswith("jp") or "日本" in str(value or ""):
        return "ja"
    if (
        text.startswith("zh")
        or text.startswith("cn")
        or "中文" in str(value or "")
        or "汉语" in str(value or "")
        or "漢語" in str(value or "")
    ):
        return "zh"
    if text.startswith("en"):
        return "en"
    return "ko"


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(normalize_ui_language(code), "한국어")


def _push_owner_candidate(stack: list[Any], current: Any, name: str):
    getter = getattr(current, name, None)
    if not callable(getter):
        return
    try:
        stack.append(getter())
    except Exception:
        pass


def _owner_candidates(owner: Any):
    seen: set[int] = set()
    stack = [owner]
    while stack:
        current = stack.pop(0)
        if current is None:
            continue
        ident = id(current)
        if ident in seen:
            continue
        seen.add(ident)
        yield current
        for name in ("_main_window", "parent", "window"):
            _push_owner_candidate(stack, current, name)
        host = getattr(current, "host", None)
        if host is not None:
            stack.append(host)


def ui_language(owner: Any) -> str:
    for candidate in _owner_candidates(owner):
        if hasattr(candidate, "ui_language"):
            return normalize_ui_language(getattr(candidate, "ui_language", "ko"))
        config = getattr(candidate, "config", None)
        if isinstance(config, dict) and "language" in config:
            return normalize_ui_language(config.get("language"))
    return "ko"


def tr(owner: Any, text: str, **kwargs: Any) -> str:
    template = str(text or "")
    template = TRANSLATION_TABLES.get(ui_language(owner), {}).get(template, template)
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template
