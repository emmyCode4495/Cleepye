import { useEffect, useState } from "react";

export function useElapsed(startedAt: number | null) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (startedAt == null) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [startedAt]);
  return startedAt == null ? 0 : Math.max(0, Math.floor((now - startedAt) / 1000));
}
