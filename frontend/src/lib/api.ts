import type { JobDetail, JobSummary, MineInput, MineResponse } from "./types";
import { BRAND, ENGINE_START_HINT } from "./brand";

/** Hosted API origin when frontend is on Vercel (no trailing slash). Empty = same origin. */
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "";
export function apiUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

/** Optional bearer token provider (wired from AuthContext). */
let accessTokenProvider: (() => string | null) | null = null;
export function setAccessTokenProvider(fn: (() => string | null) | null) {
  accessTokenProvider = fn;
}
function authHeaders(base: Record<string, string> = {}): Record<string, string> {
  const token = accessTokenProvider?.();
  if (token) return { ...base, Authorization: `Bearer ${token}` };
  return base;
}

export class ApiError extends Error {
  status?: number;
  offline: boolean;
  constructor(message: string, opts: { status?: number; offline?: boolean } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = opts.status;
    this.offline = !!opts.offline;
  }
}

const OFFLINE_MESSAGE = API_BASE
  ? `Can't reach the ${BRAND} API at ${API_BASE}. Check that the server is deployed and VITE_API_URL is correct.`
  : `Can't reach the ${BRAND} engine. Start it with \`${ENGINE_START_HINT}\` and try again.`;

function detailToMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (typeof d?.msg === "string" ? d.msg : JSON.stringify(d))).join("; ");
  }
  return null;
}

async function readError(res: Response): Promise<ApiError> {
  let body: any = null;
  try {
    body = await res.json();
  } catch {
    /* empty */
  }
  const msg = detailToMessage(body?.detail);
  if (!msg && res.status >= 500) return new ApiError(OFFLINE_MESSAGE, { status: res.status, offline: true });
  return new ApiError(msg ?? `Request failed (${res.status})`, { status: res.status });
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), { signal, headers: authHeaders({ Accept: "application/json" }) });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(OFFLINE_MESSAGE, { offline: true });
  }
  if (!res.ok) throw await readError(res);
  return res.json() as Promise<T>;
}

export const api = {
  me: async (signal?: AbortSignal) =>
    getJson<{
      user: { id: string; email?: string | null };
      profile: Record<string, unknown> | null;
      plan_limits?: {
        plan_id: string;
        name: string;
        max_clips_per_job: number;
        max_clips_ui: number;
        max_source_minutes: number;
        credits_per_month: number | null;
      } | null;
    }>("/api/me", signal),

  aspects: async (signal?: AbortSignal) =>
    (await getJson<{ aspects: Array<{ id: string; label: string; width: number; height: number }> }>("/api/aspects", signal)).aspects ?? [],

  plans: async (signal?: AbortSignal) =>
    getJson<{
      plans: Array<Record<string, unknown>>;
      packs?: unknown[];
      currency?: string;
      credit_rule?: string;
    }>("/api/plans", signal),

  fonts: async (signal?: AbortSignal) =>
    (await getJson<{ fonts: Array<{ id: string; name: string; filename: string; size?: number }> }>("/api/fonts", signal)).fonts ?? [],
  async uploadFont(file: File): Promise<{ id: string; name: string; filename: string }> {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(apiUrl("/api/fonts"), {
      method: "POST",
      headers: authHeaders(),
      body: form,
    });
    if (!res.ok) throw await readError(res);
    return res.json();
  },
  async deleteFont(id: string): Promise<void> {
    const res = await fetch(apiUrl(`/api/fonts/${encodeURIComponent(id)}`), {
      method: "DELETE",
      headers: authHeaders({ Accept: "application/json" }),
    });
    if (!res.ok) throw await readError(res);
  },

  async cancelJob(id: string, signal?: AbortSignal): Promise<{ job_id: string; status: string; message: string }> {
    let res: Response;
    try {
      res = await fetch(apiUrl(`/api/jobs/${encodeURIComponent(id)}/cancel`), {
        method: "POST",
        signal,
        headers: authHeaders({ Accept: "application/json" }),
      });
    } catch (e) {
      if ((e as Error).name === "AbortError") throw e;
      throw new ApiError(OFFLINE_MESSAGE, { offline: true });
    }
    if (!res.ok) throw await readError(res);
    return res.json();
  },

  jobs: async (signal?: AbortSignal) =>
    (await getJson<{ jobs: JobSummary[] }>("/api/jobs?limit=200", signal)).jobs ?? [],
  job: (id: string, signal?: AbortSignal) =>
    getJson<JobDetail>(`/api/jobs/${encodeURIComponent(id)}`, signal),
  styles: async (signal?: AbortSignal) =>
    (await getJson<{ styles: Array<{ id: string; name: string }> }>("/api/styles", signal)).styles ?? [],
  async health(timeoutMs = 4000): Promise<boolean> {
    try {
      const res = await fetch(apiUrl("/health"), { cache: "no-store", signal: AbortSignal.timeout(timeoutMs) });
      return res.ok;
    } catch {
      return false;
    }
  },
};

