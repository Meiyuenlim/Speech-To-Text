import type { JobStatus, Meeting, MeetingSummary, MinutesResponse, MinutesDocument, TranscriptSegment } from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Keep the HTTP status when the response is not JSON.
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export type NewMeetingInput = {
  title: string;
  meeting_date?: string;
  purpose?: string;
  language: string;
  whisper_model: string;
  ollama_model: string;
  noise_reduction_enabled: boolean;
  glossary?: string;
};

export const api = {
  listMeetings: () => request<MeetingSummary[]>("/meetings"),
  getMeeting: (id: string) => request<Meeting>(`/meetings/${id}`),
  createMeeting: (input: NewMeetingInput) => request<Meeting>("/meetings", { method: "POST", body: JSON.stringify(input) }),
  upload: (id: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<Meeting>(`/meetings/${id}/upload`, { method: "POST", body });
  },
  process: (id: string) => request<JobStatus>(`/meetings/${id}/process`, { method: "POST" }),
  cancel: (id: string) => request<JobStatus>(`/meetings/${id}/cancel`, { method: "POST" }),
  status: (id: string) => request<JobStatus>(`/meetings/${id}/status`),
  updateTranscript: (id: string, segments: TranscriptSegment[]) => request<TranscriptSegment[]>(`/meetings/${id}/transcript`, { method: "PUT", body: JSON.stringify({ segments }) }),
  regenerateMinutes: (id: string) => request<JobStatus>(`/meetings/${id}/regenerate-minutes`, { method: "POST" }),
  updateMinutes: (id: string, minutes: MinutesDocument) => request<MinutesResponse>(`/meetings/${id}/minutes`, { method: "PUT", body: JSON.stringify({ minutes }) }),
  approveMinutes: (id: string) => request<MinutesResponse>(`/meetings/${id}/approve`, { method: "POST" }),
  deleteMeeting: (id: string) => request<void>(`/meetings/${id}`, { method: "DELETE" }),
};

export function fileUrl(path: string | null): string | null {
  if (!path) return null;
  return path.startsWith("http") ? path : `${API_BASE.replace(/\/api$/, "")}${path}`;
}

export function exportUrl(id: string, format: "docx" | "txt" | "json"): string {
  return `${API_BASE}/meetings/${id}/export/${format}`;
}
