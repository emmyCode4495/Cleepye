import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Check, Clock, Copy, Download, ExternalLink, FileVideo, Film, Plus, Sparkles } from "lucide-react";
import { ScoreRing } from "../components/ScoreRing";
import { SourceTimeline } from "../components/SourceTimeline";
import { EmptyState, ErrorState } from "../components/States";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { api, ApiError } from "../lib/api";
import { getLook } from "../lib/captionStyles";
import { cn } from "../lib/cn";
import { clipUrl, fileNameFromPath, humanDuration, isUrlSource, scoreTier, sourceLabel, timecode } from "../lib/format";
import type { Clip, JobDetail as Job } from "../lib/types";

type Order = "score" | "time";

function Stat({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="surface p-4 sm:p-5">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 font-display text-3xl font-bold leading-none tracking-tight">{value}</p>
      {sub && <p className="mt-1.5 text-xs text-dim">{sub}</p>}
    </div>
  );
}

function ClipRow({ clip, rank, active, onSelect, jobId }: { clip: Clip; rank: number; active: boolean; onSelect: () => void; jobId: string }) {
  const { color } = scoreTier(clip.score);
  return (
    <div
      className={cn("group relative flex items-stretch gap-1 rounded-2xl border transition", active ? "border-white/20 bg-ink-2" : "bg-ink-1 hover:border-white/15 hover:bg-ink-2/60")}
    >
      {active && <span className="absolute inset-y-3 left-0 w-[3px] rounded-r-full" style={{ background: color }} />}
      <button onClick={onSelect} aria-current={active} className="flex min-w-0 flex-1 items-center gap-4 p-4 text-left">
        <span className="w-5 shrink-0 text-center font-mono text-xs text-dim">{rank}</span>
        <ScoreRing score={clip.score} size={46} />
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{clip.title || `Clip ${clip.index}`}</span>
          <span className="mt-0.5 line-clamp-2 block text-sm leading-snug text-muted">{clip.hook}</span>
          <span className="mt-2 flex items-center gap-2 font-mono text-[11px] text-dim">
            <Clock className="h-3 w-3" /> {timecode(clip.start)} → {timecode(clip.end)} · {Math.round(clip.duration)}s
          </span>
        </span>
      </button>
      <a
        href={clipUrl(jobId, clip)}
        download={fileNameFromPath(clip.path)}
        aria-label={`Download clip ${clip.index}`}
        title="Download"
        className="my-3 mr-3 grid w-11 shrink-0 place-items-center self-center rounded-xl text-muted transition hover:bg-white/[0.07] hover:text-lime"
      >
        <Download className="h-[18px] w-[18px]" />
      </a>
    </div>
  );
}

function Loading() {
  return (
    <div className="space-y-6" aria-busy>
      <div className="skeleton h-24 max-w-xl" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-24" />)}</div>
      <div className="skeleton h-20" />
      <div className="grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-[340px_1fr]"><div className="skeleton aspect-[9/16]" /><div className="space-y-3">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-28" />)}</div></div>
    </div>
  );
}

export default function JobDetail() {
  const { id = "" } = useParams();
  const { data: job, error, loading, reload } = useAsync((s) => api.job(id, s), [id]);
  useDocumentTitle(job ? sourceLabel(job.source, job.source_type) : "Results");

  if (loading && !job) return <Loading />;
  if (error || !job) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <BackLink />
        {notFound ? (
          <EmptyState icon={<Film className="h-6 w-6" />} title="That mine doesn't exist" body={`No job with ID “${id}” was found. It may have been cleared from the local database.`} action={{ label: "Go to history", to: "/history" }} />
        ) : (
          <ErrorState error={error?.message ?? "Couldn't load this job."} offline={error instanceof ApiError && error.offline} onRetry={reload} />
        )}
      </div>
    );
  }
  return <Results job={job} onRefresh={reload} />;
}

function BackLink() {
  return (
    <Link to="/history" className="inline-flex items-center gap-1.5 text-sm text-muted transition hover:text-bone">
      <ArrowLeft className="h-4 w-4" /> History
    </Link>
  );
}

