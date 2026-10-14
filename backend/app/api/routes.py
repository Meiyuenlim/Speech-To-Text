from __future__ import annotations

import json
import shutil
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.meeting import Meeting, MeetingMinutes, TranscriptSegment
from app.schemas.meeting import (
    JobStatusResponse,
    MeetingCreate,
    MeetingResponse,
    MeetingSummary,
    MeetingUpdate,
    MinutesDocument,
    MinutesResponse,
    MinutesUpdate,
    SystemCheckResponse,
    TranscriptSegmentResponse,
    TranscriptUpdate,
)
from app.services.exporter import export_docx, export_payload, export_txt
from app.services.files import ALLOWED_MIME_TYPES, internal_audio_filename, sanitize_filename, validate_audio_filename
from app.services.markdown import to_markdown
from app.services.processor import processing_manager
from app.services.system import system_check


router = APIRouter(prefix="/api")


def _meeting_or_404(meeting_id: str, db: Session) -> Meeting:
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


def _warnings(meeting: Meeting) -> list[str]:
    try:
        return json.loads(meeting.warnings_json or "[]")
    except json.JSONDecodeError:
        return [meeting.warnings_json or "Unknown processing warning"]


def _minutes_response(minutes: MeetingMinutes | None) -> MinutesResponse | None:
    if not minutes:
        return None
    try:
        document = MinutesDocument.model_validate(json.loads(minutes.minutes_json))
    except (ValueError, json.JSONDecodeError):
        document = MinutesDocument(generation_warnings=["Stored minutes JSON could not be validated."])
    return MinutesResponse(
        id=minutes.id,
        meeting_id=minutes.meeting_id,
        minutes=document,
        markdown=minutes.minutes_markdown,
        approved=minutes.approved,
        created_at=minutes.created_at,
        updated_at=minutes.updated_at,
    )


def _detail(meeting: Meeting) -> MeetingResponse:
    return MeetingResponse(
        id=meeting.id,
        title=meeting.title,
        meeting_date=meeting.meeting_date,
        original_filename=meeting.original_filename,
        status=meeting.status,
        progress=meeting.progress,
        status_message=meeting.status_message,
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
        purpose=meeting.purpose,
        language=meeting.language,
        whisper_model=meeting.whisper_model,
        ollama_model=meeting.ollama_model,
        noise_reduction_enabled=meeting.noise_reduction_enabled,
        device=meeting.device,
        compute_type=meeting.compute_type,
        warnings=_warnings(meeting),
        original_audio_url=f"/api/meetings/{meeting.id}/audio/original" if meeting.original_audio_path else None,
        enhanced_audio_url=f"/api/meetings/{meeting.id}/audio/enhanced" if meeting.enhanced_audio_path else None,
        selected_audio_url=f"/api/meetings/{meeting.id}/audio/selected" if meeting.selected_audio_path else None,
        transcript=[TranscriptSegmentResponse.model_validate(segment) for segment in meeting.transcript_segments],
        minutes=_minutes_response(meeting.minutes),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "local-only"}


@router.get("/system-check", response_model=SystemCheckResponse)
def get_system_check(model: str | None = None) -> dict:
    return system_check(model)


