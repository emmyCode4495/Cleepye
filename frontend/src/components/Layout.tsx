import { Link, NavLink, Outlet, useOutletContext } from "react-router-dom";
import { History, Plus, Loader2 } from "lucide-react";
import { Logo } from "./Logo";
import { useMine } from "../context/MineContext";
import { useEngineStatus, type EngineState } from "../hooks/useEngineStatus";
import { useElapsed } from "../hooks/useElapsed";
import { clock } from "../lib/format";
import { cn } from "../lib/cn";

export interface ShellContext {
  engine: EngineState;
  recheck: () => void;
}
export const useShell = () => useOutletContext<ShellContext>();

const NAV = [
  { to: "/", label: "New mine", icon: Plus, end: true },
  { to: "/history", label: "History", icon: History, end: false },
];

const ENGINE_LABEL: Record<EngineState, { text: string; dot: string }> = {
  checking: { text: "Connecting…", dot: "bg-dim" },
  online: { text: "Local engine", dot: "bg-lime" },
  busy: { text: "Engine busy", dot: "bg-amber" },
  offline: { text: "Engine offline", dot: "bg-coral" },
};

function EngineChip({ state, onClick }: { state: EngineState; onClick: () => void }) {
  const s = ENGINE_LABEL[state];
  return (
    <button
      onClick={onClick}
      title={state === "online" ? "Everything runs on your machine. Click to re-check." : "Click to re-check the engine"}
      className="chip hover:border-white/15 hover:text-bone"
    >
      <span className="relative flex h-2 w-2">
        {state === "online" && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-lime/60" />}
        <span className={cn("relative inline-flex h-2 w-2 rounded-full", s.dot)} />
      </span>
      <span className="hidden sm:inline">{s.text}</span>
      <span className="sm:hidden">{state === "online" ? "Local" : s.text.split(" ").pop()}</span>
    </button>
  );
}

function MiningPill() {
  const { state } = useMine();
  const elapsed = useElapsed(state.status === "running" ? state.startedAt : null);
  if (state.status !== "running") return null;
  return (
    <Link to="/" className="chip border-lime/30 bg-lime/10 text-lime hover:bg-lime/15">
      <Loader2 className="h-3.5 w-3.5 animate-spin" />
      <span className="font-mono tabular-nums">{clock(elapsed)}</span>
      <span className="hidden sm:inline">Mining</span>
    </Link>
  );
}

export default function Layout() {
  const { state } = useMine();
  const { state: engine, recheck } = useEngineStatus(state.status === "running");

  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70] focus:rounded-lg focus:bg-lime focus:px-3 focus:py-2 focus:text-lime-ink">
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b bg-ink/70 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-5 sm:px-8">
          <Link to="/" aria-label="Cleepye home" className="rounded-lg">
            <Logo />
          </Link>
          <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
            {NAV.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn("rounded-lg px-3.5 py-2 text-sm transition-colors", isActive ? "bg-white/[0.07] text-bone" : "text-muted hover:bg-white/[0.04] hover:text-bone")
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <MiningPill />
            <EngineChip state={engine} onClick={recheck} />
          </div>
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-5 pb-28 pt-8 sm:px-8 md:pb-16 md:pt-12">
        <Outlet context={{ engine, recheck } satisfies ShellContext} />
      </main>

      <footer className="hidden border-t md:block">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-8 py-6 text-xs text-dim">
          <span>Video, transcripts and clips never leave this machine unless you choose a cloud AI provider.</span>
          <span className="font-mono">v0.1</span>
        </div>
      </footer>

      {/* Mobile tab bar */}
      <nav
        aria-label="Primary"
        className="fixed inset-x-0 bottom-0 z-40 border-t bg-ink/85 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl md:hidden"
      >
        <div className="mx-auto grid max-w-md grid-cols-2">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => cn("flex flex-col items-center gap-1 py-3 text-[11px] font-medium", isActive ? "text-lime" : "text-dim")}
            >
              <Icon className="h-5 w-5" />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
