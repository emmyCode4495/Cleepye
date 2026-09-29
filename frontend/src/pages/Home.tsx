import { useState } from "react";
import { useNavigate } from "react-router-dom";

const STYLES = [
  { id: "viral", name: "Viral" },
  { id: "clean", name: "Clean" },
  { id: "karaoke", name: "Karaoke" },
  { id: "bold", name: "Bold" },
  { id: "neon", name: "Neon" },
  { id: "minimal", name: "Minimal" },
  { id: "pop", name: "Pop" },
];

export default function Home() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [maxClips, setMaxClips] = useState(8);
  const [style, setStyle] = useState("viral");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      let res: Response;

      if (file) {
        const form = new FormData();
        form.append("file", file);
        form.append("max_clips", String(maxClips));
        form.append("caption_style", style);
        res = await fetch("/api/process/upload", {
          method: "POST",
          body: form,
        });
      } else if (url.trim()) {
        res = await fetch("/api/process/url", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url: url.trim(),
            max_clips: maxClips,
            caption_style: style,
          }),
        });
      } else {
        setError("Provide a URL or upload a file");
        setLoading(false);
        return;
      }

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Processing failed");

      navigate(`/jobs/${data.job_id}`);
    } catch (err: any) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-3xl font-bold mb-2">Mine viral clips</h1>
      <p className="text-zinc-400 mb-8">
        Drop a long video or paste a link. ClipMine finds the best moments,
        reframes them, and burns in captions.
      </p>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm text-zinc-400 mb-1">Video URL</label>
          <input
            type="url"
            placeholder="https://youtube.com/watch?v=..."
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setFile(null);
            }}
            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-3 focus:outline-none focus:border-amber-500"
          />
        </div>

        <div className="text-center text-zinc-500 text-sm">or</div>

        <div>
          <label className="block text-sm text-zinc-400 mb-1">
            Upload local file
          </label>
          <input
            type="file"
            accept="video/*"
            onChange={(e) => {
              setFile(e.target.files?.[0] || null);
              setUrl("");
            }}
            className="w-full text-sm text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-amber-500 file:text-black file:font-medium hover:file:bg-amber-400"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-zinc-400 mb-1">Max clips</label>
            <input
              type="number"
              min={1}
              max={20}
              value={maxClips}
              onChange={(e) => setMaxClips(Number(e.target.value))}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2 focus:outline-none focus:border-amber-500"
            />
          </div>
          <div>
            <label className="block text-sm text-zinc-400 mb-1">
              Caption style
            </label>
            <select
              value={style}
              onChange={(e) => setStyle(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2 focus:outline-none focus:border-amber-500"
            >
              {STYLES.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error && (
          <div className="text-red-400 text-sm bg-red-950/50 border border-red-900 rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-black font-semibold py-3 rounded-lg transition"
        >
          {loading ? "Mining… this can take a few minutes" : "Start Mining"}
        </button>
      </form>
    </div>
  );
}
