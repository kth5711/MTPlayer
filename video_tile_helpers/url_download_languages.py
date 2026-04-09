from __future__ import annotations

from typing import Final


DEFAULT_URL_SUBTITLE_LANGUAGE: Final[str] = "ko"
URL_SUBTITLE_LANGUAGES: Final[tuple[tuple[str, str], ...]] = (
    ("ko", "한국어"),
    ("en", "English"),
    ("ja", "日本語"),
    ("zh-Hans", "中文(简体)"),
    ("zh-Hant", "中文(繁體)"),
    ("es", "Español"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("it", "Italiano"),
    ("pt", "Português"),
    ("pt-BR", "Português (Brasil)"),
    ("ru", "Русский"),
    ("uk", "Українська"),
    ("pl", "Polski"),
    ("nl", "Nederlands"),
    ("tr", "Türkçe"),
    ("ar", "العربية"),
    ("hi", "हिन्दी"),
    ("bn", "বাংলা"),
    ("id", "Bahasa Indonesia"),
    ("vi", "Tiếng Việt"),
    ("th", "ไทย"),
    ("ms", "Bahasa Melayu"),
    ("tl", "Filipino"),
    ("fa", "فارسی"),
    ("he", "עברית"),
    ("sv", "Svenska"),
    ("no", "Norsk"),
    ("da", "Dansk"),
    ("fi", "Suomi"),
    ("cs", "Čeština"),
    ("hu", "Magyar"),
    ("ro", "Română"),
    ("bg", "Български"),
    ("el", "Ελληνικά"),
    ("sr", "Српски"),
    ("hr", "Hrvatski"),
    ("sk", "Slovenčina"),
    ("sl", "Slovenščina"),
    ("et", "Eesti"),
    ("lv", "Latviešu"),
    ("lt", "Lietuvių"),
)
_URL_SUBTITLE_LANGUAGE_CODES: Final[set[str]] = {code for code, _label in URL_SUBTITLE_LANGUAGES}


def normalize_url_subtitle_language(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return DEFAULT_URL_SUBTITLE_LANGUAGE
    candidate = text.split(",", 1)[0].strip()
    if candidate.endswith(".*"):
        candidate = candidate[:-2]
    if candidate in _URL_SUBTITLE_LANGUAGE_CODES:
        return candidate
    lowered = candidate.lower()
    for code, _label in URL_SUBTITLE_LANGUAGES:
        if code.lower() == lowered:
            return code
    short = lowered.split("-", 1)[0]
    for code, _label in URL_SUBTITLE_LANGUAGES:
        if code.lower() == short:
            return code
    return DEFAULT_URL_SUBTITLE_LANGUAGE
