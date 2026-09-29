import { scoreTier } from "../lib/format";

export function ScoreRing({ score, size = 48, stroke = 4 }: { score: number; size?: number; stroke?: number }) {
  const { color, label } = scoreTier(score);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={`Viral score ${score} out of 100 (${label})`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgb(255 255 255 / 0.08)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${c * pct} ${c}`}
          style={{ transition: "stroke-dasharray .8s cubic-bezier(.2,.7,.2,1)" }}
        />
      </svg>
      <span className="absolute inset-0 grid place-items-center font-display font-bold tabular-nums" style={{ fontSize: size * 0.34 }}>
        {Math.round(score)}
      </span>
    </div>
  );
}
