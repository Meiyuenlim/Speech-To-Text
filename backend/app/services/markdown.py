from __future__ import annotations

from app.schemas.meeting import ActionItem, EvidenceItem, MinutesDocument
from app.services.transcription import format_timestamp


def evidence_line(item: EvidenceItem) -> str:
    return f"- {item.text} _(evidence {format_timestamp(item.evidence_start_time)}–{format_timestamp(item.evidence_end_time)})_"


def to_markdown(minutes: MinutesDocument) -> str:
    lines = [f"# {minutes.meeting_title}"]
    if minutes.meeting_date:
        lines.append(f"**Date:** {minutes.meeting_date}")
    if minutes.meeting_purpose:
        lines.append(f"**Purpose:** {minutes.meeting_purpose}")
    lines.extend(["", "## Executive summary", minutes.executive_summary or "Not provided.", "", "## Main discussion points"])
    lines.extend([evidence_line(item) for item in minutes.main_discussion_points] or ["- None recorded."])
    lines.extend(["", "## Decisions made"])
    lines.extend([evidence_line(item) for item in minutes.decisions_made] or ["- None recorded."])
    lines.extend(["", "## Action items"])
    if minutes.action_items:
        lines.append("| Action | Owner | Deadline | Status | Evidence |\n| --- | --- | --- | --- | --- |")
        for item in minutes.action_items:
            evidence = f"{format_timestamp(item.evidence_start_time)}–{format_timestamp(item.evidence_end_time)}"
            lines.append(f"| {item.text} | {item.owner or '—'} | {item.deadline or '—'} | {item.status} | {evidence} |")
    else:
        lines.append("- None recorded.")
    for title, items in (
        ("Risks and concerns", minutes.risks_and_concerns),
        ("Unresolved questions", minutes.unresolved_questions),
        ("Next steps", minutes.next_steps),
    ):
        lines.extend(["", f"## {title}"])
        lines.extend([evidence_line(item) for item in items] or ["- None recorded."])
    if minutes.next_meeting_date:
        lines.extend(["", f"**Next meeting:** {minutes.next_meeting_date}"])
    if minutes.generation_warnings:
        lines.extend(["", "## Generation warnings", *[f"- {warning}" for warning in minutes.generation_warnings]])
    return "\n".join(lines).strip() + "\n"
