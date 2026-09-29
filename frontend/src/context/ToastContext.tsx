import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, AlertTriangle, X } from "lucide-react";

interface ToastInput {
  title: string;
  description?: string;
  tone?: "success" | "error";
  action?: { label: string; to: string };
}
interface Toast extends ToastInput {
  id: number;
}

const ToastCtx = createContext<{ push: (t: ToastInput) => void } | null>(null);
let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const push = useCallback(
    (t: ToastInput) => {
      const id = nextId++;
      setToasts((list) => [...list.slice(-2), { ...t, id }]);
      window.setTimeout(() => dismiss(id), 9000);
    },
    [dismiss]
  );
  const value = useMemo(() => ({ push }), [push]);

  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-[60] flex flex-col items-center gap-2 px-4 sm:bottom-6 sm:items-end sm:px-6"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className="pointer-events-auto flex w-full max-w-sm animate-toast-in items-start gap-3 rounded-2xl border bg-ink-2/95 p-4 shadow-2xl backdrop-blur"
          >
            {t.tone === "error" ? (
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-coral" />
            ) : (
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-lime" />
            )}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{t.title}</p>
              {t.description && <p className="mt-0.5 text-sm text-muted">{t.description}</p>}
              {t.action && (
                <Link to={t.action.to} onClick={() => dismiss(t.id)} className="mt-2 inline-block text-sm font-medium text-lime hover:underline">
                  {t.action.label} →
                </Link>
              )}
            </div>
            <button onClick={() => dismiss(t.id)} aria-label="Dismiss" className="-m-1 rounded-md p-1 text-dim hover:text-bone">
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastCtx);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
