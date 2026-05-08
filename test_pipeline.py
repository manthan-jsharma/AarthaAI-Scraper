"""
test_pipeline.py — Full pipeline simulation (1 broker per source, no DB writes)

Run: python test_pipeline.py

Flow per broker:
  PHASE 1  Discovery      — 1 broker from MagicBricks, JustDial, Google Maps
  PHASE 2  Portal scrape  — MagicBricks: scrape agent profile (name + agency + listings)
                          — JustDial:    skip (directory already gave phone + rating)
                          — Google Maps: fetch business details (phone + website)
  PHASE 3  DDG search     — MagicBricks: "{agency}" "{name}" → linkedin, housing, nobroker, website
                          — JustDial:    "{agency}"           → same targets + google_maps
                          — Google Maps: "{name}"             → same targets
  PHASE 4  Website scrape — if URL found from maps or DDG
  PHASE 5  LinkedIn scrape— if URL found AND presence score >= 2
  PHASE 6  Scoring        — all sub-scores + total (printed, not saved to DB)
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()


# ── Pipeline imports ──────────────────────────────────────────────────────────

from agents.sources import magicbricks, justdial, google_maps
from agents.sources.portal_url_finder import find_missing_urls
from agents.scrapfly_scraper import scrapfly_scrape
from agents.smart_scraper import smart_scrape
from agents.schemas import PortalProfile, WebsiteData, LinkedInProfile
from scoring.engine import (
    score_website, score_social_media, score_linkedin,
    score_google_business, score_property_portals,
    score_listings, score_video,
)


# ── Prompts (mirrors scraping_agent.py) ──────────────────────────────────────

PORTAL_PROMPT = """
Extract the following from this real estate agent profile page and return as JSON:
- name: agent/broker full name
- agency: agency or company name if shown (or null)
- area: area or locality they serve
- listings_count: number of active listings shown (or 0)
- rating: rating score if shown e.g. 4.5 (or null)
- review_count: number of reviews (or 0)
- years_experience: years of experience if mentioned (or null)
- phone: phone number if visible (or null)
- profile_complete: boolean — does profile have photo, bio, and listings?
"""

WEBSITE_PROMPT = """
Extract the following from this real estate broker website and return as JSON:
- has_website: true
- has_contact_page: boolean — is there a contact page or section?
- has_listings_page: boolean — are property listings shown?
- has_blog: boolean — is there a blog or news section?
- seo_title: the page title
- meta_description: meta description if present
- phone: any phone number found (or null)
- email: any email found (or null)
- social_links: list of any social media URLs found
"""

LINKEDIN_PROMPT = """
Extract the following from this LinkedIn profile page and return as JSON:
- followers: follower or connection count (or null)
- posts_last_30_days: estimated number of posts in the last 30 days (or null)
- avg_likes: average likes on recent posts (or null)
- avg_comments: average comments on recent posts (or null)
- has_property_content: boolean — do posts mention real estate, properties, or listings?
- bio: short professional headline or summary (or null)
- website: website URL shown on the profile (or null)
"""


# ── Print helpers ─────────────────────────────────────────────────────────────

def _banner(text: str):
    bar = "█" * 60
    print(f"\n{bar}\n  {text}\n{bar}")

def _section(text: str):
    print(f"\n{'─'*60}\n  {text}\n{'─'*60}")

def _step(n: int, text: str):
    print(f"\n[STEP {n}] {text}")

def _pp(label: str, data):
    print(f"  {label}")
    print("  " + json.dumps(data, indent=2, ensure_ascii=False, default=str).replace("\n", "\n  "))

def _ok(msg: str):  print(f"  ✓ {msg}")
def _skip(msg: str): print(f"  — {msg}")


# ── Presence score (mirrors scraping_agent.py) ────────────────────────────────

def _presence_score(broker: dict) -> int:
    url_fields = [
        "google_maps_url", "website_url", "magicbricks_url",
        "acres99_url", "housing_url", "nobroker_url", "justdial_url",
    ]
    return sum(1 for f in url_fields if broker.get(f))


# ── Per-broker pipeline ───────────────────────────────────────────────────────

async def run_broker(broker: dict, source: str) -> dict:
    _section(f"BROKER: {broker['name']}  [{source}]")
    _pp("Discovery data:", broker)

    individual_name: str | None = None
    agency_name: str | None = None

    # ── STEP 2: Portal profile scrape ────────────────────────────────────────
    _step(2, "Portal profile scrape")

    if source == "magicbricks" and broker.get("magicbricks_url"):
        url = broker["magicbricks_url"]
        print(f"  Scraping: {url[:80]}")
        raw = await scrapfly_scrape(url, PORTAL_PROMPT, response_schema=PortalProfile)
        portal_data = raw if isinstance(raw, dict) else {}
        broker["portal_data"] = {"magicbricks": portal_data}
        individual_name = portal_data.get("name")
        agency_name     = portal_data.get("agency")
        _pp("Portal result:", portal_data)
        _ok(f"individual_name={individual_name!r}  agency={agency_name!r}")
        # Promote phone from portal profile if not yet known
        if portal_data.get("phone") and not broker.get("phone"):
            broker["phone"] = portal_data["phone"]
            _ok(f"Phone promoted from portal: {portal_data['phone']}")

    elif source == "justdial":
        _skip("JustDial — directory already returned phone + rating, no profile scrape needed")
        # JustDial: only agency name known, no individual name
        # DDG will search: "{agency} real estate bangalore linkedin" etc.
        agency_name = broker.get("name")
        individual_name = None

    elif source == "google_maps":
        _skip("Google Maps profile scrape — fetching business details instead (Step 2b)")
        # Google Maps: business name used as agency for DDG search
        # DDG will search: "{name} real estate bangalore linkedin" etc.
        agency_name = broker.get("name")
        individual_name = None

    # ── STEP 2b: Google Maps business details ────────────────────────────────
    if broker.get("google_maps_url"):
        _step("2b", "Google Maps business details")
        maps = await google_maps.get_business_details(broker["google_maps_url"])
        if maps:
            broker["google_business_data"] = maps
            if maps.get("phone") and not broker.get("phone"):
                broker["phone"] = maps["phone"]
            if maps.get("website") and not broker.get("website_url"):
                broker["website_url"] = maps["website"]
                _ok(f"Website from Maps: {maps['website']}")
            _pp("Maps details:", maps)
        else:
            _skip("No data from Google Maps details")

    # ── STEP 3: DDG search for missing URLs ──────────────────────────────────
    _step(3, "DDG search for missing URLs")
    print(f"  individual_name={individual_name!r}  agency={agency_name!r}")

    new_urls = await find_missing_urls(broker, individual_name, agency_name)
    if new_urls:
        broker.update(new_urls)
        _pp("DDG found:", new_urls)
    else:
        _skip("DDG: no new URLs found")

    # ── STEP 4: Website scrape ───────────────────────────────────────────────
    _step(4, "Website scrape")

    if broker.get("website_url"):
        print(f"  Scraping: {broker['website_url'][:80]}")
        raw = await smart_scrape(broker["website_url"], WEBSITE_PROMPT, WebsiteData)
        website_data = raw if isinstance(raw, dict) else {}
        broker["website_data"] = website_data
        _pp("Website result:", website_data)

        # Promote social links found on website
        for url in (website_data.get("social_links") or []):
            if not isinstance(url, str):
                continue
            if "instagram.com" in url.lower() and not broker.get("instagram_url"):
                broker["instagram_url"] = url
                _ok(f"Instagram promoted from website: {url}")
            elif "linkedin.com" in url.lower() and not broker.get("linkedin_url"):
                broker["linkedin_url"] = url
                _ok(f"LinkedIn promoted from website: {url}")
    else:
        _skip("No website URL — skip")

    # ── STEP 5: LinkedIn scrape ──────────────────────────────────────────────
    _step(5, "LinkedIn scrape")

    if not broker.get("linkedin_url"):
        _skip("No LinkedIn URL found")
    elif _presence_score(broker) < 2:
        _skip(f"Presence score {_presence_score(broker)} < 2 — not worth scraping LinkedIn")
    else:
        print(f"  Scraping: {broker['linkedin_url'][:80]}")
        raw = await scrapfly_scrape(
            broker["linkedin_url"],
            LINKEDIN_PROMPT,
            response_schema=LinkedInProfile,
            country="US",
            headers={"Accept-Language": "en-US,en;q=0.5"},
        )
        linkedin_data = raw if isinstance(raw, dict) else {}
        broker["linkedin_data"] = linkedin_data

        if not linkedin_data:
            print("  WARNING: LinkedIn scrape returned empty — likely blocked by Scrapfly")
        elif all(v is None for v in linkedin_data.values()):
            print("  WARNING: LinkedIn scraped but all fields null — wrong profile or blocked page")
        else:
            _pp("LinkedIn result:", linkedin_data)

        # Promote website URL from LinkedIn if not yet known
        if linkedin_data.get("website") and not broker.get("website_url"):
            broker["website_url"] = linkedin_data["website"]
            _ok(f"Website promoted from LinkedIn: {linkedin_data['website']}")

    # ── STEP 6: Scoring ──────────────────────────────────────────────────────
    _step(6, "Scoring")

    website_data   = broker.get("website_data") or {}
    if broker.get("website_url") and not website_data.get("has_website"):
        website_data = {**website_data, "has_website": True}

    linkedin_data  = broker.get("linkedin_data") or {}
    google_data    = broker.get("google_business_data") or {}
    portal_data    = broker.get("portal_data") or {}
    instagram_data = broker.get("instagram_data") or {}
    combined_social = {**instagram_data}

    scores = {
        "score_website":          score_website(website_data),
        "score_social_media":     score_social_media(combined_social),
        "score_linkedin":         score_linkedin(linkedin_data),
        "score_google_business":  score_google_business(google_data),
        "score_property_portals": score_property_portals(portal_data, broker),
        "score_listings":         score_listings(portal_data),
        "score_video":            score_video(website_data, combined_social),
    }
    scores["total_score"] = sum(v for k, v in scores.items() if k != "total_score")

    _pp("Scores:", scores)
    broker["scores"] = scores
    return broker


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    _banner("REAL ESTATE BROKER PIPELINE — FULL SIMULATION")
    print("  1 broker per source  ×  3 sources  |  No DB writes")

    # ── PHASE 1: Discovery ───────────────────────────────────────────────────
    _banner("PHASE 1 — DISCOVERY")

    _section("MagicBricks directory")
    mb_brokers = await magicbricks.discover_brokers(max_results=1)
    _pp(f"{len(mb_brokers)} broker(s):", mb_brokers)

    _section("JustDial directory")
    jd_brokers = await justdial.discover_brokers(max_results=1)
    _pp(f"{len(jd_brokers)} broker(s):", jd_brokers)

    _section("Google Maps discovery")
    gm_brokers = await google_maps.discover_brokers(max_results=1)
    _pp(f"{len(gm_brokers)} broker(s):", gm_brokers)

    # ── PHASE 2: Enrichment + Scoring ────────────────────────────────────────
    _banner("PHASE 2 — ENRICHMENT + SCORING")

    results = []
    for source, brokers in [
        ("magicbricks", mb_brokers),
        ("justdial",    jd_brokers),
        ("google_maps", gm_brokers),
    ]:
        if not brokers:
            print(f"\n[{source.upper()}] Discovery returned 0 brokers — skipping")
            continue
        result = await run_broker(brokers[0].copy(), source)
        results.append((source, result))
        await asyncio.sleep(2)

    # ── Final summary ─────────────────────────────────────────────────────────
    _banner("PIPELINE COMPLETE — FINAL SUMMARY")

    for source, b in results:
        scores = b.get("scores", {})
        portals = [p for p in ["magicbricks_url", "justdial_url", "housing_url",
                                "nobroker_url", "acres99_url"] if b.get(p)]
        print(f"\n{b['name']}  [{source}]")
        print(f"  Phone    : {b.get('phone', '—')}")
        print(f"  Website  : {b.get('website_url', '—')}")
        print(f"  LinkedIn : {b.get('linkedin_url', '—')}")
        print(f"  Portals  : {[p.replace('_url','') for p in portals] or '—'}")
        print(f"  Scores   : {scores}")


if __name__ == "__main__":
    asyncio.run(main())
