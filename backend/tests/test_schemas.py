import pytest

from app.schemas.meeting import EvidenceExtraction, MinutesDocument, TranscriptSegmentInput
from app.services.transcription import format_timestamp


def test_timestamp_formatting() -> None:
    assert format_timestamp(0) == "00:00:00"
    assert format_timestamp(3661.9) == "01:01:01"


def test_transcript_rejects_backwards_timestamps() -> None:
    with pytest.raises(ValueError):
        TranscriptSegmentInput(sequence=0, start_time=5, end_time=2, text="bad")


def test_structured_minutes_and_evidence_defaults_validate() -> None:
    assert EvidenceExtraction.model_validate({}).action_items == []
    document = MinutesDocument.model_validate({"meeting_title": "Planning"})
    assert document.meeting_title == "Planning"
    assert document.generation_warnings == []
