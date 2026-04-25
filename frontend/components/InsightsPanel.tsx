interface InsightsPanelProps {
  strengths: string | null;
  weaknesses: string | null;
  missed_opportunities: string | null;
  sales_pitch: string | null;
}

const SECTIONS = [
  { key: "strengths", title: "Strengths", border: "border-[#E8B84B]/40", bg: "bg-[#E8B84B]/5", text: "text-[#E8B84B]" },
  { key: "weaknesses", title: "Weaknesses", border: "border-red-500/40", bg: "bg-red-500/5", text: "text-red-400" },
  { key: "missed_opportunities", title: "Missed Opportunities", border: "border-orange-400/40", bg: "bg-orange-400/5", text: "text-orange-400" },
  { key: "sales_pitch", title: "Sales Pitch", border: "border-blue-400/40", bg: "bg-blue-400/5", text: "text-blue-300" },
] as const;

export default function InsightsPanel({ strengths, weaknesses, missed_opportunities, sales_pitch }: InsightsPanelProps) {
  const data = { strengths, weaknesses, missed_opportunities, sales_pitch };
  const hasAny = Object.values(data).some(Boolean);

  if (!hasAny) {
    return (
      <p className="text-sm text-white/25 italic py-4">
        AI insights not generated yet. Run the full pipeline to generate.
      </p>
    );
  }

  return (
    <div className="grid gap-3">
      {SECTIONS.map(({ key, title, border, bg, text }) =>
        data[key] ? (
          <div key={key} className={`rounded-xl border ${border} ${bg} p-4`}>
            <h4 className={`font-semibold text-sm mb-2 ${text}`}>{title}</h4>
            <p className="text-sm text-white/60 whitespace-pre-line leading-relaxed">{data[key]}</p>
          </div>
        ) : null
      )}
    </div>
  );
}
