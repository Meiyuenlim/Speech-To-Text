from __future__ import annotations

from unittest.mock import patch


def create_meeting(client):
    response = client.post(
        "/api/meetings",
        json={"title": "Quarterly planning", "language": "en", "noise_reduction_enabled": False},
    )
    assert response.status_code == 201
    return response.json()


def test_health_endpoint(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "local-only"}


def test_meeting_creation_upload_transcript_edit_and_exports(client) -> None:
    meeting = create_meeting(client)
    meeting_id = meeting["id"]
    invalid = client.post(
        f"/api/meetings/{meeting_id}/upload",
        files={"file": ("notes.txt", b"not audio", "text/plain")},
    )
    assert invalid.status_code == 400

    uploaded = client.post(
        f"/api/meetings/{meeting_id}/upload",
        files={"file": ("meeting.wav", b"RIFFplaceholder", "audio/wav")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["original_filename"] == "meeting.wav"

    updated = client.put(
        f"/api/meetings/{meeting_id}/transcript",
        json={
            "segments": [
                {
                    "sequence": 0,
                    "start_time": 0,
                    "end_time": 4.2,
                    "text": "We will ship the draft on Friday.",
                    "confidence": 0.91,
                    "needs_review": False,
                }
            ]
        },
    )
    assert updated.status_code == 200
    assert updated.json()[0]["text"].startswith("We will")

    minutes = client.put(
        f"/api/meetings/{meeting_id}/minutes",
        json={
            "minutes": {
                "meeting_title": "Quarterly planning",
                "executive_summary": "A draft was scheduled.",
                "decisions_made": [],
                "action_items": [],
            }
        },
    )
    assert minutes.status_code == 200
    assert minutes.json()["minutes"]["executive_summary"] == "A draft was scheduled."
    assert client.post(f"/api/meetings/{meeting_id}/approve").status_code == 200
    assert client.get(f"/api/meetings/{meeting_id}/export/txt").status_code == 200
    assert client.get(f"/api/meetings/{meeting_id}/export/json").status_code == 200
    docx = client.get(f"/api/meetings/{meeting_id}/export/docx")
    assert docx.status_code == 200
    assert docx.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_process_requires_upload_and_job_queue_transition(client) -> None:
    meeting = create_meeting(client)
    response = client.post(f"/api/meetings/{meeting['id']}/process")
    assert response.status_code == 400

    client.post(
        f"/api/meetings/{meeting['id']}/upload",
        files={"file": ("meeting.mp3", b"audio", "audio/mpeg")},
    )
    with patch("app.api.routes.processing_manager.enqueue"):
        response = client.post(f"/api/meetings/{meeting['id']}/process")
    assert response.status_code == 202
    assert response.json()["status"] == "preparing_audio"
