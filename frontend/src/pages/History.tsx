import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

interface Job {
  id: string;
  source_type: string;
  source: string;
  status: string;
  duration: number | null;
  candidates_found: number;
  clips_rendered: number;
  caption_style: string;
  created_at: string | null;
}

export default function History() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/jobs")
      .then((r) => r.json())
      .then((d) => setJobs(d.jobs || []))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-zinc-400">Loading history…</p>;

  if (!jobs.length) {
    return (
      <div className="text-center py-20">
        <p className="text-zinc-400 mb-4">No mines yet.</p>
        <Link to="/" className="text-amber-400 hover:underline">
          Start your first mine →
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Mine History</h1>
      <div className="space-y-3">
        {jobs.map((j) => (
          <Link
            key={j.id}
            to={`/jobs/${j.id}`}
            className="block bg-zinc-900 border border-zinc-800 hover:border-zinc-600 rounded-xl p-4 transition"
          >
            <div className="flex justify-between items-start">
              <div>
                <div className="font-medium truncate max-w-md">
                  {j.source_type === "url" ? j.source : "Local upload"}
                </div>
                <div className="text-sm text-zinc-500 mt-1">
                  {j.clips_rendered} clips · {j.caption_style} ·{" "}
                  {j.created_at?.slice(0, 19)}
                </div>
              </div>
              <span className="text-xs bg-zinc-800 px-2 py-1 rounded">
                {j.id}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
