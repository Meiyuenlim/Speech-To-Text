from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterator
from pathlib import Path

from app.services.system import whisper_runtime


def _confidence(avg_logprob: float | None) -> float | None:
    if avg_logprob is None:
        return None
    return round(max(0.0, min(1.0, math.exp(avg_logprob))), 3)


def _looks_repetitive(text: str) -> bool:
    words = re.findall(r"\w+", text.lower())
    if len(words) < 6:
        return False
    return len(set(words)) <= max(2, len(words) // 4)


class TranscriptionService:
    def runtime(self) -> tuple[str, str]:
        device, compute_type, _ = whisper_runtime()
        return device, compute_type

    def transcribe(
        self,
        audio_path: Path,
        model_name: str,
        language: str,
        glossary: str | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> tuple[list[dict], str | None, str, str]:
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Install it in the backend virtual environment."
            ) from exc

        device, compute_type = self.runtime()
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
        kwargs = {
            "beam_size": 5,
            "vad_filter": True,
            "word_timestamps": True,
            "task": "transcribe",
        }
        if language != "auto":
            kwargs["language"] = language
        if glossary:
            kwargs["initial_prompt"] = glossary
        segments, info = model.transcribe(str(audio_path), **kwargs)
        rows: list[dict] = []
        for index, segment in enumerate(segments):
            text = (segment.text or "").strip()
            if not text:
                continue
            confidence = _confidence(getattr(segment, "avg_logprob", None))
            no_speech = getattr(segment, "no_speech_prob", 0.0) or 0.0
            uncertain = bool(no_speech > 0.6 or (confidence is not None and confidence < 0.35))
            rows.append(
                {
                    "sequence": index,
                    "start_time": float(segment.start),
                    "end_time": float(segment.end),
                    "text": text,
                    "confidence": confidence,
                    "needs_review": uncertain or _looks_repetitive(text),
                }
            )
            if progress:
                progress(min(75, 45 + len(rows) // 5))
        detected_language = getattr(info, "language", None)
        return rows, detected_language, device, compute_type


def transcript_text(segments: list[dict]) -> str:
    return "\n".join(f"[{format_timestamp(row['start_time'])}] {row['text']}" for row in segments)


def format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def chunk_segments(segments: list[dict], max_chars: int = 9000) -> Iterator[list[dict]]:
    current: list[dict] = []
    current_chars = 0
    for segment in segments:
        size = len(segment.get("text", ""))
        if current and current_chars + size > max_chars:
            yield current
            current = []
            current_chars = 0
        current.append(segment)
        current_chars += size
    if current:
        yield current
