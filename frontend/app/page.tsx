"use client";

import { useEffect, useState, useCallback } from "react";
import Header from "@/components/Header";
import BrokerCard from "@/components/BrokerCard";
import { fetchBrokers, fetchAreas, type Broker } from "@/lib/api";

export default function DashboardPage() {
  const [brokers, setBrokers] = useState<Broker[]>([]);
  const [areas, setAreas] = useState<string[]>([]);
  const [area, setArea] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [data, areaList] = await Promise.all([
        fetchBrokers(area || undefined),
        fetchAreas(),
      ]);
      setBrokers(data);
      setAreas(areaList);
    } finally {
      setLoading(false);
    }
  }, [area]);

  useEffect(() => { load(); }, [load]);

  const filtered = brokers
    .filter((b) => b.total_score >= minScore)
    .filter((b) =>
      search
        ? b.name.toLowerCase().includes(search.toLowerCase()) ||
          b.area?.toLowerCase().includes(search.toLowerCase())
        : true
    );

  const avgScore = brokers.length
    ? Math.round(brokers.reduce((s, b) => s + b.total_score, 0) / brokers.length)
    : 0;

  return (
    <div className="min-h-screen bg-[#0a0a0a]">
      <Header />

      <main className="max-w-6xl mx-auto px-6 py-10">

        {/* Hero heading */}
        <div className="mb-10">
          <p className="text-xs text-[#E8B84B] font-semibold tracking-widest uppercase mb-3">
            AI-Powered Rankings
          </p>
          <h1 className="text-4xl font-bold text-white leading-tight">
            Bangalore&apos;s Top{" "}
            <span className="text-[#E8B84B]">Real Estate Brokers</span>
          </h1>
          <p className="text-white/40 mt-2 text-sm">
            Ranked by digital presence · Updated automatically
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { value: brokers.length, label: "Brokers Tracked" },
            { value: brokers.filter((b) => b.total_score >= 70).length, label: "High Scorers (70+)" },
            { value: avgScore, label: "Avg Score" },
          ].map(({ value, label }) => (
            <div key={label} className="bg-[#111111] border border-white/8 rounded-2xl p-5">
              <p className="text-3xl font-bold text-[#E8B84B]">{value}</p>
              <p className="text-xs text-white/30 mt-1">{label}</p>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="bg-[#111111] border border-white/8 rounded-2xl p-5 mb-8 flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-48">
            <label className="text-xs font-medium text-white/30 block mb-2">Search</label>
            <input
              type="text"
              placeholder="Broker name or area..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-white/20 focus:outline-none focus:border-[#E8B84B]/50"
            />
          </div>

          <div className="min-w-44">
            <label className="text-xs font-medium text-white/30 block mb-2">Area</label>
            <select
              value={area}
              onChange={(e) => setArea(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#E8B84B]/50"
            >
              <option value="" className="bg-[#111]">All Areas</option>
              {areas.map((a) => (
                <option key={a} value={a} className="bg-[#111]">{a}</option>
              ))}
            </select>
          </div>

          <div className="min-w-52">
            <label className="text-xs font-medium text-white/30 block mb-2">
              Min Score:{" "}
              <span className="text-[#E8B84B] font-bold">{minScore}</span>
            </label>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="w-full accent-[#E8B84B]"
            />
          </div>

          <button
            onClick={() => { setArea(""); setMinScore(0); setSearch(""); }}
            className="text-sm text-white/25 hover:text-white/50 transition-colors"
          >
            Clear
          </button>
        </div>

        {/* Count */}
        <p className="text-xs text-white/25 mb-4">
          Showing {filtered.length} broker{filtered.length !== 1 ? "s" : ""}
        </p>

        {/* Grid */}
        {loading ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-[#111111] border border-white/8 rounded-2xl h-44 animate-pulse" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-24 text-white/20">
            <p className="text-5xl mb-4">🏠</p>
            <p className="font-semibold text-white/40">No brokers found</p>
            <p className="text-sm mt-2">Run the pipeline to collect broker data</p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((broker, i) => (
              <BrokerCard key={broker.id} broker={broker} rank={i + 1} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
