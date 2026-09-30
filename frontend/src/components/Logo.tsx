import { BRAND } from "../lib/brand";
import { cn } from "../lib/cn";

/** Brand mark — official Cleepye logo asset (no play-button SVG). */
export function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <img
      src="/logo.png"
      alt=""
      width={32}
      height={32}
      className={cn("shrink-0 rounded-lg object-contain", className)}
      draggable={false}
    />
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <LogoMark className="h-9 w-9" />
      <span
        className="font-display text-[22px] font-bold leading-none tracking-tight"
        style={{ fontVariationSettings: '"wdth" 92' }}
      >
        <span className="text-bone">cleep</span>
        <span className="text-lime">ye</span>
      </span>
    </span>
  );
}
