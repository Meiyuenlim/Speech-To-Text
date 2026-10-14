from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.meeting import Meeting, MeetingMinutes, TranscriptSegment
from app.schemas.meeting import EvidenceExtraction, MinutesDocument
from app.services.audio import AudioPipeline
from app.services.markdown import to_markdown
from app.services.ollama import (
    OllamaClient,
    OllamaUnavailable,
    evidence_prompt,
    evidence_schema,
    minutes_prompt,
    minutes_schema,
    validate_with_retry,
)
from app.services.transcription import TranscriptionService, chunk_segments


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobCancelled(RuntimeError):
    pass


class ProcessingManager:
    """A persisted, single-worker queue suitable for a single-user desktop app."""

    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="meeting-job")
        self.futures: dict[str, Future] = {}
        self.cancelled: set[str] = set()
        self.lock = threading.Lock()

    def enqueue(self, meeting_id: str, regenerate_only: bool = False) -> None:
        with self.lock:
            self.cancelled.discard(meeting_id)
            future = self.executor.submit(self._run, meeting_id, regenerate_only)
            self.futures[meeting_id] = future

    def cancel(self, meeting_id: str) -> bool:
        with self.lock:
            self.cancelled.add(meeting_id)
            future = self.futures.get(meeting_id)
            return bool(future and future.cancel())

    def _check_cancelled(self, meeting_id: str) -> None:
        if meeting_id in self.cancelled:
            raise JobCancelled("Processing cancelled by the user")

    def _set_status(
        self,
        db: Session,
        meeting: Meeting,
        status: str,
        progress: int,
        message: str,
    ) -> None:
        meeting.status = status
        meeting.progress = progress
        meeting.status_message = message
        meeting.updated_at = _now()
        db.commit()

    def _add_warning(self, meeting: Meeting, warning: str) -> None:
        warnings = json.loads(meeting.warnings_json or "[]")
        if warning not in warnings:
            warnings.append(warning)
        meeting.warnings_json = json.dumps(warnings, ensure_ascii=False)

    def _fail(self, db: Session, meeting: Meeting, error: str) -> None:
        meeting.status = "failed"
        meeting.progress = 100
        meeting.error_message = error
        meeting.status_message = "Processing failed"
        meeting.processing_finished_at = _now()
        meeting.updated_at = _now()
        db.commit()

    def _run(self, meeting_id: str, regenerate_only: bool) -> None:
        db = SessionLocal()
        meeting = db.get(Meeting, meeting_id)
        if not meeting:
            db.close()
            return
        meeting.error_message = None
        meeting.processing_started_at = _now()
        meeting.processing_finished_at = None
        meeting.warnings_json = "[]"
        db.commit()
        try:
            if regenerate_only:
                self._generate_minutes(db, meeting)
            else:
                self._process_recording(db, meeting)
        except JobCancelled as exc:
            self._fail(db, meeting, str(exc))
        except Exception as exc:
            self._fail(db, meeting, str(exc))
        finally:
            db.close()

    def _process_recording(self, db: Session, meeting: Meeting) -> None:
        if not meeting.original_audio_path:
            raise RuntimeError("Upload a recording before starting processing")
        self._check_cancelled(meeting.id)
        source = Path(meeting.original_audio_path)
        if not source.exists():
            raise RuntimeError("The uploaded recording is missing from local storage")
        pipeline = AudioPipeline()
        converted = settings.processed_dir / f"{meeting.id}-original-48khz.wav"
        enhanced = settings.processed_dir / f"{meeting.id}-enhanced-48khz.wav"
        selected = settings.processed_dir / f"{meeting.id}-selected-16khz.wav"
        self._set_status(db, meeting, "preparing_audio", 10, "Converting the original recording to mono WAV")
        pipeline.convert_to_wav(source, converted, 48000)
        duration = pipeline.duration_seconds(converted)
        if duration is not None and duration > settings.max_recording_minutes * 60:
            raise RuntimeError(
                f"The recording is longer than the configured {settings.max_recording_minutes}-minute limit"
            )
        meeting.converted_audio_path = str(converted)
        db.commit()
        self._check_cancelled(meeting.id)

        selected_source = converted
        if meeting.noise_reduction_enabled:
            self._set_status(db, meeting, "reducing_noise", 25, "Trying optional DeepFilterNet noise reduction")
            try:
                pipeline.enhance_with_deepfilter(converted, enhanced)
                meeting.enhanced_audio_path = str(enhanced)
                selected_source = enhanced
            except Exception as exc:
                self._add_warning(meeting, f"Noise reduction was unavailable; the original WAV was used ({exc}).")
                meeting.enhanced_audio_path = None
                db.commit()
        else:
            self._set_status(db, meeting, "reducing_noise", 25, "Noise reduction disabled; using original WAV")
        pipeline.convert_to_wav(selected_source, selected, 16000)
        meeting.selected_audio_path = str(selected)
        db.commit()
        self._check_cancelled(meeting.id)

        service = TranscriptionService()
        device, compute_type = service.runtime()
        meeting.device = device
        meeting.compute_type = compute_type
        self._set_status(db, meeting, "transcribing", 40, f"Transcribing locally with {meeting.whisper_model}")
        rows, detected_language, device, compute_type = service.transcribe(
            selected,
            meeting.whisper_model,
            meeting.language,
            meeting.glossary,
            progress=lambda value: self._set_status(db, meeting, "transcribing", value, "Transcribing locally"),
        )
        meeting.device = device
        meeting.compute_type = compute_type
        if meeting.language == "auto" and detected_language:
            meeting.language = detected_language
        for old in list(meeting.transcript_segments):
            db.delete(old)
        db.flush()
        for row in rows:
            db.add(
                TranscriptSegment(
                    id=str(uuid.uuid4()), meeting_id=meeting.id, **row
                )
            )
        db.commit()
        # The deletion loop loaded this relationship before inserting the new
        # rows by foreign key. With expire_on_commit=False it still contains the
        # old (often empty) list. Reload it before generating minutes.
        db.expire(meeting, ["transcript_segments"])
        self._check_cancelled(meeting.id)
        self._generate_minutes(db, meeting)

    def _generate_minutes(self, db: Session, meeting: Meeting) -> None:
        segments = [
            {
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "text": segment.text,
            }
            for segment in meeting.transcript_segments
        ]
        if not segments:
            raise RuntimeError("No transcript segments were produced; review the recording and try again")
        client = OllamaClient()
        self._set_status(db, meeting, "extracting_evidence", 70, "Extracting timestamped evidence with Ollama")
        evidence: list[dict] = []
        warnings: list[str] = json.loads(meeting.warnings_json or "[]")
        client.ensure_model(meeting.ollama_model)
        for chunk in chunk_segments(segments):
            self._check_cancelled(meeting.id)
            try:
                extraction, retry_warnings = validate_with_retry(
                    client, meeting.ollama_model, evidence_prompt(chunk), EvidenceExtraction, evidence_schema()
                )
                evidence.append(extraction.model_dump(mode="json"))
                warnings.extend(item for item in retry_warnings if item not in warnings)
            except Exception as exc:
                warnings.append(f"Evidence extraction failed for one transcript chunk: {exc}")
        self._set_status(db, meeting, "generating_minutes", 85, "Generating editable meeting minutes")
        try:
            minutes, retry_warnings = validate_with_retry(
                client,
                meeting.ollama_model,
                minutes_prompt(
                    meeting.title,
                    meeting.meeting_date.isoformat() if meeting.meeting_date else None,
                    meeting.purpose,
                    evidence,
                ),
                MinutesDocument,
                minutes_schema(),
            )
            warnings.extend(item for item in retry_warnings if item not in warnings)
        except Exception as exc:
            warnings.append(f"Final minutes validation failed: {exc}")
            minutes = MinutesDocument(
                meeting_title=meeting.title,
                meeting_date=meeting.meeting_date.isoformat() if meeting.meeting_date else None,
                meeting_purpose=meeting.purpose,
                generation_warnings=warnings,
            )
        minutes.generation_warnings = list(dict.fromkeys(warnings + minutes.generation_warnings))
        existing = db.query(MeetingMinutes).filter(MeetingMinutes.meeting_id == meeting.id).one_or_none()
        if existing:
            existing.minutes_json = json.dumps(minutes.model_dump(mode="json"), ensure_ascii=False)
            existing.minutes_markdown = to_markdown(minutes)
            existing.updated_at = _now()
            existing.approved = False
        else:
            db.add(
                MeetingMinutes(
                    id=str(uuid.uuid4()),
                    meeting_id=meeting.id,
                    minutes_json=json.dumps(minutes.model_dump(mode="json"), ensure_ascii=False),
                    minutes_markdown=to_markdown(minutes),
                )
            )
        meeting.warnings_json = json.dumps(minutes.generation_warnings, ensure_ascii=False)
        meeting.status = "completed"
        meeting.progress = 100
        meeting.status_message = "Processing complete"
        meeting.processing_finished_at = _now()
        meeting.updated_at = _now()
        db.commit()


processing_manager = ProcessingManager()
