import {
  Captions,
  Check,
  Crop,
  FileAudio,
  Gauge,
  Loader2,
  ScanSearch,
  Square,
  Download,
  Upload,
} from "lucide-react";
import { useMine } from "../context/MineContext";
import { useElapsed } from "../hooks/useElapsed";
import { clock, formatBytes } from "../lib/format";
import { getLook } from "../lib/captionStyles";
import { cn } from "../lib/cn";

/** Maps backend stage ids → UI step */
const STEPS = [
  {
    ids: ["upload", "queued", "download"],
    icon: Download,
    title: "Ingest",
    body: "Upload or download the source video.",
  },
  {
    ids: ["transcribe"],
    icon: FileAudio,
    title: "Transcribe",
    body: "Whisper builds a word-level transcript.",
  },
  {
    ids: ["score"],
    icon: ScanSearch,
    title: "Score moments",
    body: "Ranks the strongest 25–65s stretches.",
  },
  {
    ids: ["reframe"],
    icon: Crop,
    title: "Reframe 9:16",
    body: "Tracks the subject and crops vertical.",
  },
  {
    ids: ["render", "done"],
    icon: Captions,
    title: "Render",
    body: "Cuts clips and burns in captions.",
  },
] as const;

function activeStepIndex(stage: string, uploading: boolean): number {
  if (uploading) return 0;
  const s = (stage || "queued").toLowerCase();
  for (let i = 0; i < STEPS.length; i++) {
    if ((STEPS[i].ids as readonly string[]).includes(s)) return i;
  }
  // Fallback by rough progress bands if stage is unknown
  return 0;
}

export default function MiningPanel() {
  const { state, cancel } = useMine();
  const elapsed = useElapsed(state.status === "running" ? state.startedAt : null);
  if (state.status !== "running") return null;

  const uploading = state.phase === "uploading";
  const uploadPct = state.total ? Math.min(100, Math.round((state.loaded / state.total) * 100)) : 0;
  const enginePct = Math.round(state.progress || 0);
  const pct = uploading ? uploadPct : enginePct;
  const look = getLook(state.style);
  const stage = state.stage || (uploading ? "upload" : "queued");
  const current = activeStepIndex(stage, uploading);

  return (
    <section className="mx-auto max-w-3xl animate-rise" aria-live="polite">
      <div className="surface overflow-hidden">
        {/* Header */}
        <div className="relative border-b px-6 pb-8 pt-7 sm:px-8">
          <p className="eyebrow flex items-center gap-2 text-lime">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            {uploading ? "Uploading" : "Mining in progress"}
          </p>
          <h1 className="mt-3 break-words font-display text-3xl font-bold leading-tight tracking-tight sm:text-4xl">
            {state.label}
          </h1>
          <p className="mt-2 text-sm text-muted">
            Up to {state.maxClips} clips · {look.name} captions
          </p>

          {/* Live status line */}
          <div className="mt-4 flex items-start gap-3 rounded-xl border border-lime/20 bg-lime/5 px-4 py-3">
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-lime/20">
              {uploading ? (
                <Upload className="h-3.5 w-3.5 text-lime" />
              ) : (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-lime" />
              )}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium text-lime">
                {STEPS[current]?.title ?? "Working"}
                <span className="ml-2 font-mono text-xs text-lime/70">{pct}%</span>
              </p>
              <p className="mt-0.5 text-sm text-muted">
                {state.message || (uploading ? "Uploading your file…" : "Working…")}
              </p>
            </div>
          </div>

          <div className="mt-8 flex items-end justify-between gap-6">
            <div>
              <p className="eyebrow">Elapsed</p>
              <p className="font-mono text-5xl font-medium tabular-nums tracking-tight sm:text-6xl">
                {clock(elapsed)}
              </p>
            </div>
            <div className="text-right">
              <p className="font-mono text-2xl tabular-nums">{pct}%</p>
              <p className="font-mono text-xs text-dim">
                {uploading
                  ? `${formatBytes(state.loaded)} / ${formatBytes(state.total)}`
                  : stage}
              </p>
            </div>
          </div>

          {/* Progress bar */}
          <div
            className="relative mt-6 h-2.5 overflow-hidden rounded-full border bg-ink-2"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            aria-label="Mining progress"
          >
            <div
              className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-lime/50 to-lime transition-[width] duration-500"
              style={{ width: `${Math.max(pct, 3)}%` }}
            />
          </div>
        </div>

        {/* Phase stepper */}
        <div className="px-6 py-6 sm:px-8">
          <p className="eyebrow mb-5 flex items-center gap-2">
            <Gauge className="h-3.5 w-3.5" /> Pipeline phases
          </p>

          <ol className="space-y-3">
            {STEPS.map((step, i) => {
              const Icon = step.icon;
              const isDone = i < current || stage === "done";
              const isActive = i === current && stage !== "done";
              const isPending = i > current && stage !== "done";

              return (
                <li
                  key={step.title}
                  className={cn(
                    "relative flex items-stretch gap-4 rounded-2xl border p-4 transition-all duration-300",
                    isActive && "border-lime/50 bg-lime/10 shadow-[0_0_24px_-8px_rgba(163,230,53,0.35)]",
                    isDone && !isActive && "border-white/10 bg-white/[0.03]",
                    isPending && "border-white/[0.06] bg-transparent opacity-50"
                  )}
                >
                  {/* Left status icon */}
                  <div
                    className={cn(
                      "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border",
                      isActive && "border-lime/40 bg-lime/20 text-lime",
                      isDone && !isActive && "border-lime/20 bg-lime/10 text-lime",
                      isPending && "border-white/10 bg-white/[0.03] text-dim"
                    )}
                  >
                    {isDone && !isActive ? (
                      <Check className="h-5 w-5" strokeWidth={2.5} />
                    ) : isActive ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <Icon className="h-5 w-5" />
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p
                        className={cn(
                          "text-sm font-semibold",
                          isActive && "text-lime",
                          isDone && !isActive && "text-white/80",
                          isPending && "text-muted"
                        )}
                      >
                        {step.title}
                      </p>
                      {isActive && (
                        <span className="rounded-full bg-lime/20 px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wide text-lime">
                          Current
                        </span>
                      )}
                      {isDone && !isActive && (
                        <span className="rounded-full bg-white/5 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-dim">
                          Done
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-muted">{step.body}</p>
                    {isActive && state.message && (
                      <p className="mt-2 text-xs text-lime/80">{state.message}</p>
                    )}
                  </div>

                  <span
                    className={cn(
                      "self-center font-mono text-xs tabular-nums",
                      isActive ? "text-lime" : "text-dim"
                    )}
                  >
                    0{i + 1}
                  </span>
                </li>
              );
            })}
          </ol>
        </div>

        <div className="flex flex-col gap-3 border-t bg-white/[0.015] px-6 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <p className="text-xs leading-relaxed text-muted">
            You can open History in another tab. This panel updates as each phase finishes.
          </p>
          <button
            onClick={cancel}
            className="btn-ghost shrink-0"
            title="Stops waiting in the browser. The engine may still finish and save the job to History."
          >
            <Square className="h-3.5 w-3.5" /> Stop waiting
          </button>
        </div>
      </div>
    </section>
  );
}
