import { Captions, Crop, FileAudio, Gauge, Loader2, ScanSearch, Square, Download } from "lucide-react";
import { useMine } from "../context/MineContext";
import { useElapsed } from "../hooks/useElapsed";
import { clock, formatBytes } from "../lib/format";
import { getLook } from "../lib/captionStyles";

const PIPELINE = [
  { icon: Download, title: "Ingest", body: "Downloads the link or reads your file." },
  { icon: FileAudio, title: "Transcribe", body: "Whisper builds a word-level transcript locally." },
  { icon: ScanSearch, title: "Score moments", body: "Ranks the strongest 25–65 second stretches." },
  { icon: Crop, title: "Reframe 9:16", body: "Tracks the subject and crops to vertical." },
  { icon: Captions, title: "Render", body: "Cuts each clip and burns in animated captions." },
];

export default function MiningPanel() {
  const { state, cancel } = useMine();
  const elapsed = useElapsed(state.status === "running" ? state.startedAt : null);
  if (state.status !== "running") return null;

  const uploading = state.phase === "uploading";
  const pct = state.total ? Math.min(100, Math.round((state.loaded / state.total) * 100)) : 0;
  const look = getLook(state.style);

  return (
    <section className="mx-auto max-w-3xl animate-rise" aria-live="polite">
      <div className="surface overflow-hidden">
        <div className="relative border-b px-6 pb-8 pt-7 sm:px-8">
          <p className="eyebrow flex items-center gap-2 text-lime">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> {uploading ? "Uploading" : "Mining in progress"}
          </p>
          <h1 className="mt-3 break-words font-display text-3xl font-bold leading-tight tracking-tight sm:text-4xl">{state.label}</h1>
          <p className="mt-2 text-sm text-muted">
            Up to {state.maxClips} clips · {look.name} captions
          </p>

          <div className="mt-8 flex items-end justify-between gap-6">
            <div>
              <p className="eyebrow">Elapsed</p>
              <p className="font-mono text-5xl font-medium tabular-nums tracking-tight sm:text-6xl">{clock(elapsed)}</p>
            </div>
            {uploading && (
              <div className="text-right">
                <p className="font-mono text-2xl tabular-nums">{pct}%</p>
                <p className="font-mono text-xs text-dim">
                  {formatBytes(state.loaded)} / {formatBytes(state.total)}
                </p>
              </div>
            )}
          </div>

          {/* timeline scanner — decorative activity indicator; the engine doesn't report per-stage progress */}
          <div className="relative mt-6 h-12 overflow-hidden rounded-xl border bg-ink-2" role="progressbar" aria-label={uploading ? "Upload progress" : "Processing"} aria-valuemin={0} aria-valuemax={100} aria-valuenow={uploading ? pct : undefined}>
            <div className="ruler absolute inset-x-0 bottom-0 h-full opacity-60" />
            {uploading ? (
              <div className="absolute inset-y-0 left-0 bg-lime/25 transition-[width] duration-300" style={{ width: `${pct}%` }}>
                <div className="absolute inset-y-0 right-0 w-0.5 bg-lime shadow-[0_0_12px_rgb(var(--lime))]" />
              </div>
            ) : (
              <div className="absolute inset-y-0 left-0 w-full">
                <div className="absolute inset-y-0 w-1/3 animate-sweep bg-gradient-to-r from-transparent via-lime/25 to-transparent">
                  <div className="absolute inset-y-0 right-1/2 w-0.5 bg-lime shadow-[0_0_14px_rgb(var(--lime))]" />
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="px-6 py-6 sm:px-8">
          <p className="eyebrow mb-4 flex items-center gap-2">
            <Gauge className="h-3.5 w-3.5" /> What the engine is doing, in order
          </p>
          <ol className="grid gap-3 sm:grid-cols-5">
            {PIPELINE.map(({ icon: Icon, title, body }, i) => (
              <li key={title} className="rounded-xl border bg-white/[0.02] p-3.5">
                <div className="mb-2.5 flex items-center justify-between text-dim">
                  <Icon className="h-4 w-4 text-lime" />
                  <span className="font-mono text-[11px]">0{i + 1}</span>
                </div>
                <p className="text-sm font-medium">{title}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted">{body}</p>
              </li>
            ))}
          </ol>
        </div>

        <div className="flex flex-col gap-3 border-t bg-white/[0.015] px-6 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <p className="text-xs leading-relaxed text-muted">
            Keep this tab open. Long videos take a while, and pages may load slowly while the engine is busy — you'll get a notification when clips are ready.
          </p>
          <button onClick={cancel} className="btn-ghost shrink-0" title="Stops waiting in the browser. The engine may still finish and save the job to History.">
            <Square className="h-3.5 w-3.5" /> Stop waiting
          </button>
        </div>
      </div>
    </section>
  );
}
