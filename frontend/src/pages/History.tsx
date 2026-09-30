import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, FileVideo, Globe, Plus, Search, Film, Square, Loader2 } from "lucide-react";
import { EmptyState, ErrorState } from "../components/States";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { api, ApiError } from "../lib/api";
import { getLook } from "../lib/captionStyles";
import { dayBucket, humanDuration, isUrlSource, parseServerDate, relativeTime, sourceLabel } from "../lib/format";
import type { JobSummary } from "../lib/types";
import { useToast } from "../context/ToastContext";
import { useNotice } from "../context/NoticeContext";

type Sort = "newest" | "oldest" | "clips";

function isRunning(status: string | undefined) {
  return status === "running" || status === "pending" || status === "queued";
}

function Row({
  job,
  onCancel,
  cancelling,
}: {
  job: JobSummary;
  onCancel: (id: string) => void;
  cancelling: boolean;
}) {
  const look = getLook(job.caption_style);
  const url = isUrlSource(job.source, job.source_type);
  const running = isRunning(job.status);
  const cancelled = job.status === "cancelled";
  const failed = job.status === "failed";

  return (
    <div className="group surface flex items-center gap-4 p-4 transition hover:border-white/20 hover:bg-ink-2 sm:gap-5 sm:p-5">
      <Link
        to={`/jobs/${job.id}`}
        className="grid h-14 w-14 shrink-0 place-items-center rounded-xl border bg-lime/[0.07] text-center"
      >
        <div>
          <p className="font-display text-xl font-bold leading-none text-lime">{job.clips_rendered}</p>
          <p className="mt-0.5 font-mono text-[9px] uppercase tracking-widest text-dim">clips</p>
        </div>
      </Link>

      <Link to={`/jobs/${job.id}`} className="min-w-0 flex-1">
        <p className="truncate font-medium">{sourceLabel(job.source, job.source_type)}</p>
        <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-dim">
          {url ? <Globe className="h-3.5 w-3.5" /> : <FileVideo className="h-3.5 w-3.5" />}
          <span>{relativeTime(parseServerDate(job.created_at))}</span>
          <span aria-hidden>·</span>
          <span>{humanDuration(job.duration)} source</span>
          {running && job.progress != null && (
            <>
              <span aria-hidden>·</span>
              <span className="text-amber">{Math.round(job.progress)}%</span>
            </>
          )}
          {running && job.message && (
            <>
              <span aria-hidden className="hidden sm:inline">
                ·
              </span>
              <span className="hidden max-w-[14rem] truncate sm:inline">{job.message}</span>
            </>
          )}
        </p>
      </Link>

      {running && (
        <span className="chip border-amber/30 text-amber capitalize">
          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          {job.stage || job.status}
        </span>
      )}
      {cancelled && <span className="chip border-white/15 text-dim">Cancelled</span>}
      {failed && <span className="chip border-coral/30 text-coral">Failed</span>}

      <span className="chip hidden md:inline-flex">
        <span
          className="h-2 w-2 rounded-full"
          style={{ background: look.highlight === "#ffffff" ? look.primary : look.highlight }}
        />
        {look.name}
      </span>

      <span className="hidden font-mono text-xs text-dim lg:block">{job.id}</span>

      {running ? (
        <button
          type="button"
          disabled={cancelling}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onCancel(job.id);
          }}
          className="btn-ghost shrink-0 border border-coral/30 text-coral hover:bg-coral/10"
          title="Cancel this job"
        >
          {cancelling ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Square className="h-3.5 w-3.5" />
          )}
          <span className="ml-1.5 hidden sm:inline">Cancel</span>
        </button>
      ) : (
        <Link to={`/jobs/${job.id}`} className="text-dim group-hover:text-bone">
          <ChevronRight className="h-5 w-5" />
        </Link>
      )}
    </div>
  );
}

export default function History() {
  useDocumentTitle("History");
  const { push } = useToast();
  const notice = useNotice();
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<Sort>("newest");
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const jobs = useAsync((s) => api.jobs(s), []);
  const hasRunning = (jobs.data ?? []).some((j) => isRunning(j.status));

  const filtered = useMemo(() => {
    let list = [...(jobs.data ?? [])];
    const query = q.trim().toLowerCase();
    if (query) {
      list = list.filter(
        (j) =>
          j.id.toLowerCase().includes(query) ||
          (j.source || "").toLowerCase().includes(query) ||
          (j.status || "").toLowerCase().includes(query)
      );
    }
    if (sort === "newest") list.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    if (sort === "oldest") list.sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
    if (sort === "clips") list.sort((a, b) => (b.clips_rendered || 0) - (a.clips_rendered || 0));
    return list;
  }, [jobs.data, q, sort]);

  const grouped = useMemo(() => {
    const map = new Map<string, JobSummary[]>();
    for (const j of filtered) {
      const key = dayBucket(parseServerDate(j.created_at));
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(j);
    }
    return [...map.entries()];
  }, [filtered]);

  const onCancel = useCallback(
    async (id: string) => {
      setCancellingId(id);
      try {
        await api.cancelJob(id);
        push({ title: "Job cancelled", description: `Stopped ${id}` });
        jobs.reload();
      } catch (e) {
        notice.error(
          "Could not cancel",
          e instanceof ApiError ? e.message : "Something went wrong. Try again.",
        );
      } finally {
        setCancellingId(null);
      }
    },
    [jobs, push, notice]
  );

  useEffect(() => {
    if (!hasRunning) return;
    const id = window.setInterval(() => {
      jobs.reload();
    }, 2500);
    return () => window.clearInterval(id);
  }, [hasRunning, jobs.reload]);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight">History</h1>
          <p className="mt-1 text-sm text-muted">Past mines, running jobs, and exports on this machine.</p>
        </div>
        <Link to="/" className="btn-primary inline-flex items-center gap-2 self-start">
          <Plus className="h-4 w-4" /> New mine
        </Link>
      </div>

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-dim" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by source, status, or id…"
            className="field pl-10"
          />
        </div>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as Sort)}
          className="field w-full sm:w-40"
          aria-label="Sort"
        >
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="clips">Most clips</option>
        </select>
      </div>

      {jobs.error && (
        <ErrorState
          error={jobs.error instanceof ApiError ? jobs.error.message : "Something went wrong"}
          offline={jobs.error instanceof ApiError ? jobs.error.offline : false}
          onRetry={() => jobs.reload()}
        />
      )}

      {!jobs.error && !jobs.loading && filtered.length === 0 && (
        <EmptyState
          icon={<Film className="h-6 w-6" />}
          title="No mines yet"
          body="Run your first mine from the home page. Jobs and clips will show up here."
          action={{ label: "Start mining", to: "/" }}
        />
      )}

      <div className="space-y-8">
        {grouped.map(([bucket, items]) => (
          <section key={bucket}>
            <h2 className="mb-3 font-mono text-xs uppercase tracking-widest text-dim">{bucket}</h2>
            <div className="space-y-3">
              {items.map((job) => (
                <Row
                  key={job.id}
                  job={job}
                  onCancel={onCancel}
                  cancelling={cancellingId === job.id}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
