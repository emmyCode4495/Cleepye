export interface Clip {
  index: number;
  path: string;
  start: number;
  end: number;
  duration: number;
  score: number;
  title: string;
  hook: string;
  caption_style: string;
}

/** Row returned by GET /api/jobs */
export interface JobSummary {
  id: string;
  source_type: string;
  source: string;
  status: string;
  stage?: string;
  progress?: number;
  message?: string;
  duration: number | null;
  candidates_found: number;
  clips_rendered: number;
  caption_style: string;
  created_at: string | null;
}

/** Payload returned by GET /api/jobs/:id */
export interface JobDetail {
  id: string;
  source: string;
  source_type?: string;
  status: string;
  stage?: string;
  progress?: number;
  message?: string;
  duration: number | null;
  candidates_found: number;
  clips_rendered: number;
  caption_style: string;
  created_at?: string | null;
  error?: string | null;
  clips: Clip[];
}

export interface MineResponse {
  job_id: string;
  status: string;
  message: string;
}

export type MineInput =
  | { kind: "url"; url: string; maxClips: number; style: string; fontId?: string | null }
  | { kind: "file"; file: File; maxClips: number; style: string; fontId?: string | null };
