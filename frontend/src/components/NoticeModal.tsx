import { useEffect, useId, useRef } from "react";
import { AlertTriangle, CheckCircle2, Info, WifiOff, X } from "lucide-react";
import { cn } from "../lib/cn";

export type NoticeTone = "error" | "success" | "info" | "offline";

export type NoticePayload = {
  title: string;
  message: string;
  tone?: NoticeTone;
  /** Primary button */
  actionLabel?: string;
  onAction?: () => void;
  /** Secondary / dismiss */
  dismissLabel?: string;
};

const TONE = {
  error: {
    icon: AlertTriangle,
    ring: "border-coral/30",
    iconWrap: "bg-coral/15 text-coral",
    bar: "bg-coral",
  },
  offline: {
    icon: WifiOff,
    ring: "border-coral/30",
    iconWrap: "bg-coral/15 text-coral",
    bar: "bg-coral",
  },
  success: {
    icon: CheckCircle2,
    ring: "border-lime/30",
    iconWrap: "bg-lime/15 text-lime",
    bar: "bg-lime",
  },
  info: {
    icon: Info,
    ring: "border-white/15",
    iconWrap: "bg-white/10 text-bone",
    bar: "bg-white/40",
  },
} as const;

type Props = NoticePayload & {
  open: boolean;
  onClose: () => void;
};

export function NoticeModal({
  open,
  onClose,
  title,
  message,
  tone = "error",
  actionLabel,
  onAction,
  dismissLabel = "Got it",
}: Props) {
  const titleId = useId();
  const descId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const t = TONE[tone];
  const Icon = t.icon;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // Focus panel for a11y
    panelRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[80] flex items-end justify-center p-4 sm:items-center" role="presentation">
      <button
        type="button"
        aria-label="Close"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-[fadeIn_0.15s_ease-out]"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        tabIndex={-1}
        className={cn(
          "relative w-full max-w-md overflow-hidden rounded-2xl border bg-ink-2 shadow-2xl outline-none",
          "animate-[riseIn_0.2s_ease-out]",
          t.ring
        )}
      >
        <div className={cn("h-1 w-full", t.bar)} />
        <div className="p-6">
          <div className="flex items-start gap-4">
            <div className={cn("grid h-11 w-11 shrink-0 place-items-center rounded-xl", t.iconWrap)}>
              <Icon className="h-5 w-5" strokeWidth={2.25} />
            </div>
            <div className="min-w-0 flex-1 pt-0.5">
              <h2 id={titleId} className="font-display text-lg font-semibold tracking-tight text-bone">
                {title}
              </h2>
              <p id={descId} className="mt-1.5 text-sm leading-relaxed text-muted">
                {message}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="-m-1 rounded-lg p-1.5 text-dim transition hover:bg-white/[0.06] hover:text-bone"
              aria-label="Dismiss"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button type="button" onClick={onClose} className="btn-ghost justify-center px-4 py-2.5">
              {dismissLabel}
            </button>
            {actionLabel && (
              <button
                type="button"
                className="btn-primary justify-center px-4 py-2.5"
                onClick={() => {
                  onAction?.();
                  onClose();
                }}
              >
                {actionLabel}
              </button>
            )}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
        @keyframes riseIn {
          from { opacity: 0; transform: translateY(12px) scale(0.98) }
          to { opacity: 1; transform: translateY(0) scale(1) }
        }
      `}</style>
    </div>
  );
}
