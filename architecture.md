Project Title:
AI Tool for Real Estate Broker Digital Ranking (Bangalore)
Objective:
Build an automated AI-powered system that identifies, analyzes, and ranks real estate brokers in Bangalore based on their digital presence.

Scope of Work:

1. Lead Discovery Agent
   Automatically collect broker profiles from:
   Google search results
   MagicBricks, 99acres, Housing, NoBroker
   LinkedIn and Instagram
   Extract:
   Name
   Area
   Contact (if available)
   Profile links
2. Web Scraping Agent
   Extract data from:
   Personal websites
   Social media profiles
   Google Business listings
   Property portals
   Data points:
   Website structure (SEO, pages, speed indicators)
   Social metrics (followers, posts, engagement)
   Listings count and quality
   Reviews and ratings
3. Scoring Engine
   Implement a scoring system:
   Website: /30
   Social Media: /20
   LinkedIn: /10
   Google Business: /15
   Property Portals: /15
   Listings Platforms: /5
   Video Presence: /5
   Total Score: /100

4. AI Insights Engine
   Use an LLM (preferably free/open-source or Groq) to generate:
   Strengths
   Weaknesses
   Missed opportunities
   Sales pitch angle

5. Database & Storage
   Store all broker data in a structured format (Supabase/PostgreSQL)
   Ensure deduplication and updates

6. Output & Dashboard
   Web dashboard / For now Google Sheets
   Must include:
   Rankings
   Filters (area, score)
7. Automation
   System should run periodically (daily/weekly)
   Auto-update rankings

Tech Stack Preference:
Backend: Python (FastAPI)
Scraping: Playwright / Firecrawl
AI: Groq (LLaMA models)
Frontend (optional): Next.js
DB: Supabase

Timeline:
Beta Version: 5–7 days
Full system: 10–14 days

Success Criteria:
Minimum 50 brokers auto-collected
Accurate scoring system
Clean structured output
Actionable insights generated

Final Deliverable:
Working AI agent + database + output dashboard
