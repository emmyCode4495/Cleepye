import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";

export type EngineState = "checking" | "online" | "offline" | "busy";

/**
 * Polls /health. The engine runs a job synchronously, so while a mine is active
 * a slow/failed health check means "busy", not "offline".
 */
export function useEngineStatus(mining: boolean) {
  const [state, setState] = useState<EngineState>("checking");

  const check = useCallback(async () => {
    const ok = await api.health(mining ? 2500 : 4000);
    setState(ok ? "online" : mining ? "busy" : "offline");
  }, [mining]);

  useEffect(() => {
    let cancelled = false;
    const run = () => !cancelled && check();
    run();
    const id = window.setInterval(run, mining ? 20000 : 12000);
    const onFocus = () => run();
    window.addEventListener("focus", onFocus);
    return () => {
      cancelled = true;
      window.clearInterval(id);
      window.removeEventListener("focus", onFocus);
    };
  }, [check, mining]);

  return { state, recheck: check };
}
