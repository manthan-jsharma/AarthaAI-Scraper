"""
Scrapfly-backed scraper for bot-protected portals (MagicBricks, 99acres etc.)
and LinkedIn.

Two-layer extraction strategy:
  Layer 1 — JSON-LD: extract schema.org structured data from raw HTML.
             If the page has it and it's sufficient → return it directly.
             Zero Gemini tokens consumed.
  Layer 2 — Gemini fallback: clean the raw HTML to plain text (nav/footer
             stripped), trim to 8k chars, send to Gemini for extraction.
             Only runs when JSON-LD is missing or incomplete.

Falls back to local smart_scrape if SCRAPFLY_KEY is not configured.
"""
import asyncio
import json
from bs4 import BeautifulSoup
from loguru import logger

from config import settings
from agents.smart_scraper import ask_gemini, smart_scrape


# ---------------------------------------------------------------------------
# JSON-LD extraction helpers
# ---------------------------------------------------------------------------

_USEFUL_SCHEMA_TYPES = {
    "realestateagent", "person", "localbusiness",
    "organization", "professionalbusiness", "realestate",
}


def _normalize_json_ld(data: dict) -> dict | None:
    """Map a single JSON-LD object to our broker schema fields."""
    if not isinstance(data, dict):
        return None

    schema_type = data.get("@type", "")
    if isinstance(schema_type, list):
        schema_type = " ".join(schema_type)

    if not any(t in schema_type.lower() for t in _USEFUL_SCHEMA_TYPES):
        return None

    result: dict = {}

    if name := data.get("name"):
        result["name"] = name

    if phone := data.get("telephone") or data.get("phone"):
        result["phone"] = str(phone)

    agg = data.get("aggregateRating") or {}
    if isinstance(agg, dict):
        if rating := agg.get("ratingValue"):
            try:
                result["rating"] = float(rating)
            except (ValueError, TypeError):
                pass
        if reviews := agg.get("reviewCount") or agg.get("ratingCount"):
            try:
                result["review_count"] = int(str(reviews).replace(",", ""))
            except (ValueError, TypeError):
                pass

    addr = data.get("address") or {}
    if isinstance(addr, dict):
        locality = addr.get("addressLocality") or addr.get("addressRegion")
        if locality:
            result["area"] = locality
    elif isinstance(addr, str) and addr:
        result["area"] = addr

    if desc := data.get("description"):
        result["bio"] = str(desc)[:300]

    return result if result.get("name") else None


