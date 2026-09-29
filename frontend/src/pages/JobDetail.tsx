import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";

interface Clip {
  index: number;
  path: string;
  start: number;
  end: number;
  duration: number;
  score: number;
  title: string;
  hook: string;
  caption_style: string;
}

interface Job {
  id: string;
  source: string;
  status: string;
  duration: number | null;
  candidates_found: number;
  clips_rendered: number;
  caption_style: string;
  clips: Clip[];
}

export default function JobDetail() {
  const { id } = useParams();
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/jobs/${id}`)
      .then((r) => r.json())
      .then(setJob)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p className="text-zinc-400">Loading…</p>;
  if (!job) return <p className="text-red-400">Job not found</p>;

  return (
    <div>
      <Link to="/history" className="text-sm text-zinc-400 hover:text-white mb-4 inline-block">
        ← Back to history
      </Link>

      <h1 className="text-2xl font-bold mb-1">Job {job.id}</h1>
      <p className="text-zinc-400 text-sm mb-8 truncate">{job.source}</p>

      <div className="grid grid-cols-3 gap-4 mb-10">
        <div className="bg-zinc-900 rounded-xl p-4">
          <div className="text-2xl font-bold">{job.clips_rendered}</div>
          <div className="text-sm text-zinc-500">Clips rendered</div>
        </div>
        <div className="bg-zinc-900 rounded-xl p-4">
          <div className="text-2xl font-bold">{job.candidates_found}</div>
          <div className="text-sm text-zinc-500">Candidates found</div>
        </div>
        <div className="bg-zinc-900 rounded-xl p-4">
          <div className="text-2xl font-bold capitalize">{job.caption_style}</div>
          <div className="text-sm text-zinc-500">Caption style</div>
        </div>
      </div>

      <h2 className="text-lg font-semibold mb-4">Clips</h2>
      <div className="space-y-4">
        {job.clips?.map((c) => (
          <div
            key={c.index}
            className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 flex gap-5"
          >
            <div className="flex-shrink-0 w-16 h-16 rounded-lg bg-zinc-800 flex items-center justify-center text-2xl font-bold text-amber-400">
              {c.score}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-medium">{c.title || `Clip ${c.index}`}</div>
              <div className="text-sm text-zinc-400 mt-1">{c.hook}</div>
              <div className="text-xs text-zinc-500 mt-2">
                {c.start.toFixed(1)}s – {c.end.toFixed(1)}s · {c.duration}s
              </div>
            </div>
            <a
              href={`/api/clips/${job.id}/${c.path.split("/").pop()}`}
              download
              className="self-center text-sm bg-amber-500 hover:bg-amber-400 text-black font-medium px-4 py-2 rounded-lg transition"
            >
              Download
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
