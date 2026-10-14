import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ErrorState, LoadingState } from "../components/LoadingState";
import { stageLabels } from "../types";
import type { JobStatus, Meeting } from "../types";

export function ProcessingPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try { const [current, status] = await Promise.all([api.getMeeting(id), api.status(id)]); if (active) { setMeeting(current); setJob(status); if (status.status === "completed") navigate(`/meetings/${id}/review`, { replace: true }); } }
      catch (err) { if (active) setError((err as Error).message); }
    };
    void poll(); const timer = window.setInterval(() => void poll(), 1800);
    return () => { active = false; window.clearInterval(timer); };
  }, [id, navigate]);

  async function cancel() { try { setJob(await api.cancel(id)); } catch (err) { setError((err as Error).message); } }
  if (error) return <ErrorState message={error} />;
  if (!meeting || !job) return <LoadingState label="Loading processing status" />;
  const processing = !["completed", "failed"].includes(job.status);
  return <section className="narrow-page">
    <Link className="back-link" to="/">← All meetings</Link>
    <div className="page-heading compact-heading"><div><p className="eyebrow">Processing</p><h1>{meeting.title}</h1><p className="muted">{meeting.original_filename}</p></div>{processing && <button className="button button-ghost" onClick={() => void cancel()}>Cancel</button>}</div>
    <div className="card processing-card"><div className="processing-visual"><div className={`processing-ring ${job.status === "failed" ? "ring-failed" : ""}`}><span>{job.progress}%</span></div><div><h2>{stageLabels[job.status]}</h2><p className="muted">{job.status_message ?? "Working locally…"}</p></div></div><div className="progress-track"><div className="progress-fill" style={{ width: `${job.progress}%` }} /></div><div className="processing-meta"><span>Whisper <strong>{meeting.whisper_model}</strong></span><span>Device <strong>{job.device ?? "Detecting…"}{job.compute_type ? ` · ${job.compute_type}` : ""}</strong></span></div>{job.error_message && <div className="inline-error"><strong>{job.error_message}</strong><span>Check the setup notes for the missing local dependency, then try again.</span></div>}{job.warnings.map((warning) => <div className="warning-note" key={warning}>⚠ {warning}</div>)}{job.status === "failed" && <div className="form-actions"><Link className="button button-ghost" to={`/meetings/${id}/review`}>Open review</Link><Link className="button" to="/new">Try another recording</Link></div>}</div>
    <div className="card info-card"><h3>What happens next</h3><p>Audio is converted locally, optionally enhanced, transcribed with faster-whisper, and summarized by your local Ollama model. Long-running work continues in the background.</p></div>
  </section>;
}