def _extract_json_ld(html: str) -> dict | None:
    """
    Find all JSON-LD script tags in HTML and return the first one
    that maps to a useful broker/business schema type.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, Exception):
                continue

            candidates = []
            if isinstance(data, list):
                candidates = data
            elif isinstance(data, dict):
                candidates = data.get("@graph", [data])

            for item in candidates:
                result = _normalize_json_ld(item)
                if result:
                    return result
    except Exception:
        pass
    return None


def _is_sufficient(data: dict) -> bool:
    """JSON-LD is sufficient if it has a name + at least one meaningful field."""
    if not data.get("name"):
        return False
    return any(data.get(f) for f in ("phone", "rating", "review_count", "area"))


# ---------------------------------------------------------------------------
# Directory page link extraction (no Gemini needed)
# ---------------------------------------------------------------------------

def extract_profile_links(html: str, url_pattern: str, base_url: str) -> list[dict]:
    """
    Extract agent profile URLs from a portal directory page.

    Two-pass strategy:
    Pass 1 — <a href> tags (standard links)
    Pass 2 — regex across full HTML (catches JS onClick, data attrs, embedded JSON)

    Returns list of {name, profile_url}.
    """
    import re

    results = []
    seen_urls: set[str] = set()

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Pass 1: standard <a href> tags
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if url_pattern not in href:
                continue
            full_url = (base_url.rstrip("/") + href) if href.startswith("/") else href
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            name = a.get_text(strip=True)
            if not name or len(name) > 80:
                for parent in a.parents:
                    txt = parent.get_text(separator=" ", strip=True)
                    if 2 < len(txt) < 80 and len(txt.split()) <= 8:
                        name = txt
                        break

            if name and 2 < len(name) < 80:
                results.append({"name": name, "profile_url": full_url})

        # Pass 2: regex across entire HTML (handles JS-rendered links, onclick, JSON blobs)
        if not results:
            escaped = re.escape(url_pattern)
            raw_urls = re.findall(
                rf'(?:{re.escape(base_url)})?({escaped}[^\s"\'<>\\]+)',
                html,
            )
            for path in dict.fromkeys(raw_urls):  # deduplicate, preserve order
                full_url = base_url.rstrip("/") + path if path.startswith("/") else path
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)
                # Derive name from slug: company-{name}-in-{city}-agentid-{hex}
                slug = path.split("/")[-1]
                match = re.search(r"^(?:company-)?(.+?)-in-[a-z]+-agentid-", slug, re.IGNORECASE)
                if match:
                    name = match.group(1).replace("-", " ").title().strip()
                else:
                    # Fallback: strip agentid + city suffix best-effort
                    slug = re.sub(r"-agentid-[a-f0-9]+$", "", slug, flags=re.IGNORECASE)
                    slug = re.sub(r"-in-[a-z\-]+$", "", slug)
                    slug = re.sub(r"^company-", "", slug)
                    name = slug.replace("-", " ").title().strip()
                if name:
                    results.append({"name": name, "profile_url": full_url})

    except Exception as e:
        logger.warning(f"extract_profile_links failed: {e}")

    return results


# ---------------------------------------------------------------------------
# Raw HTML fetch (used by portal discovery sources)
# ---------------------------------------------------------------------------

async def scrapfly_fetch(
    url: str,
    use_js: bool = True,
    country: str = "IN",
    rendering_wait: int = 3000,
    headers: dict | None = None,
) -> str:
    """Fetch raw HTML via Scrapfly. Returns empty string on failure."""
    if not settings.scrapfly_key:
        logger.warning(f"SCRAPFLY_KEY not set — cannot fetch {url[:60]}")
        return ""
    try:
        from scrapfly import ScrapflyClient, ScrapeConfig
        client = ScrapflyClient(key=settings.scrapfly_key)
        result = await client.async_scrape(ScrapeConfig(
            url=url,
            asp=True,
            render_js=use_js,
            country=country,
            rendering_wait=rendering_wait,
            headers=headers or {},
        ))
        html = result.content or ""
        status = result.upstream_status_code
        cost = result.context.get("cost", "?")
        logger.info(f"Scrapfly fetch {url[:60]} | status={status} cost={cost} len={len(html)}")
        if status and status >= 400:
            return ""
        return html
    except Exception as e:
        logger.error(f"Scrapfly fetch failed for {url[:60]}: {e}")
        return ""


# ---------------------------------------------------------------------------
# HTML → plain text (Layer 2 fallback — denser than markdown, fewer tokens)
# ---------------------------------------------------------------------------

def _html_to_text(html: str, max_chars: int = 8000) -> str:
    """
    Strip nav/footer/scripts from raw HTML and return plain text.
    Capped at 8k chars (~2k tokens) — tighter than our markdown trim
    since we only reach here when JSON-LD failed.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "head", "iframe", "svg", "header"]):
        tag.decompose()
    lines = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]
    return "\n".join(lines)[:max_chars]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def scrapfly_scrape(
    url: str,
    prompt: str,
    use_js: bool = True,
    country: str = "IN",
    headers: dict | None = None,
    response_schema: type | None = None,
) -> dict | list:
    """
    Fetch via Scrapfly then extract structured data using the two-layer strategy.
    country="IN" for Indian portals, country="US" for LinkedIn.
    """
    if not settings.scrapfly_key:
        logger.warning(f"SCRAPFLY_KEY not set — falling back to local scrape for {url[:60]}")
        return await smart_scrape(url, prompt)

    try:
        from scrapfly import ScrapflyClient, ScrapeConfig

        client = ScrapflyClient(key=settings.scrapfly_key)
        result = await client.async_scrape(ScrapeConfig(
            url=url,
            asp=True,
            render_js=use_js,
            country=country,
            rendering_wait=3000,
            headers=headers or {},
        ))

        html = result.content or ""
        status = result.upstream_status_code
        cost = result.context.get("cost", "?")

        logger.info(f"Scrapfly {url[:60]} | status={status} cost={cost} len={len(html)}")

        if status and status >= 400:
            logger.warning(f"Scrapfly got {status} for {url[:60]}")
            return {}

        if len(html) < 200:
            logger.warning(f"Scrapfly returned near-empty response for {url[:60]}")
            return {}

        # --- Layer 1: JSON-LD (zero Gemini tokens) ---
        json_ld = _extract_json_ld(html)
        if json_ld and _is_sufficient(json_ld):
            logger.info(f"JSON-LD hit for {url[:60]} — Gemini skipped")
            return json_ld

        # --- Layer 2: plain text → Gemini ---
        text = _html_to_text(html)
        if not text:
            return {}

        # If JSON-LD had partial data, prepend it as a hint so Gemini can fill gaps
        if json_ld:
            text = f"Partial structured data: {json.dumps(json_ld)}\n\n{text}"

        logger.info(f"Gemini fallback for {url[:60]} ({len(text)} chars)")
        return await asyncio.to_thread(ask_gemini, text, prompt, response_schema)

    except Exception as e:
        logger.error(f"Scrapfly scrape failed for {url[:60]}: {e}")
        return {}
