"""
Scrapfly pipeline test — run with: python test_scrapfly.py

Tests every Scrapfly-backed step in the pipeline:
  PHASE 1 — Discovery (portal directory pages — do we get a list of brokers?)
  PHASE 2 — Profile scraping (individual broker pages — do we get rich data?)

Each test shows:
  - Raw Scrapfly result (status, credits, length)
  - JSON-LD Layer 1 hit/miss
  - Final Gemini-extracted JSON (what actually goes into the DB)

Credit cost guide:
  Directory page   (asp + render_js + IN)  ~30 credits
  Portal profile   (asp + render_js + IN)  ~30 credits
  LinkedIn profile (asp + render_js + US)  ~55 credits
"""
import asyncio
import json
import os
import sys

# Allow imports from project root
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from scrapfly import ScrapflyClient, ScrapeConfig

load_dotenv()

SCRAPFLY_KEY = os.getenv("SCRAPFLY_KEY", "")
if not SCRAPFLY_KEY:
    raise SystemExit("Set SCRAPFLY_KEY in your .env file first")

# ─────────────────────────────────────────────────────────────────────────────
# Prompts (mirrors what the pipeline uses)
# ─────────────────────────────────────────────────────────────────────────────

DIRECTORY_PROMPT = """
Extract all real estate agents or brokers listed on this page.
For each agent return:
- name: full name or business name (required)
- profile_url: the full URL to their individual agent profile page on this site (or null)
- area: area or locality in Bangalore they serve (or null)
- phone: phone number if visible (or null)
- rating: rating score if shown e.g. 4.5 (or null)
- listings_count: number of active listings shown (or 0)
Return every agent visible on the page, up to 15.
"""

