import { BRAND } from "../lib/brand";

export function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="9" fill="rgb(var(--lime))" />
      <path d="M12 9.5v13l11-6.5z" fill="rgb(var(--lime-ink))" />
      <rect x="6.5" y="6.5" width="19" height="19" rx="5" fill="none" stroke="rgb(var(--lime-ink))" strokeOpacity=".22" strokeDasharray="2 3" />
    </svg>
  );
}

export function Logo() {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark />
      <span className="font-display text-[22px] font-bold leading-none tracking-tight" style={{ fontVariationSettings: '"wdth" 92' }}>
        {BRAND}
      </span>
    </span>
  );
}
