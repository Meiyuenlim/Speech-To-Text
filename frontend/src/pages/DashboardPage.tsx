import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { ErrorState, LoadingState } from "../components/LoadingState";
import { StatusBadge } from "../components/StatusBadge";
import type { MeetingSummary } from "../types";
import { formatDate } from "../utils/format";

export function DashboardPage() {
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const refresh = () => api.listMeetings().then(setMeetings).catch((err: Error) => setError(err.message)).finally(() => setLoading(false));
  useEffect(() => { void refresh(); }, []);

  async function deleteMeeting(id: string) {
    if (!window.confirm("Delete this meeting and its local audio files? This cannot be undone.")) return;
    try { await api.deleteMeeting(id); setMeetings((items) => items.filter((item) => item.id !== id)); } catch (err) { setError((err as Error).message); }
  }

  return <section>
    <div className="page-heading">
      <div><p className="eyebrow">Workspace</p><h1>Meetings</h1><p className="muted">Review local recordings, transcripts, and evidence-backed minutes.</p></div>
      <Link className="button" to="/new">+ New meeting</Link>
    </div>
    {error && <ErrorState message={error} />}
    {loading ? <LoadingState label="Loading meetings" /> : meetings.length === 0 ? <div className="empty-state"><div className="empty-icon">▣</div><h2>No meetings yet</h2><p>Upload a recording to create your first private meeting workspace.</p><Link className="button" to="/new">Create a meeting</Link></div> :
      <div className="meeting-list">{meetings.map((meeting) => <article className="meeting-card" key={meeting.id}>
        <div className="meeting-card-main"><div className="meeting-icon">◷</div><div><h2>{meeting.title}</h2><p className="muted">{formatDate(meeting.meeting_date)} {meeting.original_filename ? `· ${meeting.original_filename}` : "· No recording uploaded"}</p></div></div>
        <div className="meeting-card-meta"><StatusBadge status={meeting.status} /><span className="muted">Updated {formatDate(meeting.updated_at)}</span></div>
        <div className="meeting-card-actions"><button className="button button-ghost" onClick={() => navigate(`/meetings/${meeting.id}/${meeting.status === "completed" ? "review" : "process"}`)}>Open</button><button className="text-button danger-text" onClick={() => void deleteMeeting(meeting.id)}>Delete</button></div>
      </article>)}</div>}
  </section>;
}
