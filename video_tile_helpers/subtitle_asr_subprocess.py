from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from typing import Iterable

try:
    from faster_whisper import BatchedInferencePipeline, WhisperModel
except ImportError:
    BatchedInferencePipeline = None
    from faster_whisper import WhisperModel

try:
    import torch
except Exception:
    torch = None


DEFAULT_MODEL = "Systran/faster-whisper-large-v3"
MAX_CUE_SECONDS = 5.2
MIN_CUE_SECONDS = 0.9
MAX_TOKENS_PER_CUE = 20
SOFT_GAP_SECONDS = 0.42
HARD_GAP_SECONDS = 0.95
DEFAULT_GPU_BATCH_SIZES = (8, 4, 2)
DEFAULT_CPU_BATCH_SIZES = (4, 2)


@dataclass
class Token:
    start: float
    end: float
    text: str


@dataclass
class Cue:
    start: float
    end: float
    text: str


def main() -> int:
    args = _parse_args()
    os.makedirs(os.path.dirname(args.output) or os.getcwd(), exist_ok=True)
    _emit_progress("모델 로드 중", 0.0)
    model, segments, info = _transcribe(args.input, args.model, args.language or None)
    _ = model
    total_duration = _info_duration_seconds(info, segments)
    _emit_progress("전사 중", 1.0 if total_duration > 0.0 else None)
    segment_list = _collect_segments_with_progress(segments, total_duration)
    _emit_progress("큐 정리 중", 96.0)
    cues = _build_cues(_segments_to_tokens(segment_list))
    if not cues:
        raise RuntimeError("음성 구간을 찾지 못했습니다.")
    _emit_progress("저장 중", 99.0, f"{len(cues)} cues")
    with open(args.output, "w", encoding="utf-8-sig", newline="\n") as handle:
        handle.write(_render_srt(cues))
    _emit_progress("완료", 100.0, f"{len(cues)} cues")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--language", default="")
    return parser.parse_args()


def _transcribe(media_path: str, model_name: str, language: str | None):
    kwargs = {
        "beam_size": 5,
        "word_timestamps": True,
        "vad_filter": True,
        "condition_on_previous_text": False,
        "without_timestamps": False,
    }
    if language:
        kwargs["language"] = language
    last_error: Exception | None = None
    for device, compute_type in (("cuda", "float16"), ("cpu", "int8")):
        try:
            model = WhisperModel(model_name, device=device, compute_type=compute_type)
            segments, info = _transcribe_with_best_pipeline(model, media_path, kwargs, device, model_name)
            return model, segments, info
        except Exception as exc:
            last_error = exc
    raise RuntimeError(str(last_error or "faster-whisper 실행에 실패했습니다."))


def _transcribe_with_best_pipeline(model, media_path: str, kwargs: dict, device: str, model_name: str):
    if _is_large_quality_model(model_name):
        return model.transcribe(media_path, **kwargs)
    if BatchedInferencePipeline is not None:
        pipeline = BatchedInferencePipeline(model=model)
        last_error: Exception | None = None
        for batch_size in _batch_size_candidates(device, model_name):
            try:
                return pipeline.transcribe(media_path, batch_size=batch_size, **kwargs)
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            try:
                return model.transcribe(media_path, **kwargs)
            except Exception:
                raise last_error
    return model.transcribe(media_path, **kwargs)


def _collect_segments_with_progress(segments: Iterable, total_duration: float) -> list:
    out: list = []
    last_percent = -1.0
    for seg in segments:
        out.append(seg)
        seg_end = max(0.0, float(getattr(seg, "end", 0.0) or 0.0))
        percent = None
        if total_duration > 0.0:
            percent = min(95.0, max(1.0, (seg_end / total_duration) * 95.0))
        if percent is None:
            if len(out) == 1 or (len(out) % 25) == 0:
                _emit_progress("전사 중", None, f"{len(out)} segments")
        elif percent - last_percent >= 1.0:
            _emit_progress("전사 중", percent, f"{seg_end:.1f}s")
            last_percent = percent
    return out


def _info_duration_seconds(info, segments: Iterable) -> float:
    for key in ("duration", "duration_after_vad"):
        try:
            value = float(getattr(info, key, 0.0) or 0.0)
        except Exception:
            value = 0.0
        if value > 0.0:
            return value
    return 0.0


