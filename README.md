# Real Estate Broker Ranker

AI-powered digital presence ranking for Bangalore real estate brokers. Automatically discovers brokers, scrapes their online presence, scores them across 7 dimensions, and surfaces AI-generated insights — all on a live dashboard.

---

## What it does

- **Discovers** brokers from Google Maps and the web (DDG search)
- **Scrapes** their website, Google Business profile, and property portal listings
- **Scores** each broker out of 100 across website, social media, Google Business, portals, listings, LinkedIn, and video
- **Generates** AI insights (strengths, weaknesses, missed opportunities, sales pitch) using Gemini
- **Displays** everything on a filterable Next.js dashboard

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + Uvicorn |
| Scraping | Playwright + BeautifulSoup + Gemini 2.5 Flash |
| AI extraction | Google Gemini 2.5 Flash (direct API) |
| AI insights | Google Gemini 2.5 Flash |
| Database | Supabase (PostgreSQL) |
| Scheduling | APScheduler (daily at 2AM) |
| Frontend | Next.js 14 + Tailwind CSS |
| Export | Google Sheets via gspread |

---

## Scoring breakdown

| Category | Max points | Data source |
|---|---|---|
| Website presence | 30 | Broker's own website |
| Social media | 20 | Instagram / Facebook activity |
| Google Business | 15 | Google Maps profile |
| Property portals | 15 | MagicBricks, 99acres, Housing, NoBroker, JustDial |
| Listings | 5 | Active listing count across portals |
| LinkedIn | 10 | LinkedIn profile activity |
| Video presence | 5 | YouTube / video content links |
| **Total** | **100** | |

---

## Project structure

```
├── agents/
│   ├── discovery_agent.py      # Orchestrates all discovery sources
│   ├── scraping_agent.py       # Per-broker deep scrape
│   ├── smart_scraper.py        # Playwright + BeautifulSoup + Gemini
│   └── sources/
│       ├── google_maps.py      # Google Maps discovery + detail scrape
│       ├── google_search.py    # DDG search + website scraping
│       ├── magicbricks.py      # Stubbed — needs residential proxies
│       ├── acres99.py          # Stubbed — needs residential proxies
│       ├── housing.py          # Stubbed — needs residential proxies
│       ├── nobroker.py         # Stubbed — needs residential proxies
│       └── justdial.py         # Stubbed — needs residential proxies
├── scoring/
│   └── engine.py               # Scoring logic for all 7 dimensions
├── insights/
│   └── groq_engine.py          # AI insight generation via Gemini
├── database/
│   └── client.py               # Supabase client with merge upsert
├── scheduler/
│   └── jobs.py                 # APScheduler daily pipeline job
├── output/
│   └── sheets.py               # Google Sheets export
├── frontend/                   # Next.js dashboard
│   ├── app/
│   │   ├── page.tsx            # Rankings dashboard
│   │   └── broker/[id]/page.tsx # Broker detail page
│   └── components/
│       ├── BrokerCard.tsx
│       ├── ScoreBar.tsx
│       ├── ScoreBadge.tsx
│       └── InsightsPanel.tsx
├── main.py                     # FastAPI app + pipeline endpoints
└── config.py                   # Settings via .env
```

---

## Setup

### 1. Clone and install Python dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Install frontend dependencies

```bash
cd frontend && npm install
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in:

```env
GOOGLE_API_KEY=your_gemini_api_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
GROQ_API_KEY=not_used_kept_for_compat
GOOGLE_SHEET_ID=optional_sheet_id
```

Get a free Gemini API key at [ai.google.dev](https://ai.google.dev).

### 4. Create the Supabase table

Run this in your Supabase SQL editor:

```sql
create table brokers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  area text,
  city text,
  phone text,
  source text,
  website_url text,
  google_maps_url text,
  magicbricks_url text,
  acres99_url text,
  housing_url text,
  nobroker_url text,
  justdial_url text,
  linkedin_url text,
  instagram_url text,
  website_data jsonb,
  google_business_data jsonb,
  portal_data jsonb,
  social_data jsonb,
  linkedin_data jsonb,
  instagram_data jsonb,
  score_website int default 0,
  score_social_media int default 0,
  score_google_business int default 0,
  score_property_portals int default 0,
  score_listings int default 0,
  score_linkedin int default 0,
  score_video int default 0,
  total_score int default 0,
  strengths text,
  weaknesses text,
  missed_opportunities text,
  sales_pitch text,
  last_scraped_at timestamptz,
  created_at timestamptz default now()
);
```

### 5. Run the backend

```bash
uvicorn main:app --reload --port 8000
```

### 6. Run the frontend

```bash
cd frontend && npm run dev
```

Dashboard at [http://localhost:3000](http://localhost:3000)

---

## Running the pipeline

### Via the dashboard

Click **Run Pipeline** in the UI header.

### Via API

```bash
# Full pipeline (discovery + scraping + insights)
curl -X POST http://localhost:8000/run/full-pipeline

# Discovery only
curl -X POST http://localhost:8000/run/discover

# Re-score all existing brokers (after scoring logic changes)
curl -X POST http://localhost:8000/run/rescore

# Export to Google Sheets
curl -X POST http://localhost:8000/run/export-sheets
```

The pipeline runs automatically every day at 2AM via APScheduler.

---

## Portal scraping (coming soon)

MagicBricks, 99acres, Housing, NoBroker, and JustDial are currently stubbed — they block datacenter IPs at the network level. Integrating [ZenRows](https://www.zenrows.com) or [Scrapfly](https://scrapfly.io) (both have free tiers) will unlock portal scraping and fill the `score_property_portals` and `score_listings` dimensions.

---

## Notes

- Gemini 2.5 Flash free tier: ~500 req/day. One full pipeline run uses ~50–80 requests.
- LinkedIn and Instagram scraping is stubbed — requires residential proxies (BrightData/Oxylabs).
- The daily cap is set to 30 brokers total (`max_brokers_per_source = 15` in `config.py`).
