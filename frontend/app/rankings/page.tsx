"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import Header from "@/components/Header";
import {
  fetchPipelineRuns,
  fetchRankingsForRun,
  type PipelineRun,
  type RankedBroker,
} from "@/lib/api";

// Score dimension columns shown in the table
const DIMS = [
  { key: "score_website",          label: "WEB",    max: 30 },
  { key: "score_social_media",     label: "SOC",    max: 20 },
  { key: "score_property_portals", label: "PRT",    max: 15 },
  { key: "score_google_business",  label: "GMB",    max: 15 },
  { key: "score_linkedin",         label: "LI",     max: 10 },
  { key: "score_listings",         label: "LST",    max: 5  },
  { key: "score_video",            label: "VID",    max: 5  },
] as const;

type DimKey = typeof DIMS[number]["key"];

// Color based on % of max score for each dimension
function dimColor(score: number, max: number): string {
  const pct = score / max;
  if (pct >= 0.7) return "text-[#4ade80]";
  if (pct >= 0.4) return "text-[#E8B84B]";
  return "text-white/25";
}

// Color for total score
function totalColor(score: number): string {
  if (score >= 70) return "text-[#4ade80]";
  if (score >= 40) return "text-[#E8B84B]";
  return "text-[#f87171]";
}

// Delta badge — compares this run's score to previous run
function DeltaBadge({ delta }: { delta: number | null }) {
  if (delta === null) return <span className="text-white/20 font-mono text-xs">—</span>;
  if (delta === 0) return <span className="text-white/20 font-mono text-xs">±0</span>;
  const positive = delta > 0;
  return (
    <span className={`font-mono text-xs font-bold ${positive ? "text-[#4ade80]" : "text-[#f87171]"}`}>
      {positive ? "+" : ""}{delta}
      <span className="ml-0.5 text-[10px]">{positive ? "▲" : "▼"}</span>
    </span>
  );
}

