"""
test_website_scrape.py — Test website scraping in isolation.

Usage:
    python test_website_scrape.py https://brokerinblue.com/

Shows every layer the pipeline sees:
  1. Raw HTML size + how many social links Playwright grabbed from live DOM
  2. Cleaned text sent to Gemini (first 3000 chars)
  3. Social links section appended to cleaned text
  4. Final Gemini extraction result (WebsiteData) — exactly what pipeline uses
  5. What score_website() and score_social_media() would produce from this data
"""
import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

from agents.smart_scraper import fetch_html, clean_html, ask_gemini
from agents.schemas import WebsiteData
from scoring.engine import score_website, score_social_media

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
- social_links: list of any social media URLs found on the page
"""

_SOCIAL_DOMAINS = ["instagram.com", "linkedin.com", "facebook.com", "youtube.com", "twitter.com", "x.com"]


def _sep(title: str = ""):
    bar = "─" * 60
    print(f"\n{bar}  {title}\n{bar}" if title else f"\n{bar}")


async def run(url: str):
    print(f"\n{'█'*60}")
    print(f"  WEBSITE SCRAPE TEST")
    print(f"  URL: {url}")
    print(f"{'█'*60}")

    # ── STEP 1: Fetch HTML via Playwright ────────────────────────────────────
    _sep("STEP 1 — Playwright fetch")
    print(f"  Fetching page…")
    html = await fetch_html(url)

    if not html:
        print("  ERROR: fetch_html returned empty — page may be unreachable")
        return

    print(f"  Raw HTML size   : {len(html):,} chars")

    # Count how many social links Playwright injected via live DOM
    injected_marker = '__social_links__'
    if injected_marker in html:
        import re
        injected_block = re.search(r'<div id="__social_links__">(.*?)</div>', html, re.DOTALL)
        if injected_block:
            live_links = re.findall(r'href="([^"]+)"', injected_block.group(1))
            print(f"  Playwright live DOM social links ({len(live_links)}):")
            for lnk in live_links:
                print(f"    {lnk}")
        else:
            print("  Playwright live DOM social links: 0")
    else:
        print("  Playwright live DOM social links: 0 (none injected)")

    # ── STEP 2: Clean HTML ───────────────────────────────────────────────────
    _sep("STEP 2 — Cleaned text sent to Gemini")
    cleaned = clean_html(html)
    print(f"  Cleaned text size: {len(cleaned):,} chars")

    # Show the "Links found on page:" section appended by clean_html
    if "Links found on page:" in cleaned:
        links_section = cleaned[cleaned.index("Links found on page:"):]
        print(f"\n  [Social/contact links section that Gemini sees]")
        print("  " + links_section.replace("\n", "\n  "))
    else:
        print("\n  WARNING: No 'Links found on page:' section in cleaned text")
        print("  Gemini will NOT see any social URLs — scraping will miss them")

    print(f"\n  [First 2000 chars of cleaned text]")
    print("  " + cleaned[:2000].replace("\n", "\n  "))

    # ── STEP 3: Gemini extraction ────────────────────────────────────────────
    _sep("STEP 3 — Gemini extraction (WebsiteData)")
    print("  Calling Gemini…")
    result = ask_gemini(cleaned, WEBSITE_PROMPT, WebsiteData)

    print(f"\n  Raw Gemini result:")
    print("  " + json.dumps(result, indent=2, ensure_ascii=False, default=str).replace("\n", "\n  "))

    # ── STEP 4: Scoring ──────────────────────────────────────────────────────
    _sep("STEP 4 — Scores from this data (same as pipeline)")

    website_data = result if isinstance(result, dict) else {}

    # Mirror the pipeline: if URL was given, has_website = True
    if url and not website_data.get("has_website"):
        website_data = {**website_data, "has_website": True}

    # Build a minimal broker dict to test score_social_media presence points
    social_links = website_data.get("social_links") or []
    instagram_url = next((u for u in social_links if "instagram.com" in u.lower()), None)
    linkedin_url  = next((u for u in social_links if "linkedin.com" in u.lower()), None)

    mock_broker = {
        "website_url":   url,
        "website_data":  website_data,
        "instagram_url": instagram_url,
        "linkedin_url":  linkedin_url,
    }

    s_website = score_website(website_data)
    s_social  = score_social_media({}, mock_broker)

    print(f"  score_website        : {s_website} / 30")
    print(f"  score_social_media   : {s_social} / 20")
    print(f"    instagram_url found: {instagram_url or '—'}")
    print(f"    social_links found : {social_links or '—'}")

    _sep("DONE")
    print(f"  WebsiteData that pipeline stores in broker['website_data']:")
    print("  " + json.dumps(website_data, indent=2, ensure_ascii=False, default=str).replace("\n", "\n  "))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_website_scrape.py <url>")
        print("Example: python test_website_scrape.py https://brokerinblue.com/")
        sys.exit(1)

    target_url = sys.argv[1]
    asyncio.run(run(target_url))
