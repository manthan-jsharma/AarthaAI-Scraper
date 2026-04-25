interface ScoreBarProps {
  label: string;
  score: number;
  max: number;
}

function barColor(pct: number): string {
  if (pct >= 75) return "bg-[#E8B84B]";
  if (pct >= 45) return "bg-orange-400";
  return "bg-red-500";
}

export default function ScoreBar({ label, score, max }: ScoreBarProps) {
  const pct = Math.round((score / max) * 100);
  return (
    <div className="flex items-center gap-4">
      <span className="w-36 text-sm text-white/40 shrink-0">{label}</span>
      <div className="flex-1 bg-white/5 rounded-full h-1.5">
        <div
          className={`${barColor(pct)} h-1.5 rounded-full transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm font-semibold text-white/70 w-12 text-right">
        {score}<span className="text-white/20">/{max}</span>
      </span>
    </div>
  );
}
