import { useEffect, useMemo, useRef, useState } from "react";
import type { TranscriptSegment } from "../types";
import { createTranscriptDocument, editTranscriptDocument, transcriptSegmentsForSave } from "../utils/transcript";

type Props = {
  segments: TranscriptSegment[];
  onSave: (segments: TranscriptSegment[]) => Promise<void>;
  onRegenerate: () => Promise<void>;
  onDirtyChange: (dirty: boolean) => void;
  regenerating: boolean;
};

export function TranscriptDocument({ segments, onSave, onRegenerate, onDirtyChange, regenerating }: Props) {
  const original = useMemo(() => createTranscriptDocument(segments), [segments]);
  const [document, setDocument] = useState(original);
  const [editing, setEditing] = useState(false);
  const [search, setSearch] = useState("");
  const [activeMatch, setActiveMatch] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const readerRef = useRef<HTMLDivElement>(null);
  const dirty = document.text !== original.text;

  useEffect(() => { setDocument(original); setError(""); }, [original]);
  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => { setActiveMatch(0); }, [search, document.text]);

  const matches = useMemo(() => {
    if (!search) return [];
    const escaped = search.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return Array.from(document.text.matchAll(new RegExp(escaped, "giu")), match => ({
      start: match.index!, end: match.index! + match[0].length,
    }));
  }, [search, document.text]);

  useEffect(() => {
    readerRef.current?.querySelector("mark.current-match")?.scrollIntoView?.({ block: "nearest" });
  }, [activeMatch, matches, editing]);

  async function save() {
    if (saving || !dirty || !document.text.trim()) return;
    setSaving(true);
    setError("");
    try {
      await onSave(transcriptSegmentsForSave(document));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return <div className="card transcript-card">
    <div className="card-heading">
      <div><h2>Transcript</h2><p className="muted">Read the full conversation in one document, or edit it to make corrections.</p></div>
      <button className="button button-ghost button-small" disabled={saving || segments.length === 0} onClick={() => setEditing(!editing)}>
        {editing ? "Reading view" : "Edit transcript"}
      </button>
    </div>
    {!editing && segments.length > 0 && <div className="transcript-toolbar">
      <input type="search" className="search-input" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search transcript" aria-label="Search transcript" />
      {search && <>
        <span className="muted transcript-match-count" role="status">{matches.length ? `${activeMatch + 1} of ${matches.length} matches` : "No matches"}</span>
        <button className="button button-ghost button-small" disabled={!matches.length} onClick={() => setActiveMatch((activeMatch - 1 + matches.length) % matches.length)}>Previous match</button>
        <button className="button button-ghost button-small" disabled={!matches.length} onClick={() => setActiveMatch((activeMatch + 1) % matches.length)}>Next match</button>
      </>}
    </div>}
    {segments.length === 0 ? <div className="empty-inline">No transcript is available yet.</div> : editing ? <textarea
      className="transcript-document-editor"
      aria-label="Full transcript"
      value={document.text}
      disabled={saving}
      onChange={event => { const text = event.target.value; setDocument(current => editTranscriptDocument(current, text)); setError(""); }}
    /> : <div className="transcript-document-reader" role="region" aria-label="Full transcript" tabIndex={0} ref={readerRef}>
      {matches.length ? <>{matches.map((match, index) => <span key={match.start}>
        {document.text.slice(index === 0 ? 0 : matches[index - 1].end, match.start)}
        <mark className={index === activeMatch ? "current-match" : ""}>{document.text.slice(match.start, match.end)}</mark>
      </span>)}{document.text.slice(matches[matches.length - 1].end)}</> : document.text}
    </div>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    <div className="transcript-footer">
      <p className="muted" role="status">{dirty ? (document.text.trim() ? "Unsaved corrections. Save before regenerating minutes." : "The transcript is empty. Add text before saving.") : "Corrections are used the next time you generate minutes."}</p>
      <div className="button-row">
        {(editing || dirty) && <button className="button" disabled={saving || !dirty || !document.text.trim()} onClick={() => void save()}>{saving ? "Saving…" : "Save corrections"}</button>}
        <button className="button button-ghost" disabled={saving || dirty || !document.text.trim() || regenerating} onClick={() => void onRegenerate()}>{regenerating ? "Minutes regeneration queued" : "Regenerate minutes"}</button>
      </div>
    </div>
  </div>;
}
