from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.core.config import settings


def whisper_runtime() -> tuple[str, str, bool]:
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            return "cuda", "float16", True
    except Exception:
        pass
    return "cpu", "int8", False


def ollama_models() -> tuple[bool, set[str], str]:
    try:
        request = Request(f"{settings.ollama_url.rstrip('/')}/api/tags", method="GET")
        with urlopen(request, timeout=2) as response:
            import json

            payload = json.loads(response.read().decode("utf-8"))
        models = {item.get("name", "") for item in payload.get("models", [])}
        return True, models, "Ollama is reachable"
    except (OSError, URLError, ValueError) as exc:
        return False, set(), f"Ollama is unavailable: {exc}"


def system_check(selected_model: str | None = None) -> dict:
    model = selected_model or settings.default_ollama_model
    ffmpeg_available = shutil.which("ffmpeg") is not None
    deepfilternet_available = (
        importlib.util.find_spec("df") is not None or shutil.which("deepFilter") is not None
    )
    ollama_available, models, ollama_message = ollama_models()
    device, compute_type, cuda = whisper_runtime()
    disk = shutil.disk_usage(settings.data_dir if settings.data_dir.exists() else settings.project_root)
    messages = [ollama_message]
    if not ffmpeg_available:
        messages.append("FFmpeg was not found on PATH.")
    if not deepfilternet_available:
        messages.append("DeepFilterNet is optional and was not found; processing will use the original WAV.")
    if not cuda:
        messages.append("CUDA is unavailable; faster-whisper will use CPU with INT8.")
    return {
        "ffmpeg_available": ffmpeg_available,
        "deepfilternet_available": deepfilternet_available,
        "ollama_available": ollama_available,
        "selected_ollama_model": model,
        "selected_ollama_model_available": model in models or any(name.split(":", 1)[0] == model for name in models),
        "cuda_available": cuda,
        "whisper_device": device,
        "whisper_compute_type": compute_type,
        "available_disk_space_bytes": disk.free,
        "messages": messages,
    }
