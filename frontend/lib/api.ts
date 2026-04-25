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
