"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import Header from "@/components/Header";
import ScoreBar from "@/components/ScoreBar";
import ScoreBadge from "@/components/ScoreBadge";
import InsightsPanel from "@/components/InsightsPanel";
import { fetchBroker, type Broker } from "@/lib/api";

const SCORE_DIMS = [
  { key: "score_website", label: "Website", max: 30 },
  { key: "score_social_media", label: "Social Media", max: 20 },
  { key: "score_google_business", label: "Google Business", max: 15 },
  { key: "score_property_portals", label: "Property Portals", max: 15 },
  { key: "score_linkedin", label: "LinkedIn", max: 10 },
  { key: "score_listings", label: "Listings", max: 5 },
  { key: "score_video", label: "Video Presence", max: 5 },
] as const;

const PORTAL_LINKS: { key: keyof Broker; label: string }[] = [
  { key: "website_url", label: "Website" },
  { key: "google_maps_url", label: "Google Maps" },
  { key: "magicbricks_url", label: "MagicBricks" },
  { key: "acres99_url", label: "99acres" },
  { key: "housing_url", label: "Housing.com" },
  { key: "nobroker_url", label: "NoBroker" },
  { key: "justdial_url", label: "JustDial" },
  { key: "linkedin_url", label: "LinkedIn" },
  { key: "instagram_url", label: "Instagram" },
];

export default function BrokerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [broker, setBroker] = useState<Broker | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchBroker(id)
      .then(setBroker)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a]">
        <Header />
        <div className="max-w-3xl mx-auto px-6 py-12 space-y-4 animate-pulse">
          <div className="h-8 bg-white/5 rounded-xl w-64" />
          <div className="h-4 bg-white/5 rounded w-40" />
          <div className="h-48 bg-[#111] rounded-2xl" />
        </div>
      </div>
    );
  }

  if (error || !broker) {
    return (
      <div className="min-h-screen bg-[#0a0a0a]">
        <Header />
        <div className="max-w-3xl mx-auto px-6 py-24 text-center text-white/20">
          <p className="text-5xl mb-4">404</p>
          <p className="text-white/40">Broker not found</p>
          <Link href="/" className="text-[#E8B84B] text-sm mt-4 inline-block hover:underline">
            ← Back to rankings
          </Link>
        </div>
      </div>
    );
  }

  const googleData = (broker.google_business_data as Record<string, string> | null) || {};
  const activeLinks = PORTAL_LINKS.filter((l) => {
    const val = broker[l.key];
    if (!val) return false;
    const s = String(val);
    return s.startsWith("http://") || s.startsWith("https://");
  });

  return (
    <div className="min-h-screen bg-[#0a0a0a]">
      <Header />

      <main className="max-w-3xl mx-auto px-6 py-10 space-y-5">

        <Link href="/" className="text-sm text-[#E8B84B]/70 hover:text-[#E8B84B] transition-colors">
          ← Back to rankings
        </Link>

        {/* Hero card */}
        <div className="bg-[#111111] border border-white/8 rounded-2xl p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs text-[#E8B84B] font-semibold tracking-widest uppercase mb-2">
                Broker Profile
              </p>
              <h1 className="text-2xl font-bold text-white">{broker.name}</h1>
              <p className="text-white/40 mt-1">{broker.area}, Bangalore</p>
              {broker.phone && (
                <p className="text-sm text-white/30 mt-1">{broker.phone}</p>
              )}
              {broker.last_scraped_at && (
                <p className="text-xs text-white/15 mt-3">
                  Last scraped: {new Date(broker.last_scraped_at).toLocaleDateString()}
                </p>
              )}
            </div>
            <div className="text-center shrink-0">
              <ScoreBadge score={broker.total_score} size="lg" />
              <p className="text-xs text-white/20 mt-2">out of 100</p>
            </div>
          </div>

          {(googleData.rating || googleData.review_count) && (
            <div className="mt-5 flex gap-6 pt-5 border-t border-white/5">
              {googleData.rating && (
                <div>
                  <p className="text-lg font-bold text-white">⭐ {googleData.rating}</p>
                  <p className="text-xs text-white/30 mt-0.5">Google Rating</p>
                </div>
              )}
              {googleData.review_count && (
                <div>
                  <p className="text-lg font-bold text-white">{googleData.review_count}</p>
                  <p className="text-xs text-white/30 mt-0.5">Reviews</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Score breakdown */}
        <div className="bg-[#111111] border border-white/8 rounded-2xl p-6">
          <h2 className="font-semibold text-white mb-5">Score Breakdown</h2>
          <div className="space-y-4">
            {SCORE_DIMS.map(({ key, label, max }) => (
              <ScoreBar key={key} label={label} score={broker[key]} max={max} />
            ))}
            <div className="pt-4 border-t border-white/5">
              <ScoreBar label="Total" score={broker.total_score} max={100} />
            </div>
          </div>
        </div>

        {/* AI Insights */}
        <div className="bg-[#111111] border border-white/8 rounded-2xl p-6">
          <h2 className="font-semibold text-white mb-5">AI Insights</h2>
          <InsightsPanel
            strengths={broker.strengths}
            weaknesses={broker.weaknesses}
            missed_opportunities={broker.missed_opportunities}
            sales_pitch={broker.sales_pitch}
          />
        </div>

        {/* Profile links */}
        {activeLinks.length > 0 && (
          <div className="bg-[#111111] border border-white/8 rounded-2xl p-6">
            <h2 className="font-semibold text-white mb-4">Profile Links</h2>
            <div className="flex flex-wrap gap-2">
              {activeLinks.map(({ key, label }) => (
                <a
                  key={key}
                  href={String(broker[key])}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm bg-white/5 hover:bg-[#E8B84B]/10 border border-white/10 hover:border-[#E8B84B]/40 text-white/50 hover:text-[#E8B84B] px-4 py-2 rounded-xl transition-all"
                >
                  {label} ↗
                </a>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
