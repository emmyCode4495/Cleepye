import type { JobDetail, JobSummary, MineInput, MineResponse } from "./types";
import { BRAND, ENGINE_START_HINT } from "./brand";

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

const OFFLINE_MESSAGE = `Can't reach the ${BRAND} engine. Start it with \`${ENGINE_START_HINT}\` and try again.`;

function detailToMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{ loc, msg, type }]
    return detail.map((d) => (typeof d?.msg === "string" ? d.msg : JSON.stringify(d))).join("; ");
  }
  return null;
}

async function readError(res: Response): Promise<ApiError> {
  // Vite's dev proxy answers 500/502/504 with an empty body when the engine is down.
  let body: any = null;
  try {
    body = await res.json();
  } catch {
    /* empty body */
  }
  const msg = detailToMessage(body?.detail);
  if (!msg && res.status >= 500) return new ApiError(OFFLINE_MESSAGE, { status: res.status, offline: true });
  return new ApiError(msg ?? `Request failed (${res.status})`, { status: res.status });
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { signal, headers: { Accept: "application/json" } });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(OFFLINE_MESSAGE, { offline: true });
  }
  if (!res.ok) throw await readError(res);
  return res.json() as Promise<T>;
}

export const api = {
  jobs: async (signal?: AbortSignal) => (await getJson<{ jobs: JobSummary[] }>("/api/jobs?limit=200", signal)).jobs ?? [],
  job: (id: string, signal?: AbortSignal) => getJson<JobDetail>(`/api/jobs/${encodeURIComponent(id)}`, signal),
  styles: async (signal?: AbortSignal) =>
    (await getJson<{ styles: Array<{ id: string; name: string }> }>("/api/styles", signal)).styles ?? [],
  async health(timeoutMs = 4000): Promise<boolean> {
    try {
      const res = await fetch("/health", { cache: "no-store", signal: AbortSignal.timeout(timeoutMs) });
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
}

/**
 * Starts a mine. The engine answers only when the whole pipeline has finished,
 * so this promise can stay pending for many minutes. For uploads we use XHR to
 * get real byte-level progress; URL jobs use plain fetch.
 */
export function mine(input: MineInput, hooks: MineHooks): Promise<MineResponse> {
  return input.kind === "url" ? mineUrl(input, hooks) : mineUpload(input, hooks);
}

async function mineUrl(input: Extract<MineInput, { kind: "url" }>, { signal }: MineHooks): Promise<MineResponse> {
  let res: Response;
  try {
    res = await fetch("/api/process/url", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: input.url, max_clips: input.maxClips, caption_style: input.style }),
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(OFFLINE_MESSAGE, { offline: true });
  }
  if (!res.ok) throw await readError(res);
  return res.json();
}

function mineUpload(input: Extract<MineInput, { kind: "file" }>, hooks: MineHooks): Promise<MineResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", input.file);
    form.append("max_clips", String(input.maxClips));
    form.append("caption_style", input.style);

    const abort = () => xhr.abort();
    hooks.signal.addEventListener("abort", abort, { once: true });
    const cleanup = () => hooks.signal.removeEventListener("abort", abort);

    xhr.open("POST", "/api/process/upload");
    xhr.responseType = "text";
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (e) => e.lengthComputable && hooks.onUploadProgress?.(e.loaded, e.total);
    xhr.upload.onload = () => hooks.onUploadDone?.();
    xhr.onerror = () => {
      cleanup();
      reject(new ApiError(OFFLINE_MESSAGE, { offline: true }));
    };
    xhr.onabort = () => {
      cleanup();
      reject(new DOMException("Aborted", "AbortError"));
    };
    xhr.onload = () => {
      cleanup();
      let body: any = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* non-JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300 && body) return resolve(body as MineResponse);
      const msg = detailToMessage(body?.detail);
      if (!msg && xhr.status >= 500) return reject(new ApiError(OFFLINE_MESSAGE, { status: xhr.status, offline: true }));
      reject(new ApiError(msg ?? `Request failed (${xhr.status})`, { status: xhr.status }));
    };
    xhr.send(form);
  });
}