// Status pill for pipeline runs
function RunStatusPill({ status }: { status: string }) {
  if (status === "completed") return null;
  if (status === "running") return (
    <span className="text-[10px] bg-[#E8B84B]/20 text-[#E8B84B] px-1.5 py-0.5 rounded font-medium">LIVE</span>
  );
  return (
    <span className="text-[10px] bg-[#f87171]/20 text-[#f87171] px-1.5 py-0.5 rounded font-medium">FAILED</span>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

type TimeFilter = "all" | "week" | "month";

export default function RankingsPage() {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [currentRows, setCurrentRows] = useState<RankedBroker[]>([]);
  const [prevRows, setPrevRows] = useState<RankedBroker[]>([]);
  const [loading, setLoading] = useState(true);
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("all");
  const [areaFilter, setAreaFilter] = useState("");

  // Load pipeline runs on mount
  useEffect(() => {
    fetchPipelineRuns().then((data) => {
      setRuns(data);
      const latest = data.find((r) => r.status === "completed") ?? data[0];
      if (latest) setSelectedRunId(latest.id);
    });
  }, []);

  // Load rankings when selected run changes
  useEffect(() => {
    if (!selectedRunId) return;
    setLoading(true);

    const selectedRun = runs.find((r) => r.id === selectedRunId);
    const prevRun = selectedRun
      ? runs.find((r) => r.run_number === selectedRun.run_number - 1)
      : null;

    const tasks = [
      fetchRankingsForRun(selectedRunId).then(setCurrentRows),
      prevRun
        ? fetchRankingsForRun(prevRun.id).then(setPrevRows)
        : Promise.resolve(setPrevRows([])),
    ];

    Promise.all(tasks).finally(() => setLoading(false));
  }, [selectedRunId, runs]);

  // Build prev score lookup map: broker_id → total_score
  const prevScoreMap = useMemo(() => {
    const map: Record<string, number> = {};
    prevRows.forEach((r) => { map[r.broker_id] = r.total_score; });
    return map;
  }, [prevRows]);

  // Build prev rank lookup map
  const prevRankMap = useMemo(() => {
    const map: Record<string, number> = {};
    prevRows.forEach((r) => { map[r.broker_id] = r.rank; });
    return map;
  }, [prevRows]);

  // Filter runs by time period for the run selector
  const filteredRuns = useMemo(() => {
    if (timeFilter === "all") return runs;
    const now = new Date();
    const cutoff = new Date(now);
    if (timeFilter === "week") cutoff.setDate(now.getDate() - 7);
    if (timeFilter === "month") cutoff.setMonth(now.getMonth() - 1);
    return runs.filter((r) => new Date(r.started_at) >= cutoff);
  }, [runs, timeFilter]);

  // Filter rows by area
  const filteredRows = useMemo(() => {
    if (!areaFilter.trim()) return currentRows;
    return currentRows.filter((r) =>
      r.brokers?.area?.toLowerCase().includes(areaFilter.toLowerCase())
    );
  }, [currentRows, areaFilter]);

  const selectedRun = runs.find((r) => r.id === selectedRunId);

  return (
    <div className="min-h-screen bg-[#0a0a0a]">
      <Header />

      <main className="max-w-[1400px] mx-auto px-6 py-8 space-y-6">

        {/* Page header */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-[#E8B84B] font-semibold tracking-widest uppercase mb-1">Live Rankings</p>
            <h1 className="text-2xl font-bold text-white">Broker Performance Board</h1>
          </div>
          {selectedRun && (
            <div className="text-right">
              <p className="text-xs text-white/30">Showing Run #{selectedRun.run_number}</p>
              <p className="text-xs text-white/20">{selectedRun.brokers_scraped} brokers · {formatDate(selectedRun.started_at)}</p>
            </div>
          )}
        </div>

        {/* Controls row */}
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">

          {/* Time filter */}
          <div className="flex items-center gap-1 bg-[#111] border border-white/8 rounded-xl p-1">
            {(["all", "week", "month"] as TimeFilter[]).map((f) => (
              <button
                key={f}
                onClick={() => setTimeFilter(f)}
                className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  timeFilter === f
                    ? "bg-[#E8B84B] text-black"
                    : "text-white/40 hover:text-white/70"
                }`}
              >
                {f === "all" ? "All Time" : f === "week" ? "This Week" : "This Month"}
              </button>
            ))}
          </div>

          {/* Area search */}
          <input
            type="text"
            placeholder="Filter by area..."
            value={areaFilter}
            onChange={(e) => setAreaFilter(e.target.value)}
            className="bg-[#111] border border-white/8 rounded-xl px-4 py-2 text-sm text-white/70 placeholder:text-white/20 focus:outline-none focus:border-[#E8B84B]/40 w-48"
          />
        </div>

        {/* Pipeline run selector */}
        {filteredRuns.length > 0 && (
          <div className="flex gap-2 overflow-x-auto pb-1">
            {filteredRuns.map((run) => (
              <button
                key={run.id}
                onClick={() => setSelectedRunId(run.id)}
                className={`shrink-0 flex items-center gap-2 px-4 py-2 rounded-xl border text-xs font-semibold transition-all ${
                  selectedRunId === run.id
                    ? "bg-[#E8B84B]/10 border-[#E8B84B]/50 text-[#E8B84B]"
                    : "border-white/8 text-white/30 hover:text-white/60 hover:border-white/20"
                }`}
              >
                <span>Run #{run.run_number}</span>
                <RunStatusPill status={run.status} />
                <span className="text-white/20 font-normal">
                  {new Date(run.started_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                </span>
              </button>
            ))}
          </div>
        )}

        {/* Rankings table */}
        <div className="bg-[#0d0d0d] border border-white/8 rounded-2xl overflow-hidden">

          {/* Table header */}
          <div className="grid grid-cols-[3rem_1fr_10rem_6rem_5rem_repeat(7,3.5rem)] gap-x-2 px-4 py-3 border-b border-white/5">
            <span className="text-[10px] text-white/20 font-bold tracking-widest uppercase">RNK</span>
            <span className="text-[10px] text-white/20 font-bold tracking-widest uppercase">BROKER</span>
            <span className="text-[10px] text-white/20 font-bold tracking-widest uppercase">AREA</span>
            <span className="text-[10px] text-white/20 font-bold tracking-widest uppercase text-right">SCORE</span>
            <span className="text-[10px] text-white/20 font-bold tracking-widest uppercase text-center">Δ RUN</span>
            {DIMS.map((d) => (
              <span key={d.key} className="text-[10px] text-white/20 font-bold tracking-widest uppercase text-center">{d.label}</span>
            ))}
          </div>

          {/* Loading state */}
          {loading && (
            <div className="space-y-px">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="grid grid-cols-[3rem_1fr_10rem_6rem_5rem_repeat(7,3.5rem)] gap-x-2 px-4 py-3 animate-pulse">
                  <div className="h-3 bg-white/5 rounded w-6" />
                  <div className="h-3 bg-white/5 rounded w-40" />
                  <div className="h-3 bg-white/5 rounded w-24" />
                  <div className="h-3 bg-white/5 rounded w-10 ml-auto" />
                  <div className="h-3 bg-white/5 rounded w-8 mx-auto" />
                  {DIMS.map((d) => <div key={d.key} className="h-3 bg-white/5 rounded w-6 mx-auto" />)}
                </div>
              ))}
            </div>
          )}

          {/* No data */}
          {!loading && filteredRows.length === 0 && (
            <div className="py-20 text-center">
              <p className="text-white/20 text-sm">
                {runs.length === 0 ? "No pipeline runs yet — run the pipeline first" : "No brokers match this filter"}
              </p>
            </div>
          )}

          {/* Data rows */}
          {!loading && filteredRows.map((row, i) => {
            const broker = row.brokers;
            const prevScore = prevScoreMap[row.broker_id] ?? null;
            const delta = prevScore !== null ? row.total_score - prevScore : null;
            const prevRank = prevRankMap[row.broker_id] ?? null;
            const rankDelta = prevRank !== null ? prevRank - row.rank : null;

            return (
              <Link
                key={row.id}
                href={`/broker/${broker?.id}`}
                className={`grid grid-cols-[3rem_1fr_10rem_6rem_5rem_repeat(7,3.5rem)] gap-x-2 px-4 py-3 border-b border-white/[0.03] hover:bg-white/[0.03] transition-colors group ${
                  i === 0 ? "bg-[#E8B84B]/[0.03]" : ""
                }`}
              >
                {/* Rank */}
                <div className="flex items-center gap-1">
                  <span className={`font-mono text-sm font-bold ${
                    i === 0 ? "text-[#E8B84B]" : i === 1 ? "text-white/60" : i === 2 ? "text-[#cd7f32]/70" : "text-white/25"
                  }`}>
                    {row.rank}
                  </span>
                  {rankDelta !== null && rankDelta !== 0 && (
                    <span className={`text-[9px] ${rankDelta > 0 ? "text-[#4ade80]" : "text-[#f87171]"}`}>
                      {rankDelta > 0 ? "▲" : "▼"}
                    </span>
                  )}
                </div>

                {/* Broker name */}
                <div className="min-w-0">
                  <p className="text-sm text-white/80 font-medium truncate group-hover:text-white transition-colors">
                    {broker?.name ?? "—"}
                  </p>
                  {broker?.phone && (
                    <p className="text-[11px] text-white/20 font-mono mt-0.5">{broker.phone}</p>
                  )}
                </div>

                {/* Area */}
                <span className="text-xs text-white/30 truncate self-center">{broker?.area ?? "—"}</span>

                {/* Total score */}
                <div className="text-right self-center">
                  <span className={`font-mono text-base font-bold ${totalColor(row.total_score)}`}>
                    {row.total_score}
                  </span>
                </div>

                {/* Delta */}
                <div className="text-center self-center">
                  <DeltaBadge delta={delta} />
                </div>

                {/* Dimension scores */}
                {DIMS.map((d) => {
                  const score = row[d.key as DimKey] ?? 0;
                  return (
                    <div key={d.key} className="text-center self-center">
                      <span className={`font-mono text-xs font-semibold ${dimColor(score, d.max)}`}>
                        {score}
                      </span>
                    </div>
                  );
                })}
              </Link>
            );
          })}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-6 text-[11px] text-white/20 pb-4">
          <span><span className="text-[#4ade80]">■</span> Strong ≥70%</span>
          <span><span className="text-[#E8B84B]">■</span> Average 40–70%</span>
          <span><span className="text-white/25">■</span> Weak &lt;40%</span>
          <span className="ml-4">WEB=Website · SOC=Social · PRT=Portals · GMB=Google · LI=LinkedIn · LST=Listings · VID=Video</span>
        </div>

      </main>
    </div>
  );
}
