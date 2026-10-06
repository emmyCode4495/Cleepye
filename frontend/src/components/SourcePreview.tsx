import { useEffect, useState } from "react";
import { Film, Image as ImageIcon, Link2, X } from "lucide-react";
import { formatBytes, linkThumbnailUrl, detectPlatform } from "../lib/format";

type Props =
  | {
      kind: "file";
      file: File;
      onClear: () => void;
      /** larger player-style preview (Clarity page) */
      large?: boolean;
    }
  | {
      kind: "link";
      url: string;
      onClear?: () => void;
      large?: boolean;
    };

/**
 * Source preview — video, image, or link thumbnail.
 */
export function SourcePreview(props: Props) {
  if (props.kind === "file") {
    return <FilePreview file={props.file} onClear={props.onClear} large={props.large} />;
  }
  return <LinkPreview url={props.url} onClear={props.onClear} large={props.large} />;
}

function isImageFile(file: File): boolean {
  return file.type.startsWith("image/") || /\.(jpe?g|png|webp|tiff?|bmp|gif)$/i.test(file.name);
}

function FilePreview({
  file,
  onClear,
  large,
}: {
  file: File;
  onClear: () => void;
  large?: boolean;
}) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [duration, setDuration] = useState<string | null>(null);
  const image = isImageFile(file);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  if (large) {
    return (
      <div className="surface mt-3 overflow-hidden">
        <div className="relative aspect-video max-h-[420px] w-full bg-black">
          {objectUrl && image && (
            <img src={objectUrl} alt={file.name} className="h-full w-full object-contain" />
          )}
          {objectUrl && !image && (
            <video
              src={objectUrl}
              className="h-full w-full object-contain"
              controls
              playsInline
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
          )}
        </div>
        <div className="flex items-center gap-3 border-t border-white/[0.06] px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{file.name}</p>
            <p className="font-mono text-xs text-dim">
              {formatBytes(file.size)}
              {image ? " · image" : duration ? ` · ${duration}` : " · video"}
            </p>
          </div>
          <button type="button" onClick={onClear} className="btn-ghost px-2.5" aria-label="Remove file">
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="surface mt-3 flex items-center gap-3 p-2.5">
      <div className="relative h-14 w-24 shrink-0 overflow-hidden rounded-lg bg-black/60">
        {objectUrl && image ? (
          <img src={objectUrl} alt="" className="h-full w-full object-cover" />
        ) : objectUrl ? (
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
            {image ? <ImageIcon className="h-5 w-5" /> : <Film className="h-5 w-5" />}
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{file.name}</p>
        <p className="font-mono text-xs text-dim">
          {formatBytes(file.size)}
          {image ? " · image" : duration ? ` · ${duration}` : ""}
        </p>
      </div>
      <button type="button" onClick={onClear} className="btn-ghost px-2.5" aria-label="Remove file">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

function LinkPreview({
  url,
  onClear,
  large,
}: {
  url: string;
  onClear?: () => void;
  large?: boolean;
}) {
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

  const meta = (
    <div className={large ? "flex items-center gap-3 border-t border-white/[0.06] px-4 py-3" : "min-w-0 flex-1"}>
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

  const thumbEl = (
    <div
      className={
        large
          ? "relative aspect-video max-h-[280px] w-full overflow-hidden bg-gradient-to-br from-ink-2 to-black/80"
          : "relative h-14 w-24 shrink-0 overflow-hidden rounded-lg bg-gradient-to-br from-ink-2 to-black/80"
      }
    >
      {thumb && !imgFailed ? (
        <img src={thumb} alt="" className="h-full w-full object-cover" onError={() => setImgFailed(true)} />
      ) : (
        <div className="flex h-full flex-col items-center justify-center gap-0.5 text-dim">
          <Link2 className="h-4 w-4" />
        </div>
      )}
    </div>
  );

  if (large) {
    return (
      <div className="surface mt-3 overflow-hidden">
        {thumbEl}
        {meta}
      </div>
    );
  }

  return (
    <div className="surface mt-3 flex items-center gap-3 p-2.5">
      {thumbEl}
      {meta}
    </div>
  );
}
