interface ScoreBadgeProps {
  score: number;
  size?: "sm" | "lg";
}

function badgeColor(score: number): string {
  if (score >= 70) return "text-[#E8B84B] border-[#E8B84B]/40 bg-[#E8B84B]/10";
  if (score >= 45) return "text-orange-400 border-orange-400/40 bg-orange-400/10";
  return "text-red-400 border-red-400/40 bg-red-400/10";
}

export default function ScoreBadge({ score, size = "sm" }: ScoreBadgeProps) {
  return (
    <span
      className={`inline-flex items-center font-bold border rounded-full ${badgeColor(score)} ${
        size === "lg" ? "text-4xl px-6 py-2" : "text-sm px-3 py-0.5"
      }`}
    >
      {score}
    </span>
  );
}
