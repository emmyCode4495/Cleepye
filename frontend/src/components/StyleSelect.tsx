import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Check, ChevronDown } from "lucide-react";
import { outlineShadow, type CaptionLook } from "../lib/captionStyles";
import { cn } from "../lib/cn";

function Sample({ look, className }: { look: CaptionLook; className?: string }) {
  return (
    <span className={cn("grid shrink-0 place-items-center rounded-lg bg-black/70 px-3", className)}>
      <span
        style={{
          fontFamily: look.font,
          fontWeight: look.weight,
          fontSize: 18 * Math.min(look.size, 1.05),
          color: look.primary,
          textTransform: look.uppercase ? "uppercase" : undefined,
          textShadow: outlineShadow("1px"),
          whiteSpace: "nowrap",
        }}
      >
        Say <span style={{ color: look.highlight }}>it</span>
      </span>
    </span>
  );
}

const WORDS = ["This", "is", "the", "moment", "that", "changes", "everything"];

/** Wide, low-key animated sample of how the chosen style reads word by word. */
function CaptionStrip({ look }: { look: CaptionLook }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setI((n) => (n + 1) % WORDS.length), 520);
    return () => window.clearInterval(id);
  }, []);
  return (
    <div className="relative mt-3 grid h-20 place-items-center overflow-hidden rounded-xl border bg-black/70 px-4" aria-hidden>
      <div className="ruler pointer-events-none absolute inset-x-0 bottom-0 h-full opacity-20" />
      <p
        className="relative text-center leading-tight"
        style={{
          fontFamily: look.font,
          fontWeight: look.weight,
          fontSize: `clamp(18px, 3.4vw, ${26 * look.size}px)`,
          textShadow: outlineShadow(`${Math.max(1, look.outline * 0.6)}px`),
          textTransform: look.uppercase ? "uppercase" : undefined,
        }}
      >
        {WORDS.map((w, k) => (
          <span key={w} className="mx-[0.14em] inline-block" style={{ color: k === i ? look.highlight : look.primary }}>
            {w}
          </span>
        ))}
      </p>
      <span className="absolute bottom-2 right-3 font-mono text-[10px] uppercase tracking-widest text-dim">Preview</span>
    </div>
  );
}

export function StyleSelect({ looks, value, onChange }: { looks: CaptionLook[]; value: string; onChange: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const uid = useId();
  const selectedIdx = Math.max(0, looks.findIndex((l) => l.id === value));
  const selected = looks[selectedIdx] ?? looks[0];

  function openMenu() {
    setActive(selectedIdx);
    setOpen(true);
  }
  function close(refocus = true) {
    setOpen(false);
    if (refocus) trigger.current?.focus();
  }
  function choose(i: number) {
    onChange(looks[i].id);
    close();
  }

  useEffect(() => {
    if (!open) return;
    list.current?.focus();
    const down = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", down);
    return () => document.removeEventListener("mousedown", down);
  }, [open]);

  useEffect(() => {
    if (open) document.getElementById(`${uid}-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [active, open, uid]);

  function onTriggerKey(e: KeyboardEvent) {
    if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) {
      e.preventDefault();
      openMenu();
    }
  }
  function onListKey(e: KeyboardEvent) {
    const last = looks.length - 1;
    switch (e.key) {
      case "ArrowDown": e.preventDefault(); setActive((a) => Math.min(last, a + 1)); break;
      case "ArrowUp": e.preventDefault(); setActive((a) => Math.max(0, a - 1)); break;
      case "Home": e.preventDefault(); setActive(0); break;
      case "End": e.preventDefault(); setActive(last); break;
      case "Enter": case " ": e.preventDefault(); choose(active); break;
      case "Escape": e.preventDefault(); close(); break;
      case "Tab": setOpen(false); break;
      default: {
        const k = e.key.toLowerCase();
        if (k.length === 1) {
          const idx = looks.findIndex((l, n) => n > active && l.name.toLowerCase().startsWith(k));
          const wrap = idx === -1 ? looks.findIndex((l) => l.name.toLowerCase().startsWith(k)) : idx;
          if (wrap !== -1) setActive(wrap);
        }
      }
    }
  }

  return (
    <div>
    <div ref={root} className="relative">
      <button
        ref={trigger}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={`${uid}-list`}
        aria-label={`Caption style: ${selected.name}`}
        onClick={() => (open ? close(false) : openMenu())}
        onKeyDown={onTriggerKey}
        className={cn("field flex items-center gap-4 !py-3 text-left", open && "!border-lime/60 !ring-4 !ring-lime/10")}
      >
        <Sample look={selected} className="h-12 w-24" />
        <span className="min-w-0 flex-1">
          <span className="block font-medium">{selected.name}</span>
          <span className="mt-0.5 block text-sm leading-snug text-muted">{selected.blurb}</span>
        </span>
        <ChevronDown className={cn("h-5 w-5 shrink-0 text-dim transition-transform", open && "rotate-180 text-lime")} />
      </button>

      {open && (
        <ul
          ref={list}
          id={`${uid}-list`}
          role="listbox"
          tabIndex={-1}
          aria-label="Caption style"
          aria-activedescendant={`${uid}-${active}`}
          onKeyDown={onListKey}
          className="absolute inset-x-0 top-[calc(100%+8px)] z-30 max-h-[min(26rem,55vh)] animate-toast-in overflow-auto rounded-2xl border bg-ink-2 p-1.5 shadow-[0_24px_60px_-12px_rgb(0_0_0/0.9)] focus:outline-none"
        >
          {looks.map((l, i) => {
            const isSel = l.id === value;
            return (
              <li
                key={l.id}
                id={`${uid}-${i}`}
                role="option"
                aria-selected={isSel}
                onMouseMove={() => setActive(i)}
                onClick={() => choose(i)}
                className={cn("flex cursor-pointer items-center gap-4 rounded-xl px-3 py-3 transition-colors", i === active ? "bg-white/[0.07]" : "", isSel && "ring-1 ring-inset ring-lime/40")}
              >
                <Sample look={l} className="h-12 w-24" />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">{l.name}</span>
                  <span className="mt-0.5 block text-sm leading-snug text-muted">{l.blurb}</span>
                </span>
                <Check className={cn("h-4 w-4 shrink-0 text-lime", !isSel && "invisible")} />
              </li>
            );
          })}
        </ul>
      )}
    </div>
    <CaptionStrip look={selected} />
    </div>
  );
}
