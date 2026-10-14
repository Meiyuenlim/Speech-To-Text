from unittest.mock import patch

import pytest

from app.schemas.meeting import EvidenceExtraction, MinutesDocument
from app.services.processor import ProcessingManager


@pytest.mark.parametrize("has_previous_transcript", [False, True])
def test_processing_passes_newly_saved_transcript_to_minutes(client, has_previous_transcript):
    """Exercise the real worker and SQLite session, mocking only audio/AI work."""
    meeting = client.post("/api/meetings", json={
        "title": "Transcript handoff", "noise_reduction_enabled": False,
    }).json()
    meeting_id = meeting["id"]
    uploaded = client.post(f"/api/meetings/{meeting_id}/upload", files={
        "file": ("recording.wav", b"placeholder", "audio/wav"),
    })
    assert uploaded.status_code == 200
    if has_previous_transcript:
        edited = client.put(f"/api/meetings/{meeting_id}/transcript", json={"segments": [{
            "sequence": 0, "start_time": 0, "end_time": 1,
            "text": "Obsolete transcript from previous processing.",
        }]})
        assert edited.status_code == 200

    rows = [{"sequence": 0, "start_time": 0.0, "end_time": 2.0,
             "text": "The new deadline is Friday.", "confidence": 0.9,
             "needs_review": False}]
    evidence_prompts = []

    def generate(client, model, prompt, schema, json_schema):
        if schema is EvidenceExtraction:
            evidence_prompts.append(prompt)
            return EvidenceExtraction(), []
        return MinutesDocument(meeting_title="Transcript handoff"), []

    manager = ProcessingManager()
    try:
        with (
            patch("app.services.processor.AudioPipeline.convert_to_wav"),
            patch("app.services.processor.AudioPipeline.duration_seconds", return_value=2.0),
            patch("app.services.processor.TranscriptionService.runtime", return_value=("cpu", "int8")),
            patch("app.services.processor.TranscriptionService.transcribe", return_value=(rows, "en", "cpu", "int8")),
            patch("app.services.processor.OllamaClient.ensure_model"),
            patch("app.services.processor.validate_with_retry", side_effect=generate),
        ):
            manager._run(meeting_id, regenerate_only=False)
    finally:
        manager.executor.shutdown(wait=True)

    # A fresh API session can see the transcript even when the worker's cached
    # relationship was empty or held deleted rows before the insert.
    transcript = client.get(f"/api/meetings/{meeting_id}/transcript").json()
    assert [segment["text"] for segment in transcript] == [rows[0]["text"]]
    status = client.get(f"/api/meetings/{meeting_id}/status").json()
    assert status["status"] == "completed", status
    assert status["error_message"] is None
    assert len(evidence_prompts) == 1
    assert rows[0]["text"] in evidence_prompts[0]
    assert "Obsolete transcript" not in evidence_prompts[0]
    assert client.get(f"/api/meetings/{meeting_id}/minutes").json() is not None
