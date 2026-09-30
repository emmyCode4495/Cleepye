import type { Clip } from "./types";

export function timecode(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const mm = String(m).padStart(h ? 2 : 1, "0");
  const ss = String(sec).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/** Always mm:ss (or h:mm:ss) — for running timers where width shouldn't jump. */
export function clock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function humanDuration(totalSeconds: number | null | undefined): string {
  if (totalSeconds == null || Number.isNaN(totalSeconds)) return "—";
  const s = Math.round(totalSeconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h) return `${h}h ${m}m`;
  if (m) return `${m}m ${s % 60}s`;
  return `${s}s`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v >= 100 ? v.toFixed(0) : v.toFixed(1)} ${units[i]}`;
}

/**
 * The API returns ISO strings that are usually timezone-naive.
 * We treat naive values as UTC (SQLAlchemy `utcnow` convention).
 * If your backend stores local time instead, drop the "Z" suffix below.
 */
export function parseServerDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(value);
  const d = new Date(hasZone ? value : `${value.replace(" ", "T")}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function relativeTime(date: Date | null): string {
  if (!date) return "—";
  const diff = (Date.now() - date.getTime()) / 1000;
  if (diff < 45) return "just now";
  if (diff < 90) return "a minute ago";
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)} h ago`;
  if (diff < 86400 * 2) return "yesterday";
  if (diff < 86400 * 7) return `${Math.round(diff / 86400)} days ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function dayBucket(date: Date | null): string {
  if (!date) return "Earlier";
  const start = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((start(new Date()) - start(date)) / 86400000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return date.toLocaleDateString(undefined, { weekday: "long" });
  return date.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" });
}

export function fileNameFromPath(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path;
}

/** Human-friendly label for a job's source (URL host/path or original filename). */
export function sourceLabel(source: string, sourceType?: string): string {
  if (!source) return "Untitled source";
  if (sourceType === "url" || /^https?:\/\//i.test(source)) {
    try {
      const u = new URL(source);
      const host = u.hostname.replace(/^www\./, "");
      const id = u.searchParams.get("v");
      const tail = id ?? u.pathname.replace(/\/$/, "");
      return tail && tail !== "/" ? `${host}${id ? " · " : ""}${tail}` : host;
    } catch {
      return source;
    }
  }
  return fileNameFromPath(source).replace(/^upload_/, "");
}

export function isUrlSource(source: string, sourceType?: string) {
  return sourceType === "url" || /^https?:\/\//i.test(source);
}

/** Works with both POSIX and Windows separators stored by the backend. */
export function clipUrl(jobId: string, clip: Clip): string {
  return `/api/clips/${encodeURIComponent(jobId)}/${encodeURIComponent(fileNameFromPath(clip.path))}`;
}

export function detectPlatform(raw: string): string | null {
  try {
    const host = new URL(raw).hostname.replace(/^www\./, "");
    if (/(^|\.)(youtube\.com|youtu\.be)$/.test(host)) return "YouTube";
    if (/vimeo\.com$/.test(host)) return "Vimeo";
    if (/(^|\.)(twitter\.com|x\.com)$/.test(host)) return "X";
    if (/tiktok\.com$/.test(host)) return "TikTok";
    if (/twitch\.tv$/.test(host)) return "Twitch";
    if (/facebook\.com|fb\.watch$/.test(host)) return "Facebook";
    if (/instagram\.com$/.test(host)) return "Instagram";
    return host;
  } catch {
    return null;
  }
}

export function isValidHttpUrl(raw: string): boolean {
  try {
    const u = new URL(raw);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}


/** Extract a YouTube video id from common URL shapes, or null. */
export function youtubeVideoId(raw: string): string | null {
  try {
    const u = new URL(raw);
    const host = u.hostname.replace(/^www\./, "");
    if (host === "youtu.be") {
      const id = u.pathname.split("/").filter(Boolean)[0];
      return id || null;
    }
    if (host === "youtube.com" || host.endsWith(".youtube.com")) {
      if (u.searchParams.get("v")) return u.searchParams.get("v");
      const parts = u.pathname.split("/").filter(Boolean);
      // /embed/ID, /shorts/ID, /live/ID
      if (parts.length >= 2 && ["embed", "shorts", "live", "v"].includes(parts[0])) {
        return parts[1] || null;
      }
    }
  } catch {
    /* ignore */
  }
  return null;
}

/** Best-effort public thumbnail for a video URL (YouTube only for now). */
export function linkThumbnailUrl(raw: string): string | null {
  const id = youtubeVideoId(raw);
  if (id) return `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
  return null;
}

export type ScoreTier = "prime" | "strong" | "fair";
export function scoreTier(score: number): { tier: ScoreTier; label: string; color: string } {
  if (score >= 80) return { tier: "prime", label: "Prime", color: "rgb(var(--lime))" };
  if (score >= 60) return { tier: "strong", label: "Strong", color: "rgb(var(--amber))" };
  return { tier: "fair", label: "Fair", color: "rgb(var(--coral))" };
}
