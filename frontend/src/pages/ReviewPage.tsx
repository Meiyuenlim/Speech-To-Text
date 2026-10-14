import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, exportUrl, fileUrl } from "../api/client";
import { ErrorState, LoadingState } from "../components/LoadingState";
import { TranscriptDocument } from "../components/TranscriptDocument";
import type { Meeting, MinutesDocument, TranscriptSegment } from "../types";
import { formatDate, formatTimestamp } from "../utils/format";

type Tab = "transcript" | "minutes" | "audio" | "details";

export function ReviewPage() {
  const { id = "" } = useParams();
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [tab, setTab] = useState<Tab>("transcript");
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [minutes, setMinutes] = useState<MinutesDocument | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [transcriptDirty, setTranscriptDirty] = useState(false);
  const regenerationPending = useRef(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    let cancelled = false;
    setMeeting(null); setError(""); setMessage(""); setTranscriptDirty(false);
    regenerationPending.current = false; setRegenerating(false);
    api.getMeeting(id).then((result) => {
      if (cancelled) return;
      setMeeting(result); setSegments(result.transcript); setMinutes(result.minutes?.minutes ?? null);
      const busy = ["preparing_audio", "reducing_noise", "transcribing", "extracting_evidence", "generating_minutes"].includes(result.status);
      regenerationPending.current = busy; setRegenerating(busy);
    }).catch((err: Error) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [id]);
  if (error && !meeting) return <ErrorState message={error} />;
  if (!meeting) return <LoadingState label="Loading review workspace" />;

  async function saveTranscript(updated: TranscriptSegment[]) { const saved = await api.updateTranscript(id, updated); setSegments(saved); setMessage("Transcript corrections saved."); }
  async function saveMinutes() { try { const saved = await api.updateMinutes(id, minutes!); setMinutes(saved.minutes); setMessage("Minutes saved as an editable draft."); } catch (err) { setError((err as Error).message); } }
  async function regenerate() {
    if (regenerationPending.current || transcriptDirty) return;
    regenerationPending.current = true;
    setRegenerating(true);
    setError("");
    setMessage("");
    try { await api.regenerateMinutes(id); setMessage("Minutes regeneration queued. Check the processing page for progress."); }
    catch (err) { regenerationPending.current = false; setRegenerating(false); setError((err as Error).message); }
  }
  async function approve() { try { await api.approveMinutes(id); setMessage("Minutes approved."); } catch (err) { setError((err as Error).message); } }
  function playAt(seconds: number) { if (audioRef.current) { audioRef.current.currentTime = seconds; void audioRef.current.play(); } }
  function updateEvidence(field: keyof MinutesDocument, index: number, key: string, value: string) { setMinutes((current) => { if (!current) return current; const items = [...(current[field] as Array<Record<string, unknown>>)].map((item) => ({ ...item })); items[index][key] = value; return { ...current, [field]: items }; }); }

  return <section>
    <Link className="back-link" to="/">← All meetings</Link>
    <div className="page-heading compact-heading"><div><p className="eyebrow">Review workspace</p><h1>{meeting.title}</h1><p className="muted">{formatDate(meeting.meeting_date)} · {meeting.original_filename} · {meeting.device ?? "Device not recorded"}</p></div><div className="button-row">{["docx", "txt", "json"].map((format) => <a className="button button-ghost button-small" href={exportUrl(id, format as "docx" | "txt" | "json")} key={format}>Export {format.toUpperCase()}</a>)}</div></div>
    {message && <div className="success-note" role="status">{message}</div>}{error && <ErrorState message={error} />}
    <div className="tabs" role="tablist">{([["transcript", "Transcript"], ["minutes", "Meeting minutes"], ["audio", "Audio comparison"], ["details", "Processing details"]] as [Tab, string][]).map(([value, label]) => <button className={tab === value ? "active" : ""} onClick={() => setTab(value)} role="tab" aria-selected={tab === value} key={value}>{label}</button>)}</div>
    <div hidden={tab !== "transcript"}><TranscriptDocument key={id} segments={segments} onSave={saveTranscript} onRegenerate={regenerate} onDirtyChange={setTranscriptDirty} regenerating={regenerating} /></div>
    {regenerating && <p><Link className="evidence-link" to={`/meetings/${id}/process`}>View minutes generation progress →</Link></p>}
    {tab === "minutes" && !minutes && <div className="card"><h2>Minutes have not been generated yet</h2><p>Your saved transcript is available in the Transcript tab. You can generate minutes from it without transcribing the recording again.</p>{transcriptDirty && <p className="muted">Save your transcript corrections before generating minutes.</p>}<button className="button" disabled={segments.length === 0 || regenerating || transcriptDirty} onClick={() => void regenerate()}>{regenerating ? "Minutes regeneration queued" : "Regenerate minutes"}</button></div>}
    {tab === "minutes" && minutes && <div className="card minutes-card"><div className="card-heading"><div><h2>Editable meeting minutes</h2><p className="muted">Evidence timestamps are retained so every claim can be checked against the transcript.</p></div><span className={`approval-label ${meeting.minutes?.approved ? "approved" : ""}`}>{meeting.minutes?.approved ? "Approved" : "Draft"}</span></div><label>Title<input value={minutes.meeting_title} onChange={(e) => setMinutes({ ...minutes, meeting_title: e.target.value })} /></label><label>Executive summary<textarea rows={5} value={minutes.executive_summary} onChange={(e) => setMinutes({ ...minutes, executive_summary: e.target.value })} /></label>{([ ["main_discussion_points", "Main discussion points"], ["decisions_made", "Decisions made"], ["risks_and_concerns", "Risks and concerns"], ["unresolved_questions", "Unresolved questions"], ["next_steps", "Next steps"]] as [keyof MinutesDocument, string][]).map(([field, label]) => <section className="editable-list" key={field}><h3>{label}</h3>{(minutes[field] as Array<{ text: string; evidence_start_time: number; evidence_end_time: number }>).length === 0 ? <p className="muted">None recorded.</p> : (minutes[field] as Array<{ text: string; evidence_start_time: number; evidence_end_time: number }>).map((item, index) => <div className="evidence-editor" key={`${field}-${index}`}><textarea value={item.text} onChange={(e) => updateEvidence(field, index, "text", e.target.value)} /><button className="evidence-link" onClick={() => playAt(item.evidence_start_time)}>⌁ {formatTimestamp(item.evidence_start_time)}–{formatTimestamp(item.evidence_end_time)}</button></div>)}</section>)}<section className="editable-list"><h3>Action items</h3>{minutes.action_items.map((item, index) => <div className="action-editor" key={`action-${index}`}><textarea value={item.text} onChange={(e) => updateEvidence("action_items", index, "text", e.target.value)} /><input value={item.owner ?? ""} placeholder="Owner (optional)" onChange={(e) => updateEvidence("action_items", index, "owner", e.target.value)} /><input value={item.deadline ?? ""} placeholder="Deadline (optional)" onChange={(e) => updateEvidence("action_items", index, "deadline", e.target.value)} /><button className="evidence-link" onClick={() => playAt(item.evidence_start_time)}>⌁ {formatTimestamp(item.evidence_start_time)}</button></div>)}</section><div className="form-actions"><button className="button" onClick={() => void saveMinutes()}>Save minutes</button><button className="button button-ghost" onClick={() => void approve()}>Approve minutes</button></div></div>}
    {tab === "audio" && <div className="audio-grid"><div className="card audio-card"><h2>Original recording</h2><p className="muted">The uploaded recording, preserved unchanged.</p>{fileUrl(meeting.original_audio_url) && <audio ref={audioRef} controls src={fileUrl(meeting.original_audio_url) ?? undefined} />}</div><div className="card audio-card"><h2>Enhanced recording</h2><p className="muted">DeepFilterNet output, when available.</p>{meeting.enhanced_audio_url ? <audio controls src={fileUrl(meeting.enhanced_audio_url) ?? undefined} /> : <div className="empty-inline">No enhanced recording was produced. The original WAV was used.</div>}</div></div>}
    {tab === "details" && <div className="details-grid"><div className="card"><h2>Processing details</h2><dl className="detail-list"><dt>Whisper model</dt><dd>{meeting.whisper_model}</dd><dt>Ollama model</dt><dd>{meeting.ollama_model}</dd><dt>Device</dt><dd>{meeting.device ?? "—"} · {meeting.compute_type ?? "—"}</dd><dt>Noise reduction</dt><dd>{meeting.noise_reduction_enabled ? "Enabled" : "Disabled"}</dd><dt>Warnings</dt><dd>{meeting.warnings.length ? meeting.warnings.join(" ") : "None"}</dd></dl></div><div className="card"><h2>Local processing notes</h2><p className="muted">No audio or transcript content is sent to external AI services. Ollama and faster-whisper run on this computer.</p></div></div>}
    <audio ref={tab === "audio" ? undefined : audioRef} src={fileUrl(meeting.original_audio_url) ?? undefined} preload="metadata" hidden />
  </section>;
}
