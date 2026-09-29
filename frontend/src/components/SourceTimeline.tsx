import { timecode, scoreTier } from "../lib/format";
import type { Clip } from "../lib/types";
import { cn } from "../lib/cn";

/** Plots each clip on the source video's timeline so you can see where the good stuff lives. */
export function SourceTimeline({ clips, duration, selected, onSelect }: { clips: Clip[]; duration: number | null; selected: number; onSelect: (index: number) => void }) {
  const total = Math.max(duration ?? 0, ...clips.map((c) => c.end), 1);
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  return (
    <div>
      <div className="relative h-16 rounded-xl border bg-ink-1">
        <div className="ruler pointer-events-none absolute inset-x-0 bottom-0 h-full opacity-50" />
        {clips.map((c) => {
          const left = (c.start / total) * 100;
          const width = Math.max(((c.end - c.start) / total) * 100, 1.2);
          const { color } = scoreTier(c.score);
          const active = c.index === selected;
          return (
            <button
              key={c.index}
              onClick={() => onSelect(c.index)}
              aria-label={`Clip ${c.index}: ${c.title || "Untitled"}, ${timecode(c.start)} to ${timecode(c.end)}, score ${c.score}`}
              aria-pressed={active}
              title={`#${c.index} · ${timecode(c.start)}–${timecode(c.end)} · score ${c.score}`}
              className={cn("group absolute rounded-md transition-all", active ? "bottom-0 top-0 z-10 shadow-[0_0_0_2px_rgb(var(--ink)),0_0_0_4px_currentColor]" : "bottom-2 top-2 opacity-85 hover:opacity-100")}
              style={{ left: `${left}%`, width: `${width}%`, background: color, color }}
            >
              <span className="pointer-events-none absolute -top-5 left-1/2 -translate-x-1/2 font-mono text-[10px] text-bone opacity-0 transition group-hover:opacity-100 group-aria-pressed:opacity-100">#{c.index}</span>
            </button>
          );
        })}
      </div>
      <div className="mt-2 flex justify-between font-mono text-[11px] text-dim" aria-hidden>
        {ticks.map((t) => (
          <span key={t}>{timecode(total * t)}</span>
        ))}
      </div>
    </div>
  );
}
