import Link from "next/link";
import type { Broker } from "@/lib/api";
import ScoreBadge from "./ScoreBadge";

interface BrokerCardProps {
  broker: Broker;
  rank: number;
}

const SCORE_DIMS = [
  { key: "score_website", label: "Website", max: 30 },
  { key: "score_social_media", label: "Social", max: 20 },
  { key: "score_google_business", label: "Google Biz", max: 15 },
  { key: "score_property_portals", label: "Portals", max: 15 },
] as const;

function MiniBar({ score, max }: { score: number; max: number }) {
  const pct = Math.round((score / max) * 100);
  const color = pct >= 75 ? "bg-[#E8B84B]" : pct >= 45 ? "bg-orange-400" : "bg-red-500";
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-14 bg-white/5 rounded-full h-1">
        <div className={`${color} h-1 rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-white/30">{score}</span>
    </div>
  );
}

export default function BrokerCard({ broker, rank }: BrokerCardProps) {
  return (
    <Link href={`/broker/${broker.id}`}>
      <div className="bg-[#111111] border border-white/8 rounded-2xl p-5 hover:border-[#E8B84B]/40 hover:bg-[#141414] transition-all cursor-pointer group">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="text-xs font-bold text-white/20 mt-1 w-5">#{rank}</span>
            <div>
              <h3 className="font-semibold text-white group-hover:text-[#E8B84B] transition-colors leading-tight">
                {broker.name}
              </h3>
              <p className="text-sm text-white/40 mt-0.5">{broker.area}</p>
              {broker.phone && (
                <p className="text-xs text-white/25 mt-1">{broker.phone}</p>
              )}
            </div>
          </div>
          <ScoreBadge score={broker.total_score} />
        </div>

        <div className="mt-4 grid grid-cols-2 gap-x-3 gap-y-2">
          {SCORE_DIMS.map(({ key, label, max }) => (
            <div key={key} className="flex items-center justify-between gap-2">
              <span className="text-xs text-white/25 w-16 shrink-0">{label}</span>
              <MiniBar score={broker[key]} max={max} />
            </div>
          ))}
        </div>

        {broker.sales_pitch && (
          <p className="mt-4 text-xs text-white/30 italic border-t border-white/5 pt-3 line-clamp-2">
            {broker.sales_pitch}
          </p>
        )}
      </div>
    </Link>
  );
}
