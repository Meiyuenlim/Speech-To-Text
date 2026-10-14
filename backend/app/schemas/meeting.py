from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Language = Literal["auto", "en", "zh", "ms"]
WhisperModel = Literal["small", "medium", "large-v3", "large-v3-turbo"]
JobStatus = Literal[
    "uploaded",
    "preparing_audio",
    "reducing_noise",
    "transcribing",
    "extracting_evidence",
    "generating_minutes",
    "completed",
    "failed",
]


class MeetingCreate(BaseModel):
    title: str = Field(default="Untitled meeting", min_length=1, max_length=200)
    meeting_date: date | None = None
    purpose: str | None = Field(default=None, max_length=5000)
    language: Language = "auto"
    whisper_model: WhisperModel = "large-v3-turbo"
    ollama_model: str = Field(default="qwen3:8b", min_length=1, max_length=120)
    noise_reduction_enabled: bool = True
    glossary: str | None = Field(default=None, max_length=5000)


class MeetingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    meeting_date: date | None = None
    purpose: str | None = Field(default=None, max_length=5000)


class TranscriptSegmentInput(BaseModel):
    id: str | None = None
    sequence: int = Field(ge=0)
    start_time: float = Field(ge=0)
    end_time: float = Field(ge=0)
    text: str = Field(min_length=1, max_length=10000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    needs_review: bool = False

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, value: float, info: Any) -> float:
        start = info.data.get("start_time")
        if start is not None and value < start:
            raise ValueError("end_time must be greater than or equal to start_time")
        return value


class TranscriptUpdate(BaseModel):
    segments: list[TranscriptSegmentInput]


class EvidenceItem(BaseModel):
    text: str
    evidence_start_time: float = Field(ge=0)
    evidence_end_time: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    source_excerpt: str


class ActionItem(EvidenceItem):
    owner: str | None = None
    deadline: str | None = None
    status: str = "open"


class EvidenceExtraction(BaseModel):
    key_discussion_points: list[EvidenceItem] = Field(default_factory=list)
    decisions: list[EvidenceItem] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    deadlines: list[EvidenceItem] = Field(default_factory=list)
    risks: list[EvidenceItem] = Field(default_factory=list)
    problems_raised: list[EvidenceItem] = Field(default_factory=list)
    proposed_solutions: list[EvidenceItem] = Field(default_factory=list)
    unresolved_questions: list[EvidenceItem] = Field(default_factory=list)
    important_factual_statements: list[EvidenceItem] = Field(default_factory=list)


class MinutesDocument(BaseModel):
    meeting_title: str = "Untitled meeting"
    meeting_date: str | None = None
    meeting_purpose: str | None = None
    executive_summary: str = ""
    main_discussion_points: list[EvidenceItem] = Field(default_factory=list)
    decisions_made: list[EvidenceItem] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    risks_and_concerns: list[EvidenceItem] = Field(default_factory=list)
    unresolved_questions: list[EvidenceItem] = Field(default_factory=list)
    next_steps: list[EvidenceItem] = Field(default_factory=list)
    next_meeting_date: str | None = None
    generation_warnings: list[str] = Field(default_factory=list)


class MinutesUpdate(BaseModel):
    minutes: MinutesDocument
    markdown: str | None = None


class MinutesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    meeting_id: str
    minutes: MinutesDocument
    markdown: str
    approved: bool
    created_at: datetime
    updated_at: datetime


class TranscriptSegmentResponse(TranscriptSegmentInput):
    model_config = ConfigDict(from_attributes=True)

    id: str


class MeetingSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    meeting_date: date | None
    original_filename: str | None
    status: str
    progress: int
    status_message: str | None
    created_at: datetime
    updated_at: datetime


class MeetingResponse(MeetingSummary):
    purpose: str | None
    language: str
    whisper_model: str
    ollama_model: str
    noise_reduction_enabled: bool
    device: str | None
    compute_type: str | None
    warnings: list[str]
    original_audio_url: str | None = None
    enhanced_audio_url: str | None = None
    selected_audio_url: str | None = None
    transcript: list[TranscriptSegmentResponse] = Field(default_factory=list)
    minutes: MinutesResponse | None = None


class JobStatusResponse(BaseModel):
    id: str
    status: str
    progress: int
    status_message: str | None
    error_message: str | None
    device: str | None
    compute_type: str | None
    warnings: list[str]
    processing_started_at: datetime | None
    processing_finished_at: datetime | None


class OllamaStatus(BaseModel):
    available: bool
    model_installed: bool
    message: str


class SystemCheckResponse(BaseModel):
    ffmpeg_available: bool
    deepfilternet_available: bool
    ollama_available: bool
    selected_ollama_model: str
    selected_ollama_model_available: bool
    cuda_available: bool
    whisper_device: str
    whisper_compute_type: str
    available_disk_space_bytes: int
    messages: list[str] = Field(default_factory=list)
