"""
Scrapfly portal test — run with: python test_scrapfly.py
Fill in your SCRAPFLY_KEY in .env or export it before running.
Replace each TEST_URLS entry with a real broker/agent profile URL.
"""
import asyncio
import os
from dotenv import load_dotenv
from scrapfly import ScrapflyClient, ScrapeConfig

load_dotenv()

SCRAPFLY_KEY = os.getenv("SCRAPFLY_KEY", "")
if not SCRAPFLY_KEY:
    raise SystemExit("Set SCRAPFLY_KEY in your .env file first")

# --- Fill in real agent/broker profile URLs below ---
TEST_URLS = {
    "linkedin":     "https://www.linkedin.com/in/manthan-sharma-12b0332a7",
    # "magicbricks":  "https://www.magicbricks.com/top-agent-details/company-jaipur-real-estate-in-jaipur-agentid-4d42393535393030",
    # "99acres":      "https://www.99acres.com/agent-profile/AGENT_ID",
    # "housing":      "https://housing.com/agents/AGENT_ID",
    # "nobroker":     "https://www.nobroker.in/property-for-rent/AREA",
    # "justdial":     "https://www.justdial.com/Bangalore/BROKER-NAME",
}

# Config per portal — tune after seeing results 
PORTAL_CONFIGS = {
     "linkedin": dict(asp=True, render_js=True, country="US",                               
                   headers={"Accept-Language": "en-US,en;q=0.5"}, format="markdown"),
    # "magicbricks": dict(asp=True,  render_js=True,  country="IN", format="markdown"),
    # "99acres":     dict(asp=True,  render_js=True,  country="IN", format="markdown"),
    # "housing":     dict(asp=True,  render_js=True,  country="IN", format="markdown"),
    # "nobroker":    dict(asp=True,  render_js=True,  country="IN", format="markdown"),
    # "justdial":    dict(asp=False, render_js=False, country="IN", format="markdown"),
}

PREVIEW_CHARS = 18000  # how much of the response to print


async def test_portal(client: ScrapflyClient, name: str, url: str):
    if "YOUR_" in url or url.endswith("/AGENT_ID") or url.endswith("/AREA") or url.endswith("/BROKER-NAME"):
        print(f"\n{'='*60}")
        print(f"[{name.upper()}] SKIPPED — fill in a real URL first")
        return

    print(f"\n{'='*60}")
    print(f"[{name.upper()}] Testing: {url}")
    cfg = PORTAL_CONFIGS[name]
    print(f"Config: {cfg}")

    try:
        result = await client.async_scrape(ScrapeConfig(url=url, **cfg))

        status = result.upstream_status_code
        content = result.content or ""
        cost = result.context.get("cost", "?")

        print(f"Status: {status} | Credits used: {cost}")

        blocked_signals = ["access denied", "captcha", "blocked", "403", "robot", "please enable javascript to view"]
        is_blocked = any(s in content.lower()[:500] for s in blocked_signals)

        if is_blocked:
            print("RESULT: BLOCKED — portal is blocking Scrapfly")
            print(f"First 500 chars:\n{content[:500]}")
        elif len(content) < 200:
            print(f"RESULT: TOO SHORT ({len(content)} chars) — likely blocked or empty")
            print(content)
        else:
            print(f"RESULT: SUCCESS — got {len(content)} chars")
            print(f"\n--- First {PREVIEW_CHARS} chars ---\n{content[:PREVIEW_CHARS]}")

    except Exception as e:
        print(f"RESULT: ERROR — {e}")


async def main():
    client = ScrapflyClient(key=SCRAPFLY_KEY)
    # Run portals one at a time so we don't burn credits if early ones fail
    for name, url in TEST_URLS.items():
        await test_portal(client, name, url)
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
