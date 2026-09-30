import { useEffect, useState } from "react";
import { Film, Link2, X } from "lucide-react";
import { formatBytes, linkThumbnailUrl, detectPlatform } from "../lib/format";

type Props =
  | {
      kind: "file";
      file: File;
      onClear: () => void;
    }
  | {
      kind: "link";
      url: string;
      onClear?: () => void;
    };

/**
 * Compact source preview (small thumbnail + meta).
 */
export function SourcePreview(props: Props) {
  if (props.kind === "file") {
    return <FilePreview file={props.file} onClear={props.onClear} />;
  }
  return <LinkPreview url={props.url} onClear={props.onClear} />;
}

function FilePreview({ file, onClear }: { file: File; onClear: () => void }) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [duration, setDuration] = useState<string | null>(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return (
    <div className="surface mt-3 flex items-center gap-3 p-2.5">
      <div className="relative h-14 w-24 shrink-0 overflow-hidden rounded-lg bg-black/60">
        {objectUrl ? (
          <video
            src={objectUrl}
            className="h-full w-full object-cover"
            muted
            preload="metadata"
            onLoadedMetadata={(e) => {
              const d = e.currentTarget.duration;
              if (Number.isFinite(d)) {
                const m = Math.floor(d / 60);
                const s = Math.floor(d % 60);
                setDuration(`${m}:${String(s).padStart(2, "0")}`);
              }
            }}
          />
        ) : (
          <div className="grid h-full place-items-center text-dim">
            <Film className="h-5 w-5" />
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{file.name}</p>
        <p className="font-mono text-xs text-dim">
          {formatBytes(file.size)}
          {duration ? ` · ${duration}` : ""}
        </p>
      </div>
      <button type="button" onClick={onClear} className="btn-ghost px-2.5" aria-label="Remove file">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

function LinkPreview({ url, onClear }: { url: string; onClear?: () => void }) {
  const thumb = linkThumbnailUrl(url);
  const platform = detectPlatform(url);
  const [imgFailed, setImgFailed] = useState(false);

  useEffect(() => {
    setImgFailed(false);
  }, [url]);

  let host = "";
  try {
    host = new URL(url).hostname.replace(/^www\./, "");
  } catch {
    host = url;
  }

  return (
    <div className="surface mt-3 flex items-center gap-3 p-2.5">
      <div className="relative h-14 w-24 shrink-0 overflow-hidden rounded-lg bg-gradient-to-br from-ink-2 to-black/80">
        {thumb && !imgFailed ? (
          <img
            src={thumb}
            alt=""
            className="h-full w-full object-cover"
            onError={() => setImgFailed(true)}
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-0.5 text-dim">
            <Link2 className="h-4 w-4" />
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate text-sm font-medium">{host}</p>
          {platform && (
            <span className="shrink-0 rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-dim">
              {platform}
            </span>
          )}
        </div>
        <p className="truncate font-mono text-[11px] text-dim">{url}</p>
      </div>
      {onClear && (
        <button type="button" onClick={onClear} className="btn-ghost px-2.5" aria-label="Clear link">
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
