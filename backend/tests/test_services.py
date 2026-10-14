from unittest.mock import patch

import pytest

from app.services.audio import AudioPipeline, AudioProcessingError
from app.services.ollama import OllamaClient, OllamaUnavailable


def test_deepfilter_failure_is_an_optional_processing_error(tmp_path) -> None:
    source = tmp_path / "input.wav"
    destination = tmp_path / "enhanced.wav"
    source.write_bytes(b"wav")
    with patch("app.services.audio.shutil.which", return_value=None):
        with pytest.raises(AudioProcessingError, match="not installed"):
            AudioPipeline().enhance_with_deepfilter(source, destination)


def test_ollama_unavailable_is_reported_without_credentials() -> None:
    with patch("app.services.ollama.httpx.get", side_effect=OSError("offline")):
        with pytest.raises(OllamaUnavailable, match="Ollama is unavailable"):
            OllamaClient("http://127.0.0.1:9").list_models()
