import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { NoticeModal, type NoticePayload, type NoticeTone } from "../components/NoticeModal";

type NoticeApi = {
  show: (n: NoticePayload) => void;
  error: (title: string, message: string, extra?: Partial<NoticePayload>) => void;
  success: (title: string, message: string, extra?: Partial<NoticePayload>) => void;
  info: (title: string, message: string, extra?: Partial<NoticePayload>) => void;
  offline: (message?: string) => void;
  close: () => void;
};

const NoticeCtx = createContext<NoticeApi | null>(null);

export function NoticeProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [payload, setPayload] = useState<NoticePayload>({
    title: "",
    message: "",
    tone: "error",
  });

  const close = useCallback(() => setOpen(false), []);

  const show = useCallback((n: NoticePayload) => {
    setPayload({
      tone: "error",
      dismissLabel: "Got it",
      ...n,
    });
    setOpen(true);
  }, []);

  const withTone = useCallback(
    (tone: NoticeTone) =>
      (title: string, message: string, extra?: Partial<NoticePayload>) => {
        show({ title, message, tone, ...extra });
      },
    [show]
  );

  const value = useMemo<NoticeApi>(
    () => ({
      show,
      error: withTone("error"),
      success: withTone("success"),
      info: withTone("info"),
      offline: (message) =>
        show({
          tone: "offline",
          title: "Engine offline",
          message:
            message ||
            "The local engine isn’t running. Start it with `python run.py`, then try again.",
        }),
      close,
    }),
    [show, withTone, close]
  );

  return (
    <NoticeCtx.Provider value={value}>
      {children}
      <NoticeModal
        open={open}
        onClose={close}
        title={payload.title}
        message={payload.message}
        tone={payload.tone}
        actionLabel={payload.actionLabel}
        onAction={payload.onAction}
        dismissLabel={payload.dismissLabel}
      />
    </NoticeCtx.Provider>
  );
}

export function useNotice() {
  const ctx = useContext(NoticeCtx);
  if (!ctx) throw new Error("useNotice must be used within NoticeProvider");
  return ctx;
}
