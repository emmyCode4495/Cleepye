import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  ClipboardPaste,
  Image as ImageIcon,
  Link2,
  Loader2,
  ShieldCheck,
  Sparkles,
  Square,
  Upload,
  Video,
} from "lucide-react";
import { useShell } from "../components/Layout";
import { SourcePreview } from "../components/SourcePreview";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useElapsed } from "../hooks/useElapsed";
import { api, ApiError, clarityFromUrl, clarityFromUpload } from "../lib/api";
import { cn } from "../lib/cn";
import { detectPlatform, formatBytes, isValidHttpUrl } from "../lib/format";

type Source = "link" | "file";
type Media = "video" | "image";

function isImageFile(f: File) {
  return f.type.startsWith("image/") || /\.(jpe?g|png|webp|tiff?|bmp|gif)$/i.test(f.name);
}
function isVideoFile(f: File) {
  return f.type.startsWith("video/") || /\.(mp4|mov|mkv|webm|avi|m4v)$/i.test(f.name);
}

export default function ClarityPage() {
  useDocumentTitle("Clarity");
  const navigate = useNavigate();
  const { engine } = useShell();

  const [media, setMedia] = useState<Media>("video");
  const [source, setSource] = useState<Source>("file");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [preset, setPreset] = useState("precise");
  const [touched, setTouched] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const [status, setStatus] = useState<"idle" | "running" | "error">("idle");
  const [phase, setPhase] = useState<"uploading" | "processing">("processing");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [loaded, setLoaded] = useState(0);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const clarity = useAsync((s) => api.clarity(s).catch(() => null), []);
  const elapsed = useElapsed(status === "running" ? startedAt : null);

  const presets = useMemo(() => {
    if (!clarity.data) return [];
    if (media === "image") return clarity.data.image_presets?.length ? clarity.data.image_presets : clarity.data.presets;
    return clarity.data.presets ?? [];
  }, [clarity.data, media]);

  const groups = useMemo(() => {
    if (!clarity.data) return [] as Array<{ id: string; name: string }>;
    return media === "image" ? clarity.data.image_groups ?? [] : clarity.data.video_groups ?? [];
  }, [clarity.data, media]);

  useEffect(() => {
    if (media === "video") setPreset(clarity.data?.default_preset || "precise");
    else setPreset("standard");
  }, [media, clarity.data?.default_preset]);

  // Keep preset valid when switching media
  useEffect(() => {
    if (presets.length && !presets.some((p) => p.id === preset)) {
      setPreset(presets[0].id);
    }
  }, [presets, preset]);

  // When media switches, drop incompatible file and prefer upload for images
  useEffect(() => {
    if (media === "image") {
      setSource("file");
      if (file && !isImageFile(file)) setFile(null);
    } else if (file && isImageFile(file)) {
      setFile(null);
    }
  }, [media]); // eslint-disable-line react-hooks/exhaustive-deps

  const trimmed = url.trim();
  const urlValid = isValidHttpUrl(trimmed);
  const platform = urlValid ? detectPlatform(trimmed) : null;
  const ready = media === "image" ? !!file : source === "link" ? urlValid : !!file;
  const urlError =
    source === "link" && media === "video" && touched && trimmed && !urlValid
      ? "That doesn't look like a full link — include https://"
      : "";

  function pickFile(f: File | undefined | null) {
    if (!f) return;
    if (media === "image") {
      if (!isImageFile(f)) {
        setTouched(true);
        setError("Please choose an image (JPEG, PNG, WebP…).");
        return;
      }
    } else if (!isVideoFile(f)) {
      setTouched(true);
      setError("Please choose a video file.");
      return;
    }
    setError(null);
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
      /* ignore */
    }
  }

  function cancel() {
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus("idle");
    setError(null);
    setProgress(0);
    setMessage("");
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!ready || status === "running") return;
    if (!clarity.data?.available) {
      setError("Clarity is not available on this server.");
      setStatus("error");
      return;
    }

    const ac = new AbortController();
    abortRef.current = ac;
    setStatus("running");
    setError(null);
    setStartedAt(Date.now());
    setProgress(0);
    setPhase(source === "file" || media === "image" ? "uploading" : "processing");
    setMessage(source === "file" || media === "image" ? "Uploading…" : "Starting Clarity…");

    const hooks = {
      signal: ac.signal,
      onUploadProgress: (l: number, t: number) => {
        setLoaded(l);
        setTotal(t);
        setPhase("uploading");
      },
      onUploadDone: () => {
        setPhase("processing");
        setMessage("Upload complete — starting Clarity…");
      },
      onProgress: (info: { progress: number; stage: string; message: string }) => {
        setProgress(info.progress);
        setMessage(info.message);
        setPhase("processing");
      },
    };

    try {
      const result =
        media === "image" && file
          ? await clarityFromUpload({ file, preset, media: "image" }, hooks)
          : source === "file" && file
            ? await clarityFromUpload({ file, preset, media: "video" }, hooks)
            : await clarityFromUrl({ url: trimmed, preset }, hooks);
      navigate(`/jobs/${result.job_id}`);
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setStatus("idle");
        return;
      }
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "Clarity failed");
    } finally {
      abortRef.current = null;
    }
  }

  if (!clarity.data && clarity.loading) {
    return (
      <div className="mx-auto max-w-3xl p-8 text-sm text-dim">
        <Loader2 className="mr-2 inline h-4 w-4 animate-spin" /> Loading Clarity…
      </div>
    );
  }

  if (clarity.data && !clarity.data.available) {
    return (
      <div className="mx-auto max-w-3xl">
        <p className="eyebrow mb-5 flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-lime" /> Clarity
        </p>
        <h1 className="font-display text-4xl font-bold tracking-tight">Enhance any video or photo</h1>
        <p className="mt-4 max-w-xl text-muted">
          Clarity is not enabled on this server yet. Ask the admin to set the Clarity API key, or use{" "}
          <a href="/mine" className="text-lime hover:underline">
            New mine
          </a>{" "}
          for clipping.
        </p>
      </div>
    );
  }

  if (status === "running") {
    const uploadPct = total ? Math.min(100, Math.round((loaded / total) * 100)) : 0;
    const pct = phase === "uploading" ? uploadPct : Math.round(progress || 0);
    return (
      <section className="mx-auto max-w-3xl animate-rise" aria-live="polite">
        <div className="surface overflow-hidden">
          <div className="border-b px-6 pb-8 pt-7 sm:px-8">
            <p className="eyebrow flex items-center gap-2 text-lime">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {phase === "uploading" ? "Uploading" : "Clarity in progress"}
            </p>
            <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight">
              {media === "image" ? "Enhancing your image" : "Sharpening your video"}
            </h1>
            <p className="mt-2 text-sm text-muted">{message || "Working…"}</p>
            <div className="mt-6 h-2 overflow-hidden rounded-full bg-white/[0.06]">
              <div className="h-full rounded-full bg-lime transition-all duration-500" style={{ width: `${pct}%` }} />
            </div>
            <div className="mt-3 flex items-center justify-between text-xs text-dim">
              <span className="font-mono tabular-nums">{pct}%</span>
              <span className="font-mono tabular-nums">
                {elapsed != null ? `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}` : "—"}
              </span>
            </div>
            {phase === "uploading" && total > 0 && (
              <p className="mt-2 text-xs text-dim">
                {formatBytes(loaded)} / {formatBytes(total)}
              </p>
            )}
            <button type="button" onClick={cancel} className="btn-ghost mt-6">
              <Square className="h-4 w-4" /> Cancel
            </button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="animate-rise">
        <p className="eyebrow mb-5 flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-lime" /> Clarity only · no mining
        </p>
        <h1
          className="font-display text-[clamp(2.4rem,5.5vw,4rem)] font-bold leading-[0.98] tracking-[-0.03em]"
          style={{ fontVariationSettings: '"wdth" 90' }}
        >
          Make it <span className="hl">sharper</span>.
        </h1>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
          Enhance video or upscale photos with Cleepye Clarity — without mining clips.
        </p>
        <p className="mt-2 flex items-center gap-2 text-sm text-dim">
          <ShieldCheck className="h-3.5 w-3.5 text-lime" />
          Optional path — use New mine when you need viral shorts instead.
        </p>
      </div>

      <form onSubmit={submit} className="mt-10 space-y-8 animate-rise [animation-delay:120ms]" noValidate>
        {/* Media type */}
        <div>
          <p className="mb-2 text-sm font-medium">What are you enhancing?</p>
          <div className="inline-flex rounded-xl border bg-ink-1 p-1">
            {(
              [
                { id: "video" as const, label: "Video", icon: Video },
                { id: "image" as const, label: "Image", icon: ImageIcon },
              ] as const
            ).map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => setMedia(id)}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition",
                  media === id ? "bg-white/[0.09] text-bone" : "text-muted hover:text-bone"
                )}
              >
                <Icon className="h-4 w-4" /> {label}
              </button>
            ))}
          </div>
        </div>

        {media === "video" && (
          <div className="inline-flex rounded-xl border bg-ink-1 p-1">
            {(
              [
                { id: "file" as const, label: "Upload", icon: Upload },
                { id: "link" as const, label: "Link", icon: Link2 },
              ] as const
            ).map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => setSource(id)}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition",
                  source === id ? "bg-white/[0.09] text-bone" : "text-muted hover:text-bone"
                )}
              >
                <Icon className="h-4 w-4" /> {label}
              </button>
            ))}
          </div>
        )}

        {media === "video" && source === "link" ? (
          <div>
            <div className="flex gap-2">
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onBlur={() => setTouched(true)}
                placeholder="https://…"
                className="input flex-1"
                autoComplete="off"
              />
              <button type="button" onClick={paste} className="btn-ghost shrink-0" title="Paste">
                <ClipboardPaste className="h-4 w-4" />
              </button>
            </div>
            {platform && <p className="mt-2 text-xs text-lime">{platform}</p>}
            {urlError && <p className="mt-2 text-xs text-red-400">{urlError}</p>}
            {urlValid && (
              <SourcePreview kind="link" url={trimmed} large onClear={() => setUrl("")} />
            )}
          </div>
        ) : (
          <div>
            {!file && (
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={cn(
                  "flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed px-6 py-12 transition",
                  dragging ? "border-lime/50 bg-lime/5" : "border-white/15 hover:border-white/25"
                )}
                onClick={() => fileInput.current?.click()}
              >
                <Upload className="mb-3 h-8 w-8 text-muted" />
                <p className="text-sm font-medium">
                  {media === "image" ? "Drop a photo or click to browse" : "Drop a video or click to browse"}
                </p>
                <p className="mt-1 text-xs text-dim">
                  {media === "image" ? "JPEG, PNG, WebP, TIFF" : "MP4, MOV, WebM, MKV"}
                </p>
                <input
                  ref={fileInput}
                  type="file"
                  accept={media === "image" ? "image/*,.jpg,.jpeg,.png,.webp,.tif,.tiff" : "video/*,.mp4,.mov,.mkv,.webm,.avi,.m4v"}
                  className="hidden"
                  onChange={(e) => pickFile(e.target.files?.[0])}
                />
              </div>
            )}
            {file && (
              <SourcePreview kind="file" file={file} large onClear={() => setFile(null)} />
            )}
          </div>
        )}

        <div className="space-y-5">
          <p className="text-sm font-medium">Workflow</p>
          {(groups.length ? groups : [{ id: "all", name: "Options" }]).map((g) => {
            const items = groups.length ? presets.filter((p) => (p.group || "upscale") === g.id) : presets;
            if (!items.length) return null;
            return (
              <div key={g.id}>
                <p className="mb-2 text-xs uppercase tracking-wide text-dim">{g.name}</p>
                <div className="flex flex-wrap gap-2">
                  {items.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setPreset(p.id)}
                      className={cn(
                        "max-w-[220px] rounded-xl border px-3 py-2 text-left text-sm transition",
                        preset === p.id ? "border-lime/40 bg-lime/10 text-lime" : "hover:border-white/20"
                      )}
                      title={p.description}
                    >
                      <span className="font-medium">{p.name}</span>
                      <span className="mt-0.5 block text-xs text-dim leading-snug">{p.description}</span>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <button
            type="submit"
            disabled={!ready || engine === "offline"}
            className="btn-primary px-7 py-4 text-base sm:min-w-56"
          >
            Run Clarity <ArrowRight className="h-4 w-4" />
          </button>
          <p className="text-sm text-dim">
            {!ready
              ? media === "image"
                ? "Add an image to continue."
                : source === "link"
                  ? "Paste a valid link to continue."
                  : "Add a video to continue."
              : `${media === "image" ? "Image" : "Video"} · ${presets.find((x) => x.id === preset)?.name ?? preset}`}
          </p>
        </div>
      </form>
    </div>
  );
}