export interface MineHooks {
  signal: AbortSignal;
  onUploadProgress?: (loaded: number, total: number) => void;
  onUploadDone?: () => void;
  /** Called whenever the engine reports progress (0–100). */
  onProgress?: (info: { progress: number; stage: string; message: string; status: string }) => void;
}

async function sleep(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true }
    );
  });
}

/** Poll job until completed or failed. */
async function waitForJob(jobId: string, hooks: MineHooks): Promise<MineResponse> {
  while (true) {
    if (hooks.signal.aborted) throw new DOMException("Aborted", "AbortError");
    const job = await api.job(jobId, hooks.signal);
    const progress = job.progress ?? 0;
    const stage = job.stage ?? "processing";
    const message = job.message ?? "Working…";
    hooks.onProgress?.({ progress, stage, message, status: job.status });

    if (job.status === "completed") {
      return {
        job_id: jobId,
        status: "completed",
        message: message || `Rendered ${job.clips_rendered} clips`,
      };
    }
    if (job.status === "failed") {
      throw new ApiError(job.error || message || "Mining failed");
    }
    await sleep(1500, hooks.signal);
  }
}

/**
 * Starts a mine and polls for live progress until the job completes.
 */
export function mine(input: MineInput, hooks: MineHooks): Promise<MineResponse> {
  return input.kind === "url" ? mineUrl(input, hooks) : mineUpload(input, hooks);
}

async function mineUrl(input: Extract<MineInput, { kind: "url" }>, hooks: MineHooks): Promise<MineResponse> {
  let res: Response;
  try {
    res = await fetch(apiUrl("/api/process/url"), {
      method: "POST",
      signal: hooks.signal,
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        url: input.url,
        max_clips: input.maxClips,
        caption_style: input.style,
        font_id: input.fontId || null,
        min_clip_duration: input.minClipDuration ?? 15,
        max_clip_duration: input.maxClipDuration ?? 60,
        aspect_ratio: input.aspectRatio ?? "9:16",
      }),
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(OFFLINE_MESSAGE, { offline: true });
  }
  if (!res.ok) throw await readError(res);
  const accepted = (await res.json()) as MineResponse;
  hooks.onUploadDone?.();
  return waitForJob(accepted.job_id, hooks);
}

function mineUpload(input: Extract<MineInput, { kind: "file" }>, hooks: MineHooks): Promise<MineResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", input.file);
    form.append("max_clips", String(input.maxClips));
    form.append("caption_style", input.style);
    if (input.fontId) form.append("font_id", input.fontId);
    form.append("min_clip_duration", String(input.minClipDuration ?? 15));
    form.append("max_clip_duration", String(input.maxClipDuration ?? 60));
    form.append("aspect_ratio", input.aspectRatio ?? "9:16");

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) hooks.onUploadProgress?.(e.loaded, e.total);
    };

    xhr.onload = async () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          hooks.onUploadDone?.();
          const accepted = JSON.parse(xhr.responseText) as MineResponse;
          const result = await waitForJob(accepted.job_id, hooks);
          resolve(result);
        } catch (e) {
          reject(e);
        }
      } else {
        try {
          const body = JSON.parse(xhr.responseText);
          const msg = detailToMessage(body?.detail) || `Upload failed (${xhr.status})`;
          reject(new ApiError(msg, { status: xhr.status }));
        } catch {
          reject(new ApiError(`Upload failed (${xhr.status})`, { status: xhr.status }));
        }
      }
    };

    xhr.onerror = () => reject(new ApiError(OFFLINE_MESSAGE, { offline: true }));
    xhr.onabort = () => reject(new DOMException("Aborted", "AbortError"));

    hooks.signal.addEventListener("abort", () => xhr.abort(), { once: true });

    xhr.open("POST", apiUrl("/api/process/upload"));
    const token = accessTokenProvider?.();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.send(form);
  });
}