def _emit_progress(stage: str, percent: float | None, note: str = "") -> None:
    payload = {"stage": str(stage or "").strip() or "자막 생성 중"}
    if percent is not None:
        payload["percent"] = max(0.0, min(100.0, float(percent)))
    if note:
        payload["note"] = str(note or "").strip()
    print("__MP_PROGRESS__" + json.dumps(payload, ensure_ascii=False), flush=True)


def _batch_size_candidates(device: str, model_name: str = "") -> tuple[int, ...]:
    override = _batch_size_override()
    if override is not None:
        return _normalize_batch_sizes((override, max(2, override // 2), 4, 2))
    if _is_large_quality_model(model_name):
        return _large_quality_batch_size_candidates(device)
    if str(device or "").strip().lower() == "cuda":
        vram_gb = _cuda_total_memory_gb()
        if vram_gb >= 14.0:
            return _normalize_batch_sizes((16, 12, 8, 4, 2))
        if vram_gb >= 10.0:
            return _normalize_batch_sizes((12, 8, 4, 2))
        return DEFAULT_GPU_BATCH_SIZES
    return DEFAULT_CPU_BATCH_SIZES


def _is_large_quality_model(model_name: str) -> bool:
    lower = str(model_name or "").strip().lower()
    if not lower:
        return False
    return "large-v3" in lower and "turbo" not in lower


def _large_quality_batch_size_candidates(device: str) -> tuple[int, ...]:
    if str(device or "").strip().lower() == "cuda":
        vram_gb = _cuda_total_memory_gb()
        if vram_gb >= 14.0:
            return _normalize_batch_sizes((8, 6, 4, 2))
        if vram_gb >= 10.0:
            return _normalize_batch_sizes((6, 4, 2))
        return _normalize_batch_sizes((4, 2))
    return DEFAULT_CPU_BATCH_SIZES


def _batch_size_override() -> int | None:
    raw = str(os.environ.get("MULTIPLAY_SUBTITLE_BATCH_SIZE") or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _normalize_batch_sizes(values: tuple[int, ...]) -> tuple[int, ...]:
    out: list[int] = []
    seen: set[int] = set()
    for value in values:
        ivalue = int(value or 0)
        if ivalue <= 0 or ivalue in seen:
            continue
        seen.add(ivalue)
        out.append(ivalue)
    return tuple(out) if out else DEFAULT_CPU_BATCH_SIZES


def _cuda_total_memory_gb() -> float:
    if torch is None:
        return 0.0
    try:
        if not torch.cuda.is_available():
            return 0.0
        props = torch.cuda.get_device_properties(0)
        total = float(getattr(props, "total_memory", 0) or 0)
        return total / float(1024 ** 3)
    except Exception:
        return 0.0


def _segments_to_tokens(segments: Iterable) -> list[Token]:
    tokens: list[Token] = []
    for seg in segments:
        seg_start = float(getattr(seg, "start", 0.0) or 0.0)
        seg_end = max(seg_start + 0.05, float(getattr(seg, "end", seg_start + 0.05) or (seg_start + 0.05)))
        words = list(getattr(seg, "words", None) or [])
        if words:
            for word in words:
                text = str(getattr(word, "word", "") or "").strip()
                if not text:
                    continue
                start = float(getattr(word, "start", seg_start) or seg_start)
                end = float(getattr(word, "end", start + 0.05) or (start + 0.05))
                tokens.append(Token(start=max(0.0, start), end=max(start + 0.03, end), text=text))
            continue
        text = _normalize_text(str(getattr(seg, "text", "") or ""))
        if not text:
            continue
        parts = _split_text_for_fallback(text)
        if not parts:
            continue
        span = max(0.05, seg_end - seg_start)
        step = span / max(1, len(parts))
        for idx, part in enumerate(parts):
            start = seg_start + (idx * step)
            end = seg_start + ((idx + 1) * step)
            tokens.append(Token(start=start, end=max(start + 0.03, end), text=part))
    return tokens


def _split_text_for_fallback(text: str) -> list[str]:
    parts = [part for part in re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE) if str(part or "").strip()]
    return parts if parts else [text]


def _build_cues(tokens: list[Token]) -> list[Cue]:
    if not tokens:
        return []
    cues: list[Cue] = []
    bucket: list[Token] = []
    for token in tokens:
        if bucket and _should_break_bucket(bucket, token):
            cue = _make_cue(bucket)
            if cue is not None:
                cues.append(cue)
            bucket = []
        bucket.append(token)
    if bucket:
        cue = _make_cue(bucket)
        if cue is not None:
            cues.append(cue)
    return _normalize_cues(cues)


def _should_break_bucket(bucket: list[Token], token: Token) -> bool:
    gap = max(0.0, token.start - bucket[-1].end)
    if gap >= HARD_GAP_SECONDS:
        return True
    preview = bucket + [token]
    preview_text = _join_tokens(preview)
    total_duration = max(0.0, token.end - bucket[0].start)
    if len(preview) > MAX_TOKENS_PER_CUE:
        return True
    if total_duration > MAX_CUE_SECONDS:
        return True
    if _display_width(preview_text) > (_line_limit(preview_text) * 2):
        return True
    if gap >= SOFT_GAP_SECONDS:
        current_text = _join_tokens(bucket)
        if _ends_with_break_punctuation(current_text):
            return True
    return False


def _make_cue(bucket: list[Token]) -> Cue | None:
    text = _format_cue_lines(bucket)
    if not text:
        return None
    start = max(0.0, float(bucket[0].start))
    end = max(start + 0.05, float(bucket[-1].end))
    return Cue(start=start, end=end, text=text)


def _format_cue_lines(tokens: list[Token]) -> str:
    parts = [str(tok.text or "").strip() for tok in tokens if str(tok.text or "").strip()]
    if not parts:
        return ""
    line_limit = _line_limit(_join_tokens(tokens))
    lines: list[str] = []
    current: list[str] = []
    for part in parts:
        candidate = _join_parts(current + [part])
        if current and _display_width(candidate) > line_limit and len(lines) < 1:
            lines.append(_join_parts(current))
            current = [part]
            continue
        current.append(part)
    if current:
        lines.append(_join_parts(current))
    if len(lines) <= 2:
        return "\n".join(lines)
    return "\n".join([lines[0], _join_parts(lines[1:])])


def _normalize_cues(cues: list[Cue]) -> list[Cue]:
    normalized: list[Cue] = []
    for idx, cue in enumerate(cues):
        start = max(0.0, cue.start)
        end = max(start + 0.25, cue.end)
        if end - start < MIN_CUE_SECONDS:
            end = start + MIN_CUE_SECONDS
        if idx + 1 < len(cues):
            next_start = max(start + 0.25, cues[idx + 1].start)
            end = min(end, max(start + 0.25, next_start - 0.04))
        normalized.append(Cue(start=start, end=end, text=cue.text))
    return normalized


def _render_srt(cues: list[Cue]) -> str:
    blocks: list[str] = []
    for idx, cue in enumerate(cues, start=1):
        blocks.append(
            f"{idx}\n{_format_timestamp(cue.start)} --> {_format_timestamp(cue.end)}\n{cue.text}\n"
        )
    return "\n".join(blocks).strip() + "\n"


def _format_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000.0)))
    hours, rem = divmod(total_ms, 3600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _line_limit(text: str) -> int:
    return 22 if _contains_cjk(text) else 42


def _contains_cjk(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if 0x1100 <= code <= 0x11FF or 0x2E80 <= code <= 0x9FFF or 0xAC00 <= code <= 0xD7A3:
            return True
    return False


def _display_width(text: str) -> int:
    width = 0
    for ch in text:
        if ch == "\n":
            continue
        width += 2 if unicodedata.east_asian_width(ch) in {"F", "W", "A"} else 1
    return width


def _join_tokens(tokens: list[Token]) -> str:
    return _join_parts([tok.text for tok in tokens])


def _join_parts(parts: Iterable[str]) -> str:
    out = ""
    for raw in parts:
        part = str(raw or "").strip()
        if not part:
            continue
        if not out:
            out = part
            continue
        if _needs_space(out, part):
            out += " " + part
        else:
            out += part
    return out.strip()


def _needs_space(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if _starts_with_punctuation(right) or _ends_with_open_punctuation(left):
        return False
    if _contains_cjk(left[-1]) or _contains_cjk(right[0]):
        return False
    return True


def _starts_with_punctuation(text: str) -> bool:
    return bool(text and unicodedata.category(text[0]).startswith("P"))


def _ends_with_open_punctuation(text: str) -> bool:
    return bool(text and text[-1] in "([{\"'“‘")


def _ends_with_break_punctuation(text: str) -> bool:
    return bool(text.rstrip().endswith((".", "!", "?", "…", "。", "！", "？")))


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc or "알 수 없는 오류"), file=sys.stderr)
        raise SystemExit(1)
