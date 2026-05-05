const API_URL = typeof window === "undefined"
  ? (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
  : "/api";

export interface Broker {
  id: string;
  name: string;
  area: string;
  city: string;
  phone: string | null;
  website_url: string | null;
  magicbricks_url: string | null;
  acres99_url: string | null;
  housing_url: string | null;
  nobroker_url: string | null;
  justdial_url: string | null;
  google_maps_url: string | null;
  linkedin_url: string | null;
  instagram_url: string | null;
  score_website: number;
  score_social_media: number;
  score_linkedin: number;
  score_google_business: number;
  score_property_portals: number;
  score_listings: number;
  score_video: number;
  total_score: number;
  strengths: string | null;
  weaknesses: string | null;
  missed_opportunities: string | null;
  sales_pitch: string | null;
  google_business_data: Record<string, unknown> | null;
  portal_data: Record<string, unknown> | null;
  source: string;
  last_scraped_at: string | null;
  created_at: string;
}

export async function fetchBrokers(area?: string, limit = 100): Promise<Broker[]> {
  const params = new URLSearchParams();
  if (area) params.set("area", area);
  params.set("limit", String(limit));
  const res = await fetch(`${API_URL}/brokers?${params}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch brokers");
  return res.json();
}

export async function fetchBroker(id: string): Promise<Broker> {
  const res = await fetch(`${API_URL}/brokers/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Broker not found");
  return res.json();
}

export async function fetchAreas(): Promise<string[]> {
  const res = await fetch(`${API_URL}/areas`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function triggerPipeline(): Promise<void> {
  await fetch(`${API_URL}/run/full-pipeline`, { method: "POST" });
}

// --- Rankings / history types ---

export interface PipelineRun {
  id: string;
  run_number: number;
  started_at: string;
  completed_at: string | null;
  brokers_scraped: number;
  status: "running" | "completed" | "failed";
}

export interface RankedBroker {
  id: string;
  broker_id: string;
  pipeline_run_id: string;
  run_number: number;
  scored_at: string;
  total_score: number;
  score_website: number;
  score_social_media: number;
  score_google_business: number;
  score_property_portals: number;
  score_listings: number;
  score_linkedin: number;
  score_video: number;
  rank: number;
  brokers: { id: string; name: string; area: string; phone: string | null; google_maps_url: string | null };
}

export interface BrokerScoreHistoryEntry {
  run_number: number;
  scored_at: string;
  total_score: number;
  score_website: number;
  score_social_media: number;
  score_google_business: number;
  score_property_portals: number;
  score_listings: number;
  score_linkedin: number;
  score_video: number;
  pipeline_runs: { run_number: number; started_at: string; status: string };
}

export async function fetchPipelineRuns(): Promise<PipelineRun[]> {
  const res = await fetch(`${API_URL}/rankings/runs`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchRankingsForRun(runId: string): Promise<RankedBroker[]> {
  const res = await fetch(`${API_URL}/rankings/run/${runId}`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchBrokerScoreHistory(brokerId: string): Promise<BrokerScoreHistoryEntry[]> {
  const res = await fetch(`${API_URL}/rankings/broker/${brokerId}/history`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}