PORTAL_PROFILE_PROMPT = """
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

LINKEDIN_PROMPT = """
Extract the following from this LinkedIn profile page and return as JSON:
- followers: follower or connection count (or null)
- posts_last_30_days: estimated number of posts in the last 30 days (or null)
- avg_likes: average likes on recent posts (or null)
- avg_comments: average comments on recent posts (or null)
- has_property_content: boolean — do posts mention real estate, properties, or listings?
- bio: short professional headline or summary (or null)
"""

# Map test name → prompt to use for Gemini extraction
PROMPTS = {
    "magicbricks_directory": DIRECTORY_PROMPT,
    "99acres_directory":     DIRECTORY_PROMPT,
    "housing_directory":     DIRECTORY_PROMPT,
    "magicbricks_profile":   PORTAL_PROFILE_PROMPT,
    "99acres_profile":       PORTAL_PROFILE_PROMPT,
    "housing_profile":       PORTAL_PROFILE_PROMPT,
    "nobroker_profile":      PORTAL_PROFILE_PROMPT,
    "justdial_profile":      PORTAL_PROFILE_PROMPT,
    "linkedin_profile":      LINKEDIN_PROMPT,
}

# Map test name → Pydantic schema for forced JSON output
def _get_schema(name: str):
    from agents.schemas import PortalAgentListings, PortalProfile, LinkedInProfile
    if "directory" in name:
        return PortalAgentListings
    if "linkedin" in name:
        return LinkedInProfile
    return PortalProfile


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — DISCOVERY  (portal agent directory pages)
# ─────────────────────────────────────────────────────────────────────────────

DISCOVERY_URLS = {
    # "magicbricks_directory": "https://www.magicbricks.com/Real-estate-property-top-agents/agent-in-Bangalore?cityName=Bangalore&postedSince=-1&isNRI=N&page=1&category=S&multiLang=en",
    "justdial_directory":    "https://www.justdial.com/Bengaluru/Real-Estate-Agents/nct-10192623",
    # Fill in real URLs once found by browsing the portal and copying from browser address bar:
    "99acres_directory":     "TODO — open 99acres.com, navigate to Bangalore agents list, paste URL here",
    "housing_directory":     "TODO — open housing.com, navigate to Bangalore agents list, paste URL here",
}

DISCOVERY_CONFIGS = {
    "magicbricks_directory": dict(asp=True, render_js=True, country="IN", rendering_wait=4000),
    "justdial_directory":    dict(asp=True, render_js=True, country="IN", rendering_wait=4000),
    "99acres_directory":     dict(asp=True, render_js=True, country="IN", rendering_wait=4000),
    "housing_directory":     dict(asp=True, render_js=True, country="IN", rendering_wait=4000),
}


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — PROFILE SCRAPING  (individual broker profile pages)
# ─────────────────────────────────────────────────────────────────────────────

PROFILE_URLS = {
    # Real MagicBricks profile — tests portal scrape + Gemini extraction (name, agency, listings, rating)
    # "magicbricks_profile": "https://www.magicbricks.com/top-agent-details/company-b-s-associates-in-bangalore-agentid-4d423236363037393431",
    # Fill these in once you have real broker URLs from discovery output:
    "justdial_profile":  "TODO — grab a _BZDET URL from justdial_directory discovery output",
    "99acres_profile":   "TODO — grab an agent-profile URL from 99acres_directory discovery output",
    "housing_profile":   "TODO — grab an /agents/ URL from housing_directory discovery output",
    "nobroker_profile":  "TODO — e.g. https://www.nobroker.in/agent/AGENT_SLUG",
    "linkedin_profile":  "TODO — e.g. https://www.linkedin.com/in/PROFILE_SLUG",
}

PROFILE_CONFIGS = {
    "magicbricks_profile": dict(asp=True, render_js=True, country="IN", rendering_wait=3000),
    "99acres_profile":     dict(asp=True, render_js=True, country="IN", rendering_wait=3000),
    "housing_profile":     dict(asp=True, render_js=True, country="IN", rendering_wait=3000),
    "nobroker_profile":    dict(asp=True, render_js=True, country="IN", rendering_wait=3000),
    "justdial_profile":    dict(asp=False, render_js=False, country="IN"),
    "linkedin_profile":    dict(asp=True, render_js=True, country="US", rendering_wait=3000,
                                headers={"Accept-Language": "en-US,en;q=0.5"}),
}


# ─────────────────────────────────────────────────────────────────────────────
# Extraction helpers
# ─────────────────────────────────────────────────────────────────────────────

def _check_blocked(content: str) -> bool:
    signals = ["access denied", "captcha", "blocked", "robot",
               "please enable javascript to view", "403 forbidden"]
    return any(s in content.lower()[:1000] for s in signals)


def _run_extraction(html: str, name: str) -> dict:
    """Run the full extraction and return result + debug info."""
    from agents.scrapfly_scraper import _extract_json_ld, _is_sufficient, _html_to_text, extract_profile_links
    from agents.smart_scraper import ask_gemini

    result = {"layer": None, "data": None}

    # Directory pages — extract profile links directly from HTML (no Gemini needed)
    if "directory" in name:
        from bs4 import BeautifulSoup

        # Debug: show all unique href patterns to find the right one
        soup = BeautifulSoup(html, "html.parser")
        all_hrefs = [a["href"] for a in soup.find_all("a", href=True)]
        unique_paths = sorted({
            h.split("?")[0] for h in all_hrefs
            if h.startswith("/") and len(h) > 5
        })
        print(f"\n--- All unique <a href> paths in page ({len(unique_paths)} total) ---")
        for p in unique_paths[:60]:
            print(f"  {p}")

        portal = name.split("_")[0]

        # JustDial: use full card parser (name + phone + rating + review_count)
        if portal == "justdial":
            from agents.sources.justdial import _parse_jd_cards
            cards = _parse_jd_cards(html, max_results=20)
            result["layer"] = f"JustDial card extraction ({len(cards)} brokers)"
            result["data"] = cards
            return result

        patterns = {
            "magicbricks": ("/top-agent-details/",  "https://www.magicbricks.com"),
            "99acres":     ("/agent-profile/",       "https://www.99acres.com"),
            "housing":     ("/agents/",              "https://housing.com"),
        }
        pattern, base = patterns.get(portal, ("/agents/", ""))
        links = extract_profile_links(html, pattern, base)

        result["layer"] = f"HTML link extraction ({len(links)} links found)"
        result["data"] = links
        return result

    # Profile pages — Layer 1: JSON-LD
    json_ld = _extract_json_ld(html)
    if json_ld and _is_sufficient(json_ld):
        result["layer"] = "JSON-LD (0 Gemini tokens)"
        result["data"] = json_ld
        return result

    # Layer 2 — text → Gemini
    text = _html_to_text(html)
    if not text:
        result["layer"] = "EMPTY — no text extracted"
        return result

    prompt = PROMPTS.get(name, PORTAL_PROFILE_PROMPT)
    schema = _get_schema(name)
    result["layer"] = f"Gemini ({len(text)} chars → ~{len(text)//4} tokens)"
    result["data"] = ask_gemini(text, prompt, schema)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Test runner
# ─────────────────────────────────────────────────────────────────────────────

async def run_test(client: ScrapflyClient, phase: str, name: str, url: str, config: dict):
    skip_markers = ["AGENT_SLUG", "AGENT_ID", "YOUR_PROFILE", "BROKER-NAME", "LISTING_ID", "TODO"]
    if any(m in url for m in skip_markers):
        print(f"\n{'─'*60}")
        print(f"[{phase} / {name.upper()}] SKIPPED — fill in a real URL first")
        return

    print(f"\n{'='*60}")
    print(f"[{phase} / {name.upper()}]")
    print(f"URL    : {url}")

    try:
        result = await client.async_scrape(ScrapeConfig(url=url, **config))

        status  = result.upstream_status_code
        content = result.content or ""
        cost    = result.context.get("cost", "?")

        print(f"Status : {status} | Credits: {cost} | Length: {len(content)} chars")

        if _check_blocked(content):
            print("RESULT : BLOCKED")
            print(f"First 500 chars:\n{content[:500]}")
            return

        if len(content) < 500:
            print(f"RESULT : TOO SHORT — likely blocked or empty")
            print(content)
            return

        print(f"RESULT : SUCCESS — running extraction...")

        # Run two-layer extraction
        extraction = _run_extraction(content, name)

        print(f"\n--- Extraction ---")
        print(f"Layer  : {extraction['layer']}")
        print(f"Output :")
        print(json.dumps(extraction["data"], indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"RESULT : ERROR — {e}")


async def main():
    client = ScrapflyClient(key=SCRAPFLY_KEY)

    print("\n" + "█"*60)
    print("  PHASE 1 — DISCOVERY (portal directory pages)")
    print("█"*60)
    for name, url in DISCOVERY_URLS.items():
        cfg = DISCOVERY_CONFIGS[name]
        await run_test(client, "DISCOVERY", name, url, cfg)
        await asyncio.sleep(2)

    print("\n" + "█"*60)
    print("  PHASE 2 — PROFILE SCRAPING (individual broker pages)")
    print("█"*60)
    for name, url in PROFILE_URLS.items():
        cfg = PROFILE_CONFIGS.get(name, dict(asp=True, render_js=True, country="IN"))
        await run_test(client, "PROFILE", name, url, cfg)
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
