import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

export function NewMeetingPage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [meetingDate, setMeetingDate] = useState("");
  const [purpose, setPurpose] = useState("");
  const [language, setLanguage] = useState("auto");
  const [whisperModel, setWhisperModel] = useState("large-v3-turbo");
  const [ollamaModel, setOllamaModel] = useState("qwen3:8b");
  const [glossary, setGlossary] = useState("");
  const [noiseReduction, setNoiseReduction] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) return setError("Add a meeting title.");
    if (!file) return setError("Choose an MP3, WAV, or M4A recording.");
    if (!/\.(mp3|wav|m4a)$/i.test(file.name)) return setError("Only MP3, WAV, and M4A recordings are supported.");
    setSaving(true); setError("");
    try {
      const meeting = await api.createMeeting({ title: title.trim(), meeting_date: meetingDate || undefined, purpose: purpose || undefined, language, whisper_model: whisperModel, ollama_model: ollamaModel, noise_reduction_enabled: noiseReduction, glossary: glossary || undefined });
      await api.upload(meeting.id, file);
      await api.process(meeting.id);
      navigate(`/meetings/${meeting.id}/process`);
    } catch (err) { setError((err as Error).message); setSaving(false); }
  }

  return <section className="narrow-page">
    <div className="page-heading"><div><p className="eyebrow">New workspace</p><h1>Start a meeting</h1><p className="muted">The recording is kept locally and is never sent to a cloud AI service.</p></div></div>
    <form className="card form-card" onSubmit={submit}>
      {error && <div className="inline-error" role="alert">{error}</div>}
      <div className="form-grid"><label>Meeting title<input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Product planning" required /></label><label>Meeting date<input type="date" value={meetingDate} onChange={(e) => setMeetingDate(e.target.value)} /></label></div>
      <label>Purpose <span className="label-hint">Optional</span><textarea rows={3} value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="What should this meeting accomplish?" /></label>
      <label className="file-drop"><span className="upload-symbol">↑</span><strong>{file ? file.name : "Choose a meeting recording"}</strong><span className="muted">MP3, WAV or M4A · up to 500 MB</span><input type="file" accept=".mp3,.wav,.m4a,audio/mpeg,audio/wav,audio/mp4" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
      <div className="section-rule"><span>Processing settings</span></div>
      <div className="form-grid"><label>Language<select value={language} onChange={(e) => setLanguage(e.target.value)}><option value="auto">Auto-detect</option><option value="en">English</option><option value="zh">Chinese</option><option value="ms">Malay</option></select></label><label>Whisper model<select value={whisperModel} onChange={(e) => setWhisperModel(e.target.value)}><option>small</option><option>medium</option><option>large-v3</option><option>large-v3-turbo</option></select></label></div>
      <label>Ollama model<input value={ollamaModel} onChange={(e) => setOllamaModel(e.target.value)} /></label>
      <label>Glossary <span className="label-hint">Optional · names, acronyms, technical terms</span><textarea rows={2} value={glossary} onChange={(e) => setGlossary(e.target.value)} /></label>
      <label className="checkbox-row"><input type="checkbox" checked={noiseReduction} onChange={(e) => setNoiseReduction(e.target.checked)} /><span><strong>Enable noise reduction</strong><small>DeepFilterNet is optional. The original audio is always preserved.</small></span></label>
      <div className="form-actions"><button type="button" className="button button-ghost" onClick={() => navigate(-1)}>Cancel</button><button className="button" disabled={saving}>{saving ? "Preparing…" : "Process meeting"}</button></div>
    </form>
  </section>;
}
