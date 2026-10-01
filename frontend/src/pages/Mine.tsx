import { useEffect, useMemo, useRef, useState, type DragEvent, type ReactNode } from "react";
import { ArrowRight, ClipboardPaste, FileVideo, Link2, Minus, Plus, ShieldCheck, Upload, X, TerminalSquare, AlertTriangle } from "lucide-react";
import { useShell } from "../components/Layout";
import MiningPanel from "../components/MiningPanel";
import { StyleSelect } from "../components/StyleSelect";
import { FontUpload } from "../components/FontUpload";
import { SourcePreview } from "../components/SourcePreview";
import { useMine } from "../context/MineContext";
import { useAuth } from "../context/AuthContext";
import { useNotice } from "../context/NoticeContext";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { api } from "../lib/api";
import { ENGINE_START_HINT } from "../lib/brand";
import { CAPTION_LOOKS, getLook, mergeStyles } from "../lib/captionStyles";
import { cn } from "../lib/cn";
import { detectPlatform, formatBytes, isValidHttpUrl } from "../lib/format";

type Source = "link" | "file";

function Step({ n, title, hint, children }: { n: string; title: string; hint?: string; children: ReactNode }) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-3 flex items-baseline gap-3">
        <span className="font-mono text-xs text-lime">{n}</span>
        <span className="font-display text-lg font-semibold tracking-tight">{title}</span>
        {hint && <span className="text-sm text-dim">{hint}</span>}
      </legend>
      {children}
    </fieldset>
  );
}

