import { Download as DownloadIcon, Monitor, Apple } from "lucide-react";
import { Link } from "react-router-dom";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { cn } from "../lib/cn";

export default function Download() {
  useDocumentTitle("Download");

  return (
    <div className="mx-auto max-w-3xl">
      <p className="eyebrow text-lime">Download</p>
      <h1 className="mt-2 font-display text-4xl font-bold tracking-tight">Get Cleepye on your desktop</h1>
      <p className="mt-3 max-w-xl text-muted">
        Run the full mining engine on your machine. Windows is available now; macOS is on the way.
      </p>

      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        {/* Windows */}
        <div className="surface flex flex-col p-6">
          <div className="mb-4 grid h-12 w-12 place-items-center rounded-xl border border-lime/25 bg-lime/10 text-lime">
            <Monitor className="h-6 w-6" />
          </div>
          <h2 className="font-display text-xl font-semibold">Windows</h2>
          <p className="mt-1 text-sm text-muted">Windows 10/11 · 64-bit installer</p>
          <ul className="mt-4 flex-1 space-y-1.5 text-sm text-dim">
            <li>· Local Whisper + FFmpeg pipeline</li>
            <li>· Works offline after setup</li>
            <li>· ~installer size TBD</li>
          </ul>
          <a
            href="/downloads/Cleepye-Setup.exe"
            className={cn("btn-primary mt-6 inline-flex items-center justify-center gap-2 py-2.5")}
            onClick={(e) => {
              // Placeholder until real binary is hosted
              e.preventDefault();
              alert("Windows installer packaging is next. Use the web app + python run.py for now.");
            }}
          >
            <DownloadIcon className="h-4 w-4" /> Download for Windows
          </a>
        </div>

        {/* macOS — coming soon */}
        <div className="surface relative flex flex-col p-6 opacity-90">
          <span className="absolute right-4 top-4 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-dim">
            Coming soon
          </span>
          <div className="mb-4 grid h-12 w-12 place-items-center rounded-xl border border-white/10 bg-white/5 text-muted">
            <Apple className="h-6 w-6" />
          </div>
          <h2 className="font-display text-xl font-semibold">macOS</h2>
          <p className="mt-1 text-sm text-muted">Apple Silicon & Intel · DMG</p>
          <ul className="mt-4 flex-1 space-y-1.5 text-sm text-dim">
            <li>· Native app experience</li>
            <li>· Same local privacy model</li>
            <li>· Notified when available</li>
          </ul>
          <button
            type="button"
            disabled
            className="btn-ghost mt-6 cursor-not-allowed border border-white/10 py-2.5 opacity-60"
          >
            macOS — Coming soon
          </button>
        </div>
      </div>

      <p className="mt-8 text-center text-sm text-dim">
        Prefer the browser?{" "}
        <Link to="/mine" className="text-lime hover:underline">
          Open New mine
        </Link>{" "}
        and run the local engine with <code className="text-bone">python run.py</code>.
      </p>
    </div>
  );
}
