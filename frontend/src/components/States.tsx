import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, RefreshCw, WifiOff } from "lucide-react";
import { ENGINE_START_HINT } from "../lib/brand";

export function EmptyState({ icon, title, body, action }: { icon: ReactNode; title: string; body: string; action?: { label: string; to: string } }) {
  return (
    <div className="surface relative overflow-hidden px-6 py-16 text-center">
      <div className="ruler pointer-events-none absolute inset-x-0 bottom-0 h-8 opacity-40" />
      <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-2xl border bg-white/[0.03] text-lime">{icon}</div>
      <h2 className="font-display text-2xl font-semibold tracking-tight">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-[15px] text-muted">{body}</p>
      {action && (
        <Link to={action.to} className="btn-primary mt-7">
          {action.label}
        </Link>
      )}
    </div>
  );
}

export function ErrorState({ error, offline, onRetry }: { error: string; offline?: boolean; onRetry?: () => void }) {
  return (
    <div className="surface flex flex-col items-start gap-4 border-coral/25 p-6 sm:flex-row sm:items-center">
      <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-coral/10 text-coral">
        {offline ? <WifiOff className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-medium">{offline ? "The engine isn't answering" : "Something went wrong"}</p>
        <p className="mt-0.5 text-sm text-muted">{offline ? <>Start the backend with <code className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono text-[13px] text-bone">{ENGINE_START_HINT}</code> and retry.</> : error}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="btn-ghost">
          <RefreshCw className="h-4 w-4" /> Retry
        </button>
      )}
    </div>
  );
}
