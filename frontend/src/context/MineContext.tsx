import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { mine, ApiError } from "../lib/api";
import type { MineInput } from "../lib/types";
import { sourceLabel } from "../lib/format";
import { useToast } from "./ToastContext";

export type MineState =
  | { status: "idle" }
  | {
      status: "running";
      phase: "uploading" | "processing";
      startedAt: number;
      label: string;
      kind: MineInput["kind"];
      loaded: number;
      total: number;
      maxClips: number;
      style: string;
    }
  | { status: "error"; message: string; offline: boolean };

interface MineApi {
  state: MineState;
  start: (input: MineInput) => void;
  cancel: () => void;
  dismissError: () => void;
}

const Ctx = createContext<MineApi | null>(null);

/**
 * Owns the (very long) processing request so it survives route changes:
 * users can browse History while a mine is running and get a toast when it lands.
 */
export function MineProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<MineState>({ status: "idle" });
  const ctrl = useRef<AbortController | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const pathRef = useRef(location.pathname);
  pathRef.current = location.pathname;
  const { push } = useToast();

  const start = useCallback(
    (input: MineInput) => {
      if (ctrl.current) return;
      const controller = new AbortController();
      ctrl.current = controller;
      const label = input.kind === "file" ? input.file.name : sourceLabel(input.url, "url");
      setState({
        status: "running",
        phase: input.kind === "file" ? "uploading" : "processing",
        startedAt: Date.now(),
        label,
        kind: input.kind,
        loaded: 0,
        total: input.kind === "file" ? input.file.size : 0,
        maxClips: input.maxClips,
        style: input.style,
      });

      mine(input, {
        signal: controller.signal,
        onUploadProgress: (loaded, total) =>
          setState((s) => (s.status === "running" ? { ...s, loaded, total } : s)),
        onUploadDone: () => setState((s) => (s.status === "running" ? { ...s, phase: "processing" } : s)),
      })
        .then((res) => {
          setState({ status: "idle" });
          if (pathRef.current === "/") navigate(`/jobs/${res.job_id}`);
          else
            push({
              title: "Your clips are ready",
              description: res.message,
              action: { label: "View clips", to: `/jobs/${res.job_id}` },
            });
        })
        .catch((e: Error) => {
          if (e.name === "AbortError") return setState({ status: "idle" });
          setState({
            status: "error",
            message: e.message || "Something went wrong while mining.",
            offline: e instanceof ApiError && e.offline,
          });
        })
        .finally(() => {
          ctrl.current = null;
        });
    },
    [navigate, push]
  );

  const cancel = useCallback(() => ctrl.current?.abort(), []);
  const dismissError = useCallback(() => setState((s) => (s.status === "error" ? { status: "idle" } : s)), []);

  // Closing the tab mid-run would drop the response, so ask first.
  useEffect(() => {
    if (state.status !== "running") return;
    const h = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [state.status]);

  const value = useMemo(() => ({ state, start, cancel, dismissError }), [state, start, cancel, dismissError]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useMine() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useMine must be used within MineProvider");
  return ctx;
}
