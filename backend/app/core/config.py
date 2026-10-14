from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


def _path_from_env(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser().resolve() if value else default


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    data_dir: Path = _path_from_env("MEETING_DATA_DIR", PROJECT_ROOT / "data")
    database_url: str = os.getenv(
        "MEETING_DATABASE_URL",
        f"sqlite:///{(_path_from_env('MEETING_DATA_DIR', PROJECT_ROOT / 'data') / 'meetings.db').as_posix()}",
    )
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    default_ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    default_whisper_model: str = os.getenv("WHISPER_MODEL", "large-v3-turbo")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "500"))
    max_recording_minutes: int = int(os.getenv("MAX_RECORDING_MINUTES", "240"))
    backend_host: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    def ensure_directories(self) -> None:
        for directory in (self.data_dir, self.uploads_dir, self.processed_dir, self.exports_dir):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
