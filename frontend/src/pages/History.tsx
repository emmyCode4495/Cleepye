import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, FileVideo, Globe, Plus, Search, Film } from "lucide-react";
import { EmptyState, ErrorState } from "../components/States";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { api, ApiError } from "../lib/api";
import { getLook } from "../lib/captionStyles";
import { cn } from "../lib/cn";
import { dayBucket, humanDuration, isUrlSource, parseServerDate, relativeTime, sourceLabel } from "../lib/format";
import type { JobSummary } from "../lib/types";

type Sort = "newest" | "oldest" | "clips";

function Row({ job }: { job: JobSummary }) {
  const look = getLook(job.caption_style);
  const url = isUrlSource(job.source, job.source_type);
  const done = job.status === "completed" || job.status === "done";
  return (
    <Link to={`/jobs/${job.id}`} className="group surface flex items-center gap-4 p-4 transition hover:border-white/20 hover:bg-ink-2 sm:gap-5 sm:p-5">
      <div className="grid h-14 w-14 shrink-0 place-items-center rounded-xl border bg-lime/[0.07] text-center">
        <div>
          <p className="font-display text-xl font-bold leading-none text-lime">{job.clips_rendered}</p>
          <p className="mt-0.5 font-mono text-[9px] uppercase tracking-widest text-dim">clips</p>
        </div>
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{sourceLabel(job.source, job.source_type)}</p>
        <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-dim">
          {url ? <Globe className="h-3.5 w-3.5" /> : <FileVideo className="h-3.5 w-3.5" />}
          <span>{relativeTime(parseServerDate(job.created_at))}</span>
          <span aria-hidden>·</span>
          <span>{humanDuration(job.duration)} source</span>
          <span aria-hidden className="hidden sm:inline">·</span>
          <span className="hidden sm:inline">{job.candidates_found} candidates</span>
        </p>
      </div>
      {!done && <span className="chip border-amber/30 text-amber capitalize">{job.status}</span>}
      <span className="chip hidden md:inline-flex">
        <span className="h-2 w-2 rounded-full" style={{ background: look.highlight === "#ffffff" ? look.primary : look.highlight }} />
        {look.name}
      </span>
      <span className="hidden font-mono text-xs text-dim lg:block">{job.id}</span>
      <ChevronRight className="h-5 w-5 shrink-0 text-dim transition group-hover:translate-x-0.5 group-hover:text-bone" />
    </Link>
  );
}

function Skeletons() {
  return (
    <div className="space-y-3" aria-busy>
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="skeleton h-[86px]" style={{ animationDelay: `${i * 120}ms` }} />
      ))}
    </div>
  );
}

export default function History() {
  useDocumentTitle("History");
  const { data, error, loading, reload } = useAsync((s) => api.jobs(s), []);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<Sort>("newest");

  const groups = useMemo(() => {
    const term = q.trim().toLowerCase();
    const list = (data ?? []).filter(
      (j) => !term || `${sourceLabel(j.source, j.source_type)} ${j.id} ${j.caption_style}`.toLowerCase().includes(term)
    );
    const ts = (j: JobSummary) => parseServerDate(j.created_at)?.getTime() ?? 0;
    list.sort((a, b) => (sort === "clips" ? b.clips_rendered - a.clips_rendered : sort === "oldest" ? ts(a) - ts(b) : ts(b) - ts(a)));
    if (sort === "clips") return [{ label: "Most clips first", jobs: list }];
    const map = new Map<string, JobSummary[]>();
    for (const j of list) {
      const k = dayBucket(parseServerDate(j.created_at));
      map.set(k, [...(map.get(k) ?? []), j]);
    }
    return [...map].map(([label, jobs]) => ({ label, jobs }));
  }, [data, q, sort]);

  const total = data?.length ?? 0;
  const clipTotal = (data ?? []).reduce((n, j) => n + j.clips_rendered, 0);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="animate-rise">
        <p className="eyebrow mb-3">Library</p>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h1 className="font-display text-4xl font-bold tracking-tight sm:text-5xl" style={{ fontVariationSettings: '"wdth" 92' }}>History</h1>
          {total > 0 && (
            <p className="pb-1.5 text-sm text-muted">
              <span className="font-mono text-bone">{total}</span> mines · <span className="font-mono text-bone">{clipTotal}</span> clips
            </p>
          )}
        </div>
      </div>

      {total > 0 && (
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-dim" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by source, style or ID" aria-label="Search history" className="field pl-11" />
          </div>
          <div role="group" aria-label="Sort" className="inline-flex shrink-0 rounded-xl border bg-ink-1 p-1">
            {([["newest", "Newest"], ["oldest", "Oldest"], ["clips", "Most clips"]] as const).map(([id, label]) => (
              <button key={id} onClick={() => setSort(id)} aria-pressed={sort === id} className={cn("rounded-lg px-3.5 py-2 text-sm transition", sort === id ? "bg-white/[0.09] text-bone" : "text-muted hover:text-bone")}>
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-8 space-y-8">
        {loading && !data ? (
          <Skeletons />
        ) : error ? (
          <ErrorState error={error.message} offline={error instanceof ApiError && error.offline} onRetry={reload} />
        ) : total === 0 ? (
          <EmptyState icon={<Film className="h-6 w-6" />} title="No mines yet" body="Every video you process is saved here, so you can come back and re-download your clips any time." action={{ label: "Start your first mine", to: "/" }} />
        ) : groups.every((g) => !g.jobs.length) ? (
          <p className="py-16 text-center text-muted">Nothing matches “{q}”.</p>
        ) : (
          groups.map((g) => (
            <section key={g.label} aria-label={g.label}>
              <h2 className="eyebrow mb-3">{g.label}</h2>
              <div className="space-y-3">
                {g.jobs.map((j, i) => (
                  <div key={j.id} className="animate-rise" style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }}>
                    <Row job={j} />
                  </div>
                ))}
              </div>
            </section>
          ))
        )}
      </div>

      {total > 0 && (
        <div className="mt-10 flex justify-center">
          <Link to="/" className="btn-ghost"><Plus className="h-4 w-4" /> New mine</Link>
        </div>
      )}
    </div>
  );
}