function Results({ job, onRefresh }: { job: Job; onRefresh: () => void }) {
  const clips = useMemo(() => job.clips ?? [], [job.clips]);
  const [order, setOrder] = useState<Order>("score");
  const [selected, setSelected] = useState<number>(() => [...clips].sort((a, b) => b.score - a.score)[0]?.index ?? -1);
  const [userPicked, setUserPicked] = useState(false);
  const [copied, setCopied] = useState(false);
  const [enhancing, setEnhancing] = useState(false);
  const [enhanceError, setEnhanceError] = useState<string | null>(null);
  const playerRef = useRef<HTMLDivElement>(null);
  const clarity = useAsync((s) => api.clarity(s).catch(() => null), []);

  const sorted = useMemo(() => [...clips].sort((a, b) => (order === "score" ? b.score - a.score : a.start - b.start)), [clips, order]);
  const current = clips.find((c) => c.index === selected) ?? sorted[0];
  const look = getLook(job.caption_style);
  const label = sourceLabel(job.source, job.source_type);
  const url = isUrlSource(job.source, job.source_type);
  const avg = clips.length ? Math.round(clips.reduce((n, c) => n + c.score, 0) / clips.length) : 0;
  const best = clips.length ? Math.max(...clips.map((c) => c.score)) : 0;

  function pick(index: number) {
    setSelected(index);
    setUserPicked(true);
    if (window.matchMedia("(max-width: 1023px)").matches) playerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // j / k to step through clips
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input,textarea,select,[contenteditable]") || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key !== "j" && e.key !== "k") return;
      const i = sorted.findIndex((c) => c.index === current?.index);
      const next = sorted[Math.max(0, Math.min(sorted.length - 1, i + (e.key === "j" ? 1 : -1)))];
      if (next) {
        setSelected(next.index);
        setUserPicked(true);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [sorted, current?.index]);

  async function copyText() {
    if (!current) return;
    try {
      await navigator.clipboard.writeText(`${current.title}\n${current.hook}`.trim());
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard unavailable */
    }
  }

  async function applyClarity(preset = "sharp") {
    if (!current || !job?.id) return;
    setEnhancing(true);
    setEnhanceError(null);
    try {
      await api.enhanceClip(job.id, current.index, preset);
      onRefresh();
    } catch (e) {
      setEnhanceError(e instanceof ApiError ? e.message : "Clarity failed");
    } finally {
      setEnhancing(false);
    }
  }

  function downloadAll() {
    sorted.forEach((c, i) =>
      window.setTimeout(() => {
        const a = document.createElement("a");
        a.href = clipUrl(job.id, c);
        a.download = fileNameFromPath(c.path);
        document.body.appendChild(a);
        a.click();
        a.remove();
      }, i * 450)
    );
  }

  return (
    <div className="animate-rise">
      <BackLink />

      <header className="mt-6 flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0 max-w-3xl">
          <p className="eyebrow mb-3 flex items-center gap-2">
            Mine <span className="text-bone/70">{job.id}</span>
            {job.status !== "completed" && <span className="chip border-amber/30 text-amber capitalize">{job.status}</span>}
          </p>
          <h1 className="break-words font-display text-3xl font-bold leading-[1.05] tracking-tight sm:text-5xl" style={{ fontVariationSettings: '"wdth" 92' }}>{label}</h1>
          <p className="mt-3 flex items-center gap-2 text-sm text-muted">
            {url ? <ExternalLink className="h-4 w-4" /> : <FileVideo className="h-4 w-4" />}
            {url ? <a href={job.source} target="_blank" rel="noreferrer" className="truncate hover:text-bone hover:underline">{job.source}</a> : "Local file"}
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/" className="btn-ghost"><Plus className="h-4 w-4" /> New mine</Link>
          {clips.length > 1 && <button onClick={downloadAll} className="btn-primary"><Download className="h-4 w-4" /> Download all</button>}
        </div>
      </header>

      <section className="mt-8 grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Summary">
        <Stat label="Clips ready" value={job.clips_rendered} sub={`of ${job.candidates_found} candidates`} />
        <Stat label="Best score" value={best || "—"} sub={clips.length ? `avg ${avg}` : undefined} />
        <Stat label="Source length" value={job.duration ? timecode(job.duration) : "—"} sub={humanDuration(job.duration)} />
        <Stat
          label="Captions"
          value={<span className="flex items-center gap-2 text-2xl"><span className="h-3 w-3 rounded-full" style={{ background: look.highlight === "#ffffff" ? look.primary : look.highlight }} />{look.name}</span>}
          sub="Burned in, 9:16"
        />
      </section>

      {!clips.length || !current ? (
        <div className="mt-10">
          <EmptyState icon={<Sparkles className="h-6 w-6" />} title="No clips were rendered" body="The engine finished but didn't produce any clips. Check that the video has clear speech, then try again — the engine log lists any clips that failed to render." action={{ label: "Try another video", to: "/" }} />
        </div>
      ) : (
        <>
          <section className="mt-10" aria-labelledby="tl">
            <div className="mb-3 flex items-baseline justify-between">
              <h2 id="tl" className="font-display text-lg font-semibold tracking-tight">Where the moments live</h2>
              <p className="hidden text-xs text-dim sm:block">Click a segment to preview it</p>
            </div>
            <SourceTimeline clips={clips} duration={job.duration} selected={current.index} onSelect={pick} />
          </section>

          <section className="mt-10 grid grid-cols-[minmax(0,1fr)] items-start gap-8 lg:grid-cols-[340px_minmax(0,1fr)] xl:grid-cols-[380px_minmax(0,1fr)] xl:gap-12">
            <div ref={playerRef} className="scroll-mt-24 lg:sticky lg:top-24">
              <div className="mx-auto w-full max-w-[340px] overflow-hidden rounded-[1.75rem] border-[6px] border-ink-3 bg-black shadow-[0_30px_80px_-30px_rgb(0_0_0/0.9)] lg:max-w-none">
                {/\.(jpe?g|png|webp|gif)$/i.test(current.path) ? (
                  <img
                    key={current.index}
                    src={clipUrl(job.id, current)}
                    alt={current.title || "Enhanced image"}
                    className="aspect-[9/16] max-h-[72vh] w-full bg-black object-contain"
                  />
                ) : (
                  <video
                    key={current.index}
                    src={`${clipUrl(job.id, current)}#t=0.1`}
                    controls
                    playsInline
                    loop
                    preload="metadata"
                    autoPlay={userPicked}
                    className="aspect-[9/16] max-h-[72vh] w-full bg-black object-contain"
                  />
                )}
              </div>
              <div className="mx-auto mt-5 max-w-[340px] lg:max-w-none">
                <div className="flex items-start gap-3">
                  <ScoreRing score={current.score} size={52} stroke={5} />
                  <div className="min-w-0">
                    <p className="eyebrow" style={{ color: scoreTier(current.score).color }}>{scoreTier(current.score).label} · clip {current.index}</p>
                    <h3 className="mt-1 font-display text-xl font-semibold leading-tight tracking-tight">{current.title || `Clip ${current.index}`}</h3>
                  </div>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-muted">{current.hook}</p>
                <p className="mt-3 font-mono text-xs text-dim">{timecode(current.start)} → {timecode(current.end)} · {Math.round(current.duration)}s</p>
                <div className="mt-5 flex flex-wrap gap-2">
                  <a href={clipUrl(job.id, current)} download={fileNameFromPath(current.path)} className="btn-primary flex-1"><Download className="h-4 w-4" /> Download</a>
                  <button onClick={copyText} className="btn-ghost" aria-label="Copy title and hook">
                    {copied ? <Check className="h-4 w-4 text-lime" /> : <Copy className="h-4 w-4" />} {copied ? "Copied" : "Copy text"}
                  </button>
                  {clarity.data?.available && (
                    <button
                      type="button"
                      onClick={() => applyClarity(current.clarity ? "ultra" : "sharp")}
                      disabled={enhancing}
                      className="btn-ghost"
                      title="Sharpen this clip with Cleepye Clarity"
                    >
                      <Sparkles className={cn("h-4 w-4", enhancing && "animate-pulse")} />
                      {enhancing ? "Clarifying…" : current.clarity ? "Re-Clarity" : "Clarity"}
                    </button>
                  )}
                </div>
                {current.clarity && (
                  <p className="mt-2 text-xs text-lime">Clarity · {current.clarity}</p>
                )}
                {enhanceError && (
                  <p className="mt-2 text-xs text-red-400">{enhanceError}</p>
                )}
              </div>
            </div>

            <div>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <h2 className="font-display text-lg font-semibold tracking-tight">Clips <span className="ml-1 font-mono text-sm text-dim">{clips.length}</span></h2>
                <div className="flex items-center gap-3">
                  <span className="hidden text-xs text-dim xl:block"><kbd className="rounded border px-1.5 py-0.5 font-mono">J</kbd> <kbd className="rounded border px-1.5 py-0.5 font-mono">K</kbd> to step through</span>
                  <div role="group" aria-label="Order" className="inline-flex rounded-xl border bg-ink-1 p-1">
                    {([["score", "By score"], ["time", "By timeline"]] as const).map(([k, l]) => (
                      <button key={k} onClick={() => setOrder(k)} aria-pressed={order === k} className={cn("rounded-lg px-3 py-1.5 text-sm transition", order === k ? "bg-white/[0.09] text-bone" : "text-muted hover:text-bone")}>{l}</button>
                    ))}
                  </div>
                </div>
              </div>
              <div className="space-y-2.5">
                {sorted.map((c, i) => (
                  <ClipRow key={c.index} clip={c} rank={i + 1} active={c.index === current.index} onSelect={() => pick(c.index)} jobId={job.id} />
                ))}
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
