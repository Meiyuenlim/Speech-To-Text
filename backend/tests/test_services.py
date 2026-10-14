import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.audio import AudioPipeline, AudioProcessingError
from app.services.executables import resolve_executable
from app.services.ollama import OllamaClient, OllamaUnavailable
from app.services.transcription import TranscriptionService


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


def test_executable_can_be_configured_with_an_absolute_path(tmp_path, monkeypatch) -> None:
    executable = tmp_path / "ffmpeg.exe"
    executable.write_bytes(b"placeholder")
    monkeypatch.setenv("TEST_FFMPEG_PATH", str(executable))
    assert resolve_executable("ffmpeg", "TEST_FFMPEG_PATH") == str(executable)


def test_transcription_retries_without_vad_when_first_pass_is_empty(tmp_path) -> None:
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"wav")
    calls: list[bool] = []

    class FakeModel:
        def __init__(self, model_name, device, compute_type):
            assert (model_name, device, compute_type) == ("small", "cpu", "int8")

        def transcribe(self, path, **kwargs):
            calls.append(kwargs["vad_filter"])
            info = SimpleNamespace(language="en")
            if len(calls) == 1:
                return iter(()), info
            segment = SimpleNamespace(
                text="hello world",
                start=0.0,
                end=1.0,
                avg_logprob=-0.1,
                no_speech_prob=0.01,
            )
            return iter((segment,)), info

    fake_module = ModuleType("faster_whisper")
    fake_module.WhisperModel = FakeModel
    with patch.dict(sys.modules, {"faster_whisper": fake_module}):
        with patch("app.services.transcription.whisper_runtime", return_value=("cpu", "int8", False)):
            rows, language, device, compute_type = TranscriptionService().transcribe(
                audio, "small", "auto"
            )

    assert calls == [False, False]
    assert rows[0]["text"] == "hello world"
    assert language == "en"
    assert (device, compute_type) == ("cpu", "int8")
