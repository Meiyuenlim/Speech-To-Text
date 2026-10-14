from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO

from docx import Document
from docx.enum.text import WD_BREAK
from docx.shared import Inches

from app.models.meeting import Meeting
from app.schemas.meeting import MinutesDocument
from app.services.markdown import to_markdown
from app.services.transcription import format_timestamp


def export_payload(meeting: Meeting, minutes: MinutesDocument | None) -> dict:
    return {
        "meeting": {
            "id": meeting.id,
            "title": meeting.title,
            "meeting_date": meeting.meeting_date.isoformat() if meeting.meeting_date else None,
            "purpose": meeting.purpose,
            "original_filename": meeting.original_filename,
            "language": meeting.language,
            "whisper_model": meeting.whisper_model,
            "ollama_model": meeting.ollama_model,
            "noise_reduction_enabled": meeting.noise_reduction_enabled,
            "status": meeting.status,
            "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
        },
        "transcript": [
            {
                "id": item.id,
                "sequence": item.sequence,
                "start_time": item.start_time,
                "end_time": item.end_time,
                "text": item.text,
                "confidence": item.confidence,
                "needs_review": item.needs_review,
            }
            for item in meeting.transcript_segments
        ],
        "minutes": minutes.model_dump(mode="json") if minutes else None,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


def export_txt(meeting: Meeting, minutes: MinutesDocument | None) -> str:
    body = to_markdown(minutes) if minutes else f"# {meeting.title}\n\nMinutes have not been generated.\n"
    transcript = ["\n## Transcript\n"]
    transcript.extend(
        f"[{format_timestamp(segment.start_time)} - {format_timestamp(segment.end_time)}] {segment.text}"
        for segment in meeting.transcript_segments
    )
    return body + "\n" + "\n".join(transcript) + "\n"


def export_docx(meeting: Meeting, minutes: MinutesDocument | None) -> bytes:
    document = Document()
    document.add_heading(meeting.title, level=0)
    document.add_paragraph(f"Date: {meeting.meeting_date.isoformat() if meeting.meeting_date else 'Not supplied'}")
    document.add_paragraph(f"Purpose: {meeting.purpose or 'Not supplied'}")
    if minutes:
        document.add_heading("Executive summary", level=1)
        document.add_paragraph(minutes.executive_summary or "Not provided.")
        for title, items in (
            ("Main discussion points", minutes.main_discussion_points),
            ("Decisions", minutes.decisions_made),
            ("Risks and concerns", minutes.risks_and_concerns),
            ("Unresolved questions", minutes.unresolved_questions),
            ("Next steps", minutes.next_steps),
        ):
            document.add_heading(title, level=1)
            for item in items:
                document.add_paragraph(
                    f"{item.text} [evidence {format_timestamp(item.evidence_start_time)}–{format_timestamp(item.evidence_end_time)}]",
                    style="List Bullet",
                )
        document.add_heading("Action items", level=1)
        table = document.add_table(rows=1, cols=5)
        table.style = "Table Grid"
        for cell, label in zip(table.rows[0].cells, ("Action", "Owner", "Deadline", "Status", "Evidence")):
            cell.text = label
        for item in minutes.action_items:
            cells = table.add_row().cells
            cells[0].text = item.text
            cells[1].text = item.owner or "—"
            cells[2].text = item.deadline or "—"
            cells[3].text = item.status
            cells[4].text = f"{format_timestamp(item.evidence_start_time)}–{format_timestamp(item.evidence_end_time)}"
        if minutes.generation_warnings:
            document.add_heading("Generation warnings", level=1)
            for warning in minutes.generation_warnings:
                document.add_paragraph(warning, style="List Bullet")
    document.add_heading("Transcript", level=1)
    for segment in meeting.transcript_segments:
        document.add_paragraph(
            f"[{format_timestamp(segment.start_time)} - {format_timestamp(segment.end_time)}] {segment.text}"
        )
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
