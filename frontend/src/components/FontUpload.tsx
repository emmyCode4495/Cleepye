import { useRef, useState } from "react";
import { Loader2, Trash2, Type, Upload } from "lucide-react";
import { api } from "../lib/api";
import { useNotice } from "../context/NoticeContext";
import { cn } from "../lib/cn";

export type CustomFont = {
  id: string;
  name: string;
  filename: string;
  size?: number;
};

type Props = {
  fonts: CustomFont[];
  value: string | null;
  onChange: (id: string | null) => void;
  onRefresh: () => void;
};

export function FontUpload({ fonts, value, onChange, onRefresh }: Props) {
  const notice = useNotice();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  async function onFile(file: File | undefined) {
    if (!file) return;
    const lower = file.name.toLowerCase();
    if (!lower.endsWith(".ttf") && !lower.endsWith(".otf") && !lower.endsWith(".ttc")) {
      notice.error("Unsupported file", "Upload a .ttf, .otf, or .ttc font file.");
      return;
    }
    setUploading(true);
    try {
      const meta = await api.uploadFont(file);
      onRefresh();
      onChange(meta.id);
      notice.success("Font uploaded", `"${meta.name}" is ready for captions.`);
    } catch (e: any) {
      notice.error("Upload failed", e?.message || "Could not upload font.");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function remove(id: string) {
    setDeleting(id);
    try {
      await api.deleteFont(id);
      if (value === id) onChange(null);
      onRefresh();
    } catch (e: any) {
      notice.error("Delete failed", e?.message || "Could not remove font.");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted">Optional — use your own caption typeface</p>
        <button
          type="button"
          disabled={uploading}
          onClick={() => inputRef.current?.click()}
          className="btn-ghost inline-flex items-center gap-1.5 border border-white/10 px-3 py-1.5 text-xs"
        >
          {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
          Upload font
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".ttf,.otf,.ttc,font/ttf,font/otf"
          className="sr-only"
          onChange={(e) => onFile(e.target.files?.[0])}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onChange(null)}
          className={cn(
            "chip text-xs",
            !value ? "border-lime/40 bg-lime/10 text-lime" : "hover:border-white/20"
          )}
        >
          Style default
        </button>
        {fonts.map((f) => (
          <div
            key={f.id}
            className={cn(
              "inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs",
              value === f.id ? "border-lime/40 bg-lime/10 text-lime" : "border-white/10 bg-white/[0.03]"
            )}
          >
            <button type="button" className="inline-flex items-center gap-1.5" onClick={() => onChange(f.id)}>
              <Type className="h-3 w-3" />
              <span className="max-w-[8rem] truncate">{f.name}</span>
            </button>
            <button
              type="button"
              disabled={deleting === f.id}
              onClick={() => remove(f.id)}
              className="rounded p-0.5 text-dim hover:text-coral"
              aria-label={`Remove ${f.name}`}
            >
              {deleting === f.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
            </button>
          </div>
        ))}
      </div>
      {fonts.length === 0 && (
        <p className="text-xs text-dim">No custom fonts yet. Upload a .ttf or .otf to brand your captions.</p>
      )}
    </div>
  );
}
