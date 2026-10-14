export type MeetingStatus =
  | "uploaded"
  | "preparing_audio"
  | "reducing_noise"
  | "transcribing"
  | "extracting_evidence"
  | "generating_minutes"
  | "completed"
  | "failed";

export type EvidenceItem = {
  text: string;
  evidence_start_time: number;
  evidence_end_time: number;
  confidence: number;
  source_excerpt: string;
};

export type ActionItem = EvidenceItem & {
  owner: string | null;
  deadline: string | null;
  status: string;
};

export type MinutesDocument = {
  meeting_title: string;
  meeting_date: string | null;
  meeting_purpose: string | null;
  executive_summary: string;
  main_discussion_points: EvidenceItem[];
  decisions_made: EvidenceItem[];
  action_items: ActionItem[];
  risks_and_concerns: EvidenceItem[];
  unresolved_questions: EvidenceItem[];
  next_steps: EvidenceItem[];
  next_meeting_date: string | null;
  generation_warnings: string[];
};

export type TranscriptSegment = {
  id: string;
  sequence: number;
  start_time: number;
  end_time: number;
  text: string;
  confidence: number | null;
  needs_review: boolean;
};

export type MinutesResponse = {
  id: string;
  meeting_id: string;
  minutes: MinutesDocument;
  markdown: string;
  approved: boolean;
  created_at: string;
  updated_at: string;
};

export type MeetingSummary = {
  id: string;
  title: string;
  meeting_date: string | null;
  original_filename: string | null;
  status: MeetingStatus;
  progress: number;
  status_message: string | null;
  created_at: string;
  updated_at: string;
};

export type Meeting = MeetingSummary & {
  purpose: string | null;
  language: string;
  whisper_model: string;
  ollama_model: string;
  noise_reduction_enabled: boolean;
  device: string | null;
  compute_type: string | null;
  warnings: string[];
  original_audio_url: string | null;
  enhanced_audio_url: string | null;
  selected_audio_url: string | null;
  transcript: TranscriptSegment[];
  minutes: MinutesResponse | null;
};

export type JobStatus = {
  id: string;
  status: MeetingStatus;
  progress: number;
  status_message: string | null;
  error_message: string | null;
  device: string | null;
  compute_type: string | null;
  warnings: string[];
  processing_started_at: string | null;
  processing_finished_at: string | null;
};

export const stageLabels: Record<string, string> = {
  uploaded: "Ready to process",
  preparing_audio: "Preparing audio",
  reducing_noise: "Reducing background noise",
  transcribing: "Transcribing locally",
  extracting_evidence: "Extracting timestamped evidence",
  generating_minutes: "Generating meeting minutes",
  completed: "Complete",
  failed: "Needs attention",
};