@router.post("/meetings", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def create_meeting(payload: MeetingCreate, db: Session = Depends(get_db)) -> MeetingResponse:
    meeting = Meeting(id=str(uuid.uuid4()), **payload.model_dump())
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return _detail(meeting)


@router.get("/meetings", response_model=list[MeetingSummary])
def list_meetings(db: Session = Depends(get_db)) -> list[MeetingSummary]:
    meetings = db.query(Meeting).order_by(Meeting.updated_at.desc()).all()
    return [MeetingSummary.model_validate(meeting) for meeting in meetings]


@router.get("/meetings/{meeting_id}", response_model=MeetingResponse)
def get_meeting(meeting_id: str, db: Session = Depends(get_db)) -> MeetingResponse:
    return _detail(_meeting_or_404(meeting_id, db))


@router.patch("/meetings/{meeting_id}", response_model=MeetingResponse)
def update_meeting(meeting_id: str, payload: MeetingUpdate, db: Session = Depends(get_db)) -> MeetingResponse:
    meeting = _meeting_or_404(meeting_id, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(meeting, key, value)
    db.commit()
    db.refresh(meeting)
    return _detail(meeting)


@router.delete("/meetings/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(meeting_id: str, db: Session = Depends(get_db)) -> Response:
    meeting = _meeting_or_404(meeting_id, db)
    for raw_path in (meeting.original_audio_path, meeting.converted_audio_path, meeting.enhanced_audio_path, meeting.selected_audio_path):
        if raw_path:
            path = Path(raw_path)
            if path.is_file() and path.is_relative_to(settings.data_dir):
                path.unlink(missing_ok=True)
    db.delete(meeting)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/meetings/{meeting_id}/upload", response_model=MeetingResponse)
def upload_audio(meeting_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)) -> MeetingResponse:
    meeting = _meeting_or_404(meeting_id, db)
    try:
        extension = validate_audio_filename(file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="The uploaded MIME type is not a supported audio type")
    settings.ensure_directories()
    destination = settings.uploads_dir / internal_audio_filename(extension)
    with destination.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if destination.stat().st_size > max_bytes:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail=f"Recordings must be smaller than {settings.max_upload_mb} MB")
    meeting.original_filename = sanitize_filename(file.filename or "recording" )
    meeting.original_audio_path = str(destination)
    meeting.status = "uploaded"
    meeting.progress = 0
    meeting.status_message = "Recording uploaded and ready to process"
    db.commit()
    db.refresh(meeting)
    return _detail(meeting)


@router.post("/meetings/{meeting_id}/process", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED)
def process_meeting(meeting_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    meeting = _meeting_or_404(meeting_id, db)
    if not meeting.original_audio_path:
        raise HTTPException(status_code=400, detail="Upload an audio recording first")
    if meeting.status in {"preparing_audio", "reducing_noise", "transcribing", "extracting_evidence", "generating_minutes"}:
        raise HTTPException(status_code=409, detail="This meeting is already being processed")
    meeting.status = "preparing_audio"
    meeting.status_message = "Queued for local processing"
    meeting.progress = 1
    db.commit()
    processing_manager.enqueue(meeting.id)
    return JobStatusResponse(
        id=meeting.id,
        status=meeting.status,
        progress=meeting.progress,
        status_message=meeting.status_message,
        error_message=meeting.error_message,
        device=meeting.device,
        compute_type=meeting.compute_type,
        warnings=_warnings(meeting),
        processing_started_at=meeting.processing_started_at,
        processing_finished_at=meeting.processing_finished_at,
    )


@router.post("/meetings/{meeting_id}/cancel", response_model=JobStatusResponse)
def cancel_meeting(meeting_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    meeting = _meeting_or_404(meeting_id, db)
    processing_manager.cancel(meeting.id)
    meeting.status = "failed"
    meeting.error_message = "Processing cancelled by the user"
    meeting.status_message = "Processing cancelled"
    db.commit()
    return get_status(meeting_id, db)


@router.get("/meetings/{meeting_id}/status", response_model=JobStatusResponse)
def get_status(meeting_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    meeting = _meeting_or_404(meeting_id, db)
    return JobStatusResponse(
        id=meeting.id,
        status=meeting.status,
        progress=meeting.progress,
        status_message=meeting.status_message,
        error_message=meeting.error_message,
        device=meeting.device,
        compute_type=meeting.compute_type,
        warnings=_warnings(meeting),
        processing_started_at=meeting.processing_started_at,
        processing_finished_at=meeting.processing_finished_at,
    )


@router.get("/meetings/{meeting_id}/transcript", response_model=list[TranscriptSegmentResponse])
def get_transcript(meeting_id: str, db: Session = Depends(get_db)) -> list[TranscriptSegmentResponse]:
    meeting = _meeting_or_404(meeting_id, db)
    return [TranscriptSegmentResponse.model_validate(segment) for segment in meeting.transcript_segments]


@router.put("/meetings/{meeting_id}/transcript", response_model=list[TranscriptSegmentResponse])
def update_transcript(meeting_id: str, payload: TranscriptUpdate, db: Session = Depends(get_db)) -> list[TranscriptSegmentResponse]:
    meeting = _meeting_or_404(meeting_id, db)
    meeting.transcript_segments.clear()
    for segment in payload.segments:
        data = segment.model_dump(exclude={"id"})
        meeting.transcript_segments.append(TranscriptSegment(id=str(uuid.uuid4()), meeting_id=meeting.id, **data))
    db.commit()
    db.refresh(meeting)
    return [TranscriptSegmentResponse.model_validate(segment) for segment in meeting.transcript_segments]


@router.get("/meetings/{meeting_id}/minutes", response_model=MinutesResponse | None)
def get_minutes(meeting_id: str, db: Session = Depends(get_db)) -> MinutesResponse | None:
    meeting = _meeting_or_404(meeting_id, db)
    return _minutes_response(meeting.minutes)


@router.put("/meetings/{meeting_id}/minutes", response_model=MinutesResponse)
def update_minutes(meeting_id: str, payload: MinutesUpdate, db: Session = Depends(get_db)) -> MinutesResponse:
    meeting = _meeting_or_404(meeting_id, db)
    minutes = meeting.minutes
    markdown = payload.markdown or to_markdown(payload.minutes)
    if minutes:
        minutes.minutes_json = json.dumps(payload.minutes.model_dump(mode="json"), ensure_ascii=False)
        minutes.minutes_markdown = markdown
        minutes.approved = False
    else:
        minutes = MeetingMinutes(
            id=str(uuid.uuid4()), meeting_id=meeting.id,
            minutes_json=json.dumps(payload.minutes.model_dump(mode="json"), ensure_ascii=False),
            minutes_markdown=markdown,
        )
        db.add(minutes)
    db.commit()
    db.refresh(minutes)
    return _minutes_response(minutes)  # type: ignore[return-value]


@router.post("/meetings/{meeting_id}/regenerate-minutes", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED)
def regenerate_minutes(meeting_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    meeting = _meeting_or_404(meeting_id, db)
    if not meeting.transcript_segments:
        raise HTTPException(status_code=400, detail="A transcript is required before generating minutes")
    processing_manager.enqueue(meeting.id, regenerate_only=True)
    meeting.status = "extracting_evidence"
    meeting.progress = 65
    meeting.status_message = "Queued to regenerate minutes from the current transcript"
    db.commit()
    return get_status(meeting_id, db)


@router.post("/meetings/{meeting_id}/approve", response_model=MinutesResponse)
def approve_minutes(meeting_id: str, db: Session = Depends(get_db)) -> MinutesResponse:
    meeting = _meeting_or_404(meeting_id, db)
    if not meeting.minutes:
        raise HTTPException(status_code=400, detail="Generate or save minutes before approving")
    meeting.minutes.approved = True
    db.commit()
    db.refresh(meeting.minutes)
    return _minutes_response(meeting.minutes)  # type: ignore[return-value]


@router.get("/meetings/{meeting_id}/audio/{kind}")
def get_audio(meeting_id: str, kind: str, db: Session = Depends(get_db)) -> FileResponse:
    meeting = _meeting_or_404(meeting_id, db)
    paths = {"original": meeting.original_audio_path, "enhanced": meeting.enhanced_audio_path, "selected": meeting.selected_audio_path}
    raw_path = paths.get(kind)
    if not raw_path:
        raise HTTPException(status_code=404, detail="Audio variant not available")
    path = Path(raw_path)
    if not path.is_file() or not path.is_relative_to(settings.data_dir):
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(path, media_type="audio/wav" if path.suffix == ".wav" else "audio/mpeg", filename=path.name)


@router.get("/meetings/{meeting_id}/export/json")
def export_json(meeting_id: str, db: Session = Depends(get_db)) -> JSONResponse:
    meeting = _meeting_or_404(meeting_id, db)
    minutes = MinutesDocument.model_validate(json.loads(meeting.minutes.minutes_json)) if meeting.minutes else None
    return JSONResponse(content=export_payload(meeting, minutes), headers={"Content-Disposition": f'attachment; filename="{meeting.id}-meeting.json"'})


@router.get("/meetings/{meeting_id}/export/txt")
def export_text(meeting_id: str, db: Session = Depends(get_db)) -> Response:
    meeting = _meeting_or_404(meeting_id, db)
    minutes = MinutesDocument.model_validate(json.loads(meeting.minutes.minutes_json)) if meeting.minutes else None
    return Response(export_txt(meeting, minutes), media_type="text/plain", headers={"Content-Disposition": f'attachment; filename="{meeting.id}-meeting.txt"'})


@router.get("/meetings/{meeting_id}/export/docx")
def export_word(meeting_id: str, db: Session = Depends(get_db)) -> Response:
    meeting = _meeting_or_404(meeting_id, db)
    minutes = MinutesDocument.model_validate(json.loads(meeting.minutes.minutes_json)) if meeting.minutes else None
    return Response(
        export_docx(meeting, minutes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{meeting.id}-meeting.docx"'},
    )
