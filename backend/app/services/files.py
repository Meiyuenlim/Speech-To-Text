from __future__ import annotations

import re
import uuid
from pathlib import Path


ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a"}
ALLOWED_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mp4",
    "audio/x-m4a",
    "application/octet-stream",  # Some Windows browsers use this for M4A/WAV.
}


def sanitize_filename(filename: str) -> str:
    name = Path(filename or "recording").name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    return name[:180] or "recording"


def validate_audio_filename(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Only MP3, WAV, and M4A recordings are supported")
    return extension


def internal_audio_filename(extension: str) -> str:
    return f"{uuid.uuid4()}{extension.lower()}"
