import { Link, NavLink, Outlet, useOutletContext } from "react-router-dom";
import {
  History,
  Plus,
  Loader2,
  Sparkles,
  Wand2,
  Home,
  Download,
  Mail,
  User,
  Menu,
  X,
} from "lucide-react";
import { useState } from "react";
import { Logo } from "./Logo";
import { useMine } from "../context/MineContext";
import { useAuth } from "../context/AuthContext";
import { useEngineStatus, type EngineState } from "../hooks/useEngineStatus";
import { useElapsed } from "../hooks/useElapsed";
import { clock } from "../lib/format";
import { cn } from "../lib/cn";

export interface ShellContext {
  engine: EngineState;
  recheck: () => void;
}
export const useShell = () => useOutletContext<ShellContext>();

type NavItem = { to: string; label: string; icon: typeof Home; end?: boolean; authOnly?: boolean };

const PUBLIC_NAV: NavItem[] = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/mine", label: "New mine", icon: Plus, end: true },
  { to: "/clarity", label: "Clarity", icon: Wand2, end: true },
  { to: "/pricing", label: "Pricing", icon: Sparkles },
  { to: "/download", label: "Download", icon: Download },
  { to: "/contact", label: "Contact", icon: Mail },
];

const AUTH_NAV: NavItem[] = [
  { to: "/history", label: "History", icon: History, authOnly: true },
  { to: "/profile", label: "Profile", icon: User, authOnly: true },
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
      type="button"
      onClick={onClick}
      title={state === "online" ? "Everything runs on your machine. Click to re-check." : "Click to re-check the engine"}
      className="chip hover:border-white/15 hover:text-bone"
    >
      <span className="relative flex h-2 w-2">
        {state === "online" && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-lime/60" />}
        <span className={cn("relative inline-flex h-2 w-2 rounded-full", s.dot)} />
      </span>
      <span className="hidden lg:inline">{s.text}</span>
    </button>
  );
}

function MiningPill() {
  const { state } = useMine();
  const elapsed = useElapsed(state.status === "running" ? state.startedAt : null);
  if (state.status !== "running") return null;
  return (
    <Link to="/mine" className="chip border-lime/30 bg-lime/10 text-lime hover:bg-lime/15">
      <Loader2 className="h-3.5 w-3.5 animate-spin" />
      <span className="font-mono tabular-nums">{clock(elapsed)}</span>
      <span className="hidden sm:inline">Mining</span>
    </Link>
  );
}

export default function Layout() {
  const { state } = useMine();
  const auth = useAuth();
  const { state: engine, recheck } = useEngineStatus(state.status === "running");
  const [open, setOpen] = useState(false);

  const signedIn = Boolean(auth.configured && auth.user);
  const publicNav = signedIn
    ? PUBLIC_NAV.filter((item) => item.to !== "/")
    : PUBLIC_NAV;
  const navItems = [...publicNav, ...(signedIn ? AUTH_NAV : [])];

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-ink/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:h-16 sm:px-6 lg:px-8">
          <Link to={signedIn ? "/mine" : "/"} className="shrink-0" aria-label="Cleepye home">
            <Logo />
          </Link>

          {/* Desktop nav */}
          <nav className="ml-4 hidden items-center gap-0.5 md:flex" aria-label="Primary">
            {navItems.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "rounded-lg px-2.5 py-1.5 text-sm font-medium transition lg:px-3",
                    isActive ? "bg-white/[0.08] text-bone" : "text-muted hover:text-bone"
                  )
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
            <MiningPill />
            {signedIn && auth.profile && (
              <Link
                to="/profile"
                className="chip hidden font-mono text-lime sm:inline-flex"
                title="Mining · Clarity credits"
              >
                {auth.profile.credits_balance}m
                <span className="text-dim">·</span>
                {(auth.profile as { clarity_credits_balance?: number }).clarity_credits_balance ?? 0}c
              </Link>
            )}
            {auth.configured && !auth.user && (
              <Link to="/auth" className="btn-ghost hidden border border-white/10 px-3 py-1.5 text-sm sm:inline-flex">
                Sign in
              </Link>
            )}
            {signedIn && (
              <Link to="/profile" className="chip hidden hover:text-bone sm:inline-flex" title={auth.user?.email || "Profile"}>
                <User className="h-3.5 w-3.5" />
                <span className="hidden max-w-[7rem] truncate lg:inline">
                  {auth.profile?.display_name || "Account"}
                </span>
              </Link>
            )}
            <EngineChip state={engine} onClick={recheck} />
            <button
              type="button"
              className="btn-ghost p-2 md:hidden"
              aria-label={open ? "Close menu" : "Open menu"}
              onClick={() => setOpen((v) => !v)}
            >
              {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {/* Mobile dropdown */}
        {open && (
          <div className="border-t border-white/[0.06] bg-ink-1 px-4 py-3 md:hidden">
            <nav className="flex flex-col gap-1" aria-label="Mobile">
              {navItems.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium",
                      isActive ? "bg-white/[0.08] text-lime" : "text-muted"
                    )
                  }
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </NavLink>
              ))}
              {auth.configured && !auth.user && (
                <Link
                  to="/auth"
                  onClick={() => setOpen(false)}
                  className="mt-1 flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-lime"
                >
                  Sign in
                </Link>
              )}
            </nav>
          </div>
        )}
      </header>

      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-5 pb-16 pt-8 sm:px-8 md:pt-12">
        <Outlet context={{ engine, recheck } satisfies ShellContext} />
      </main>

      <footer className="border-t border-white/[0.06]">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-8 text-xs text-dim sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <span>© {new Date().getFullYear()} Cleepye · Privacy-first AI video clipper</span>
          <div className="flex flex-wrap gap-4">
            <Link to="/pricing" className="hover:text-bone">
              Pricing
            </Link>
            <Link to="/download" className="hover:text-bone">
              Download
            </Link>
            <Link to="/contact" className="hover:text-bone">
              Contact
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
