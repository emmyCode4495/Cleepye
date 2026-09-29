import { useEffect } from "react";
import { BRAND } from "../lib/brand";

export function useDocumentTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${title} · ${BRAND}` : `${BRAND} — mine the moments worth clipping`;
  }, [title]);
}
