from __future__ import annotations

import concurrent.futures
import importlib.util
import json
import os
import shutil
import subprocess
from typing import Any, Dict
from urllib.parse import unquote, urlparse

from process_utils import hidden_subprocess_kwargs

HTTP_SCHEMES = {"http", "https"}
STREAM_SCHEMES = {
    "http",
    "https",
    "rtsp",
    "rtsps",
    "rtmp",
    "rtmps",
    "udp",
    "mms",
    "ftp",
    "ftps",
    "smb",
}
DIRECT_MEDIA_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".m4v",
    ".webm",
    ".ts",
    ".flv",
    ".wmv",
    ".mp3",
    ".m4a",
    ".aac",
    ".wav",
    ".ogg",
    ".opus",
    ".m3u8",
    ".mpd",
}
EXTRACTOR_HOST_SUFFIXES = (
    "youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "vimeo.com",
    "twitch.tv",
    "tv.naver.com",
    "chzzk.naver.com",
    "tiktok.com",
    "afreecatv.com",
    "sooplive.co.kr",
)
DEFAULT_RESOLVE_TIMEOUT_SECONDS = 15.0


def is_probably_url(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        parsed = urlparse(text)
    except Exception:
        return False
    scheme = str(parsed.scheme or "").lower()
    if not scheme:
        return False
    if scheme == "file":
        return True
    return scheme in STREAM_SCHEMES and bool(parsed.netloc or parsed.path)


def media_source_display_name(source: str) -> str:
    text = str(source or "").strip()
    if not text:
        return ""
    if not is_probably_url(text):
        return os.path.basename(text) or text
    try:
        parsed = urlparse(text)
    except Exception:
        return os.path.basename(text) or text
    if parsed.scheme.lower() == "file":
        local_path = unquote(parsed.path or "")
        if os.name == "nt" and local_path.startswith("/") and len(local_path) > 2 and local_path[2] == ":":
            local_path = local_path[1:]
        return os.path.basename(local_path) or text
    name = os.path.basename(unquote((parsed.path or "").rstrip("/")))
    if name:
        return name
    host = str(parsed.netloc or "").strip()
    if host:
        return host
    return text


def is_direct_media_url(source: str) -> bool:
    if not is_probably_url(source):
        return False
    try:
        parsed = urlparse(str(source or "").strip())
    except Exception:
        return False
    scheme = str(parsed.scheme or "").lower()
    if scheme not in HTTP_SCHEMES:
        return True
    path = unquote(parsed.path or "").lower()
    if any(path.endswith(ext) for ext in DIRECT_MEDIA_EXTENSIONS):
        return True
    if ".m3u8" in path or ".mpd" in path or ".ism/manifest" in path:
        return True
    return False


def extractor_hint_for_url(source: str) -> bool:
    if not is_probably_url(source):
        return False
    try:
        parsed = urlparse(str(source or "").strip())
    except Exception:
        return False
    if str(parsed.scheme or "").lower() not in HTTP_SCHEMES:
        return False
    host = str(parsed.netloc or "").strip().lower()
    if not host:
        return False
    return any(host == suffix or host.endswith("." + suffix) for suffix in EXTRACTOR_HOST_SUFFIXES)


def has_yt_dlp_support() -> bool:
    if importlib.util.find_spec("yt_dlp") is not None:
        return True
    return bool(shutil.which("yt-dlp") or shutil.which("yt-dlp.exe"))


def _pick_info_dict(info: Any) -> Dict[str, Any]:
    if not isinstance(info, dict):
        return {}
    entries = info.get("entries")
    if isinstance(entries, list):
        for entry in entries:
            picked = _pick_info_dict(entry)
            if picked:
                return picked
    return info


def _normalize_headers(raw_headers: Any) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not isinstance(raw_headers, dict):
        return out
    user_agent = str(raw_headers.get("User-Agent") or raw_headers.get("user-agent") or "").strip()
    referer = str(raw_headers.get("Referer") or raw_headers.get("referer") or "").strip()
    if user_agent:
        out["User-Agent"] = user_agent
    if referer:
        out["Referer"] = referer
    return out


def _build_result(info: Dict[str, Any], resolver: str) -> Dict[str, Any]:
    picked = _pick_info_dict(info)
    playback_url = str(picked.get("url") or "").strip()
    if not playback_url:
        raise RuntimeError("yt-dlp가 재생 가능한 스트림 URL을 돌려주지 않았습니다.")
    return {
        "playback_url": playback_url,
        "resolver": resolver,
        "resolved": True,
        "extractor": str(picked.get("extractor") or "").strip(),
        "headers": _normalize_headers(picked.get("http_headers")),
    }


def _resolve_with_python_module(
    source: str,
    *,
    timeout_seconds: float = DEFAULT_RESOLVE_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    from yt_dlp import YoutubeDL  # type: ignore

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
        "format": "best",
        "socket_timeout": max(1.0, float(timeout_seconds)),
    }
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_extract_info_with_module, source, opts)
    try:
        info = future.result(timeout=max(1.0, float(timeout_seconds)))
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise RuntimeError(
            f"yt-dlp Python 해석이 {float(timeout_seconds):.0f}초 안에 끝나지 않았습니다."
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    return _build_result(info, "yt_dlp")


def _extract_info_with_module(source: str, opts: Dict[str, Any]) -> Dict[str, Any]:
    from yt_dlp import YoutubeDL  # type: ignore

    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(source, download=False)


def _cli_executable() -> str:
    return shutil.which("yt-dlp") or shutil.which("yt-dlp.exe") or ""


def _resolve_with_cli(
    source: str,
    *,
    timeout_seconds: float = DEFAULT_RESOLVE_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    executable = _cli_executable()
    if not executable:
        raise RuntimeError("PATH에서 yt-dlp 실행 파일을 찾지 못했습니다.")
    try:
        proc = subprocess.run(
            [
                executable,
                "--quiet",
                "--no-warnings",
                "--no-playlist",
                "--skip-download",
                "-f",
                "best",
                "--dump-single-json",
                source,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=max(1.0, float(timeout_seconds)),
            **hidden_subprocess_kwargs(),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"yt-dlp CLI 해석이 {float(timeout_seconds):.0f}초 안에 끝나지 않았습니다."
        ) from exc
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(message or f"yt-dlp CLI 실행이 실패했습니다. (exit code {proc.returncode})")
    lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("yt-dlp CLI가 JSON 결과를 돌려주지 않았습니다.")
    try:
        info = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"yt-dlp CLI 결과 JSON을 파싱하지 못했습니다: {exc}") from exc
    return _build_result(info, "yt_dlp_cli")


def resolve_playback_source(
    source: str,
    *,
    timeout_seconds: float = DEFAULT_RESOLVE_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    text = str(source or "").strip()
    result = {
        "requested_source": text,
        "playback_url": text,
        "resolver": "direct",
        "resolved": False,
        "extractor": "",
        "headers": {},
    }
    if not text or not is_probably_url(text):
        return result
    if is_direct_media_url(text):
        return result

    needs_extractor = extractor_hint_for_url(text)
    support_available = has_yt_dlp_support()
    if not support_available and needs_extractor:
        raise RuntimeError(
            "유튜브 같은 페이지 URL 재생에는 yt-dlp가 필요합니다.\n\n"
            "설치:\n"
            "pip install yt-dlp"
        )
    if not support_available:
        return result

    errors = []
    if _cli_executable():
        try:
            return {**result, **_resolve_with_cli(text, timeout_seconds=timeout_seconds)}
        except Exception as exc:
            errors.append(str(exc))
    try:
        if importlib.util.find_spec("yt_dlp") is None:
            raise RuntimeError("yt-dlp Python 모듈을 찾지 못했습니다.")
        return {**result, **_resolve_with_python_module(text, timeout_seconds=timeout_seconds)}
    except Exception as exc:
        errors.append(str(exc))

    if needs_extractor:
        detail = "\n".join(err for err in errors if err) or "원인을 확인하지 못했습니다."
        raise RuntimeError(f"yt-dlp가 이 페이지 URL을 해석하지 못했습니다.\n\n{text}\n\n{detail}")
    return result


def apply_media_request_options(media, headers: Dict[str, str]):
    if media is None or not isinstance(headers, dict):
        return
    user_agent = str(headers.get("User-Agent") or "").strip()
    referer = str(headers.get("Referer") or "").strip()
    if user_agent:
        try:
            media.add_option(f":http-user-agent={user_agent}")
        except Exception:
            pass
    if referer:
        try:
            media.add_option(f":http-referrer={referer}")
        except Exception:
            pass