export default function Mine() {
  useDocumentTitle("New mine");
  const { state, start } = useMine();
  const notice = useNotice();
  const auth = useAuth();
  const maxClipsCap = auth.planLimits?.max_clips_ui ?? (auth.profile?.plan_id === "free" ? 1 : 20);
  const planName = auth.planLimits?.name ?? auth.profile?.plan_id ?? "your plan";
  const { engine, recheck } = useShell();

  const [source, setSource] = useState<Source>("link");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [maxClips, setMaxClips] = useState(1);
  // planLimits applied below after auth
  const [styleId, setStyleId] = useState("viral");
  const [fontId, setFontId] = useState<string | null>(null);

  useEffect(() => {
    setMaxClips((c) => Math.min(Math.max(1, c), maxClipsCap));
  }, [maxClipsCap]);

  const [touched, setTouched] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const styles = useAsync((s) => api.styles(s).catch(() => null), []);
  const fonts = useAsync((s) => api.fonts(s).catch(() => []), []);
  const looks = useMemo(() => mergeStyles(styles.data), [styles.data]);
  const look = getLook(styleId, looks.find((l) => l.id === styleId)?.name);

  useEffect(() => {
    if (!looks.some((l) => l.id === styleId)) setStyleId(looks[0]?.id ?? CAPTION_LOOKS[0].id);
  }, [looks, styleId]);

  const trimmed = url.trim();
  const urlValid = isValidHttpUrl(trimmed);
  const platform = urlValid ? detectPlatform(trimmed) : null;
  const ready = source === "link" ? urlValid : !!file;
  const urlError = source === "link" && touched && trimmed && !urlValid ? "That doesn't look like a full link — include https://" : "";

  function pickFile(f: File | undefined | null) {
    if (!f) return;
    if (!f.type.startsWith("video/") && !/\.(mp4|mov|mkv|webm|avi|m4v)$/i.test(f.name)) {
      setTouched(true);
      return;
    }
    setFile(f);
  }
  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    pickFile(e.dataTransfer.files?.[0]);
  }
  async function paste() {
    try {
      const text = (await navigator.clipboard.readText()).trim();
      if (text) {
        setUrl(text);
        setTouched(true);
      }
    } catch {
      /* clipboard permission denied — ignore */
    }
  }
  function submit(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!ready || state.status === "running") return;
    if (source === "file" && file) start({ kind: "file", file, maxClips: Math.min(maxClips, maxClipsCap), style: styleId, fontId });
    else start({ kind: "url", url: trimmed, maxClips: Math.min(maxClips, maxClipsCap), style: styleId, fontId });
  }

  if (state.status === "running") return <MiningPanel />;

  return (
    <div className="mx-auto max-w-3xl">
      <div>
        <div className="animate-rise">
          <p className="eyebrow mb-5 flex items-center gap-2">
            <ShieldCheck className="h-3.5 w-3.5 text-lime" /> Private by default · runs on your machine
          </p>
          <h1 className="font-display text-[clamp(2.6rem,6.2vw,4.75rem)] font-bold leading-[0.98] tracking-[-0.03em]" style={{ fontVariationSettings: '"wdth" 90' }}>
            Find the <span className="hl">moments</span> worth clipping.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
            Drop a long video or paste a link. Cleepye transcribes it, ranks the strongest stretches, reframes them to vertical, and burns in animated captions — ready to post.
          </p>
        </div>

        {engine === "offline" && (
          <div className="mt-8 flex flex-col gap-4 rounded-2xl border border-coral/25 bg-coral/[0.06] p-5 sm:flex-row sm:items-center">
            <TerminalSquare className="h-6 w-6 shrink-0 text-coral" />
            <div className="min-w-0 flex-1">
              <p className="font-medium">The local engine isn't running</p>
              <p className="mt-0.5 text-sm text-muted">
                In the project root run <code className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono text-[13px] text-bone">{ENGINE_START_HINT}</code>, then check again.
              </p>
            </div>
            <button onClick={recheck} className="btn-ghost">Check again</button>
          </div>
        )}

        <form onSubmit={submit} className="mt-10 space-y-10 animate-rise [animation-delay:120ms]" noValidate>
          <Step n="01" title="Source">
            <div role="tablist" aria-label="Source type" className="mb-4 inline-flex rounded-xl border bg-ink-1 p-1">
              {([["link", "Paste a link", Link2], ["file", "Upload a file", Upload]] as const).map(([id, label, Icon]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={source === id}
                  onClick={() => setSource(id)}
                  className={cn("flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition", source === id ? "bg-white/[0.09] text-bone" : "text-muted hover:text-bone")}
                >
                  <Icon className="h-4 w-4" /> {label}
                </button>
              ))}
            </div>

            {source === "link" ? (
              <div>
                <div className="relative">
                  <Link2 className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-dim" />
                  <input
                    type="url"
                    inputMode="url"
                    autoComplete="off"
                    spellCheck={false}
                    aria-label="Video URL"
                    aria-invalid={!!urlError}
                    placeholder="https://youtube.com/watch?v=…"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    onBlur={() => setTouched(true)}
                    className={cn("field pl-11 pr-28", urlError && "border-coral/50 focus:border-coral/60 focus:ring-coral/10")}
                  />
                  <div className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-1">
                    {platform ? (
                      <span className="chip border-lime/30 bg-lime/10 text-lime">{platform}</span>
                    ) : (
                      <button type="button" onClick={paste} className="btn-ghost px-2.5 py-1.5 text-xs">
                        <ClipboardPaste className="h-3.5 w-3.5" /> Paste
                      </button>
                    )}
                  </div>
                </div>
                {urlError ? (
                  <p className="mt-2 text-sm text-muted">{urlError}</p>
                ) : (
                  <p className="mt-2 text-sm text-dim">YouTube, Vimeo, X and most sites yt-dlp supports.</p>
                )}
                {urlValid && (
                  <SourcePreview
                    kind="link"
                    url={trimmed}
                    onClear={() => {
                      setUrl("");
                      setTouched(false);
                    }}
                  />
                )}
              </div>
            ) : file ? (
              <SourcePreview
                kind="file"
                file={file}
                onClear={() => {
                  setFile(null);
                  if (fileInput.current) fileInput.current.value = "";
                }}
              />
            ) : (
              <label
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={cn(
                  "group relative flex cursor-pointer flex-col items-center justify-center overflow-hidden rounded-2xl border border-dashed px-6 py-14 text-center transition",
                  dragging ? "border-lime bg-lime/[0.07]" : "bg-ink-1 hover:border-white/25 hover:bg-white/[0.03]"
                )}
              >
                <div className="ruler pointer-events-none absolute inset-x-0 bottom-0 h-8 opacity-30" />
                <div className={cn("mb-4 grid h-14 w-14 place-items-center rounded-2xl border transition", dragging ? "border-lime/40 bg-lime/15 text-lime" : "bg-white/[0.03] text-muted group-hover:text-lime")}>
                  <Upload className="h-6 w-6" />
                </div>
                <p className="font-medium">{dragging ? "Release to add your video" : "Drag a video here, or click to browse"}</p>
                <p className="mt-1 text-sm text-dim">MP4, MOV, MKV, WebM — stays on this machine</p>
                <input ref={fileInput} type="file" accept="video/*,.mkv" className="sr-only" onChange={(e) => pickFile(e.target.files?.[0])} />
              </label>
            )}
          </Step>

          <Step n="02" title="Captions" hint="Burned in, word by word">
            <StyleSelect looks={looks} value={styleId} onChange={setStyleId} />
            <div className="mt-5">
              <p className="mb-2 text-sm font-medium">Custom font</p>
              <FontUpload
                fonts={fonts.data ?? []}
                value={fontId}
                onChange={setFontId}
                onRefresh={() => fonts.reload()}
              />
            </div>
          </Step>

          <Step n="03" title="Output" hint="Best clips first">
            <div className="surface flex flex-wrap items-center justify-between gap-4 p-4 sm:px-5">
              <div>
                <label htmlFor="max-clips" className="text-sm font-medium">Maximum clips</label>
                <p className="text-sm text-dim">Cleepye keeps the top-scoring moments.</p>
              </div>
              <div className="flex w-full items-center gap-4 sm:w-auto">
                <input id="max-clips" type="range" min={1} max={maxClipsCap} value={Math.min(maxClips, maxClipsCap)} onChange={(e) => setMaxClips(Math.min(Number(e.target.value), maxClipsCap))} className="h-1.5 flex-1 cursor-pointer sm:w-48" />
                <div className="flex items-center rounded-xl border bg-ink-2">
                  <button type="button" aria-label="Fewer clips" onClick={() => setMaxClips((n) => Math.max(1, n - 1))} className="p-2.5 text-muted hover:text-bone"><Minus className="h-4 w-4" /></button>
                  <output className="w-8 text-center font-mono text-sm tabular-nums" htmlFor="max-clips">{Math.min(maxClips, maxClipsCap)}</output>
                <span className="text-xs text-dim">max {maxClipsCap} on {planName}</span>
                  <button type="button" aria-label="More clips" onClick={() => setMaxClips((n) => Math.min(20, n + 1))} className="p-2.5 text-muted hover:text-bone"><Plus className="h-4 w-4" /></button>
                </div>
              </div>
            </div>
          </Step>


          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <button type="submit" disabled={!ready || engine === "offline"} className="btn-primary px-7 py-4 text-base sm:min-w-56">
              Start mining <ArrowRight className="h-4 w-4" />
            </button>
            <p className="text-sm text-dim">
              {!ready ? (source === "link" ? "Paste a valid link to continue." : "Add a video to continue.") : `Up to ${Math.min(maxClips, maxClipsCap)} clips · ${look.name} captions`}
            </p>
          </div>
        </form>
      </div>

    </div>
  );
}
