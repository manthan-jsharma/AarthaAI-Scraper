"use client";

import { useState } from "react";
import Link from "next/link";
import { triggerPipeline } from "@/lib/api";

export default function Header() {
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);

  async function handleRun() {
    setRunning(true);
    setDone(false);
    try {
      await triggerPipeline();
      setDone(true);
    } finally {
      setRunning(false);
    }
  }

  return (
    <header className="border-b border-white/10 bg-[#0a0a0a]/90 backdrop-blur-sm sticky top-0 z-10">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-[#E8B84B] font-bold text-lg tracking-tight">BrokerRank</span>
            <span className="text-xs text-white/30 font-medium border border-white/10 px-2 py-0.5 rounded-full">
              Bangalore
            </span>
          </Link>
          <nav className="flex items-center gap-1">
            <Link href="/" className="text-sm text-white/40 hover:text-white/80 px-3 py-1.5 rounded-lg transition-colors">
              Brokers
            </Link>
            <Link href="/rankings" className="text-sm text-white/40 hover:text-white/80 px-3 py-1.5 rounded-lg transition-colors">
              Rankings
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          {done && (
            <span className="text-xs text-[#E8B84B] font-medium">Pipeline started</span>
          )}
          <button
            onClick={handleRun}
            disabled={running}
            className="bg-[#E8B84B] hover:bg-[#d4a43d] disabled:opacity-50 text-black text-sm font-bold px-5 py-2 rounded-full transition-colors"
          >
            {running ? "Starting..." : "RUN PIPELINE →"}
          </button>
        </div>
      </div>
    </header>
  );
}
