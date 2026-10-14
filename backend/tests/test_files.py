from pathlib import Path

import pytest

from app.services.files import internal_audio_filename, sanitize_filename, validate_audio_filename


def test_filename_is_sanitized_and_path_traversal_removed() -> None:
    result = sanitize_filename("../../Finance: Q4?.m4a")
    assert result == "Finance_ Q4_.m4a"
    assert "/" not in result and "\\" not in result


def test_audio_extensions_are_restricted() -> None:
    assert validate_audio_filename("recording.MP3") == ".mp3"
    assert Path(internal_audio_filename(".wav")).suffix == ".wav"
    with pytest.raises(ValueError):
        validate_audio_filename("recording.exe")
