import asyncio
from ddgs import DDGS
from loguru import logger
from agents.smart_scraper import smart_scrape

SEARCH_QUERIES = [
    "real estate broker agent bangalore koramangala contact phone",
    "real estate broker agent bangalore whitefield contact phone",
    "real estate broker agent bangalore hsr layout contact phone",
    "real estate broker agent bangalore indiranagar contact phone",
    "real estate broker agent bangalore jp nagar contact phone",
    "real estate broker agent bangalore electronic city contact phone",
    "real estate broker agent bangalore marathahalli contact phone",
    "real estate broker agent bangalore hebbal contact phone",
    "property dealer consultant bangalore sarjapur road contact",
    "real estate agent bangalore yelahanka contact phone",
]

# Only skip bot-blocked portal listing pages — everything else gets scraped
LISTING_PAGE_PATTERNS = [
    "justdial.com/bangalore/real-estate-agents",
    "justdial.com/bangalore/estate-agents",
    "housing.com/brokers/top/",
    "realestateindia.com/agents-brokers-in",
    "squareyards.com/real-estate-agents-in",
    "sulekha.com/real-estate-agents",
    "quikr.com/homes/property/real-estate-brokers",
    "indiahousing.com/property-dealers-list",
    "asklaila.com/search/bangalore",
    "commonfloor.com/real-estate-agents",
    "99acres.com/real-estate-agents-in",
    "magicbricks.com/agent-directory",
    "propertywala.com",
    "360realtors.com/property-in",
]

# Domains that are useless for broker data — pure social/news/job platforms
_JUNK_DOMAINS = {
    "wikipedia.org", "wikihow.com", "quora.com", "reddit.com",
    "slideshare.net", "scribd.com", "naukri.com", "indeed.com",
    "ambitionbox.com", "glassdoor.com",
}

SCRAPE_PROMPT = """
Extract all real estate brokers or agents from this page.
Return a JSON array where each item has:
- name: full name or business name (string, required)
- area: area or locality in Bangalore they serve (string or null)
- phone: phone number (string or null)
- agency: company name if different from broker name (string or null)
- rating: rating score if shown (number or null)
- listings_count: number of active listings shown (number or 0)
- has_contact_page: boolean — is there a contact section or page?
- has_listings_page: boolean — are property listings shown on this page?
- has_blog: boolean — is there a blog, articles, or news section?
- seo_title: the page HTML title tag text (string or null)
- social_links: list of any social media URLs found on the page (array of strings)
- google_maps_url: Google Maps URL for this broker if found anywhere on page (string or null)
If only one broker is on the page, still return a single-item array.
Do not return an empty array unless truly no broker info exists on the page.
"""


def _run_search(query: str) -> list[dict]:
    try:
        results = DDGS().text(query, max_results=10)
        return [r for r in results if r.get("href")]
    except Exception:
        return []


def _is_listing_page(url: str) -> bool:
    url_lower = url.lower()
    return any(p in url_lower for p in LISTING_PAGE_PATTERNS)


def _is_junk(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        domain = urlparse(url.lower()).netloc.replace("www.", "")
        return any(j in domain for j in _JUNK_DOMAINS)
    except Exception:
        return False


def _is_binary(url: str) -> bool:
    return url.lower().split("?")[0].endswith((".pdf", ".jpg", ".jpeg", ".png", ".gif", ".zip"))


BANGALORE_AREAS = [
    "koramangala", "whitefield", "hsr layout", "indiranagar", "jp nagar",
    "electronic city", "marathahalli", "hebbal", "sarjapur", "yelahanka",
    "bannerghatta", "jayanagar", "rajajinagar", "malleshwaram", "btm layout",
    "bellandur", "kr puram", "bommanahalli", "cv raman nagar", "richmond town",
]


def _extract_area(text: str, default: str) -> str:
    text_lower = text.lower()
    for area in BANGALORE_AREAS:
        if area in text_lower:
            return area.title()
    return default


def _extract_name(title: str, url: str) -> str:
    if title:
        for sep in [" - ", " | ", " – ", " · "]:
            if sep in title:
                title = title.split(sep)[0].strip()
        if title:
            return title
    try:
        path = url.split("/")[-1].split("?")[0]
        name = path.replace("-", " ").replace("_", " ").strip()
        parts = [p for p in name.split() if not p.isdigit()]
        return " ".join(parts).title() or url
    except Exception:
        return url


def _portal_url_key(url: str) -> str | None:
    url_lower = url.lower()
    if "magicbricks.com" in url_lower and "agent" in url_lower:
        return "magicbricks_url"
    if "99acres.com" in url_lower and "agent" in url_lower:
        return "acres99_url"
    if "housing.com" in url_lower and ("agent" in url_lower or "broker" in url_lower):
        return "housing_url"
    if "nobroker.in" in url_lower and "agent" in url_lower:
        return "nobroker_url"
    if "justdial.com" in url_lower:
        return "justdial_url"
    return None


def _is_blog_url(url: str) -> bool:
    url_lower = url.lower()
    return any(seg in url_lower for seg in ("/blog/", "/news/", "/article/", "/articles/", "/post/"))


async def _scrape_site(url: str, city: str) -> list[dict]:
    """smart_scrape fetches and extracts broker(s) from any URL — returns a list always."""
    try:
        result = await smart_scrape(url, SCRAPE_PROMPT)

        # Normalise to list
        if isinstance(result, list):
            items = result
        elif isinstance(result, dict):
            items = result.get("brokers", result.get("agents", result.get("content", [])))
            if not isinstance(items, list):
                items = [result] if result.get("name") else []
        else:
            items = []

        brokers = []
        portal_key = _portal_url_key(url)
        is_blog = _is_blog_url(url)

        for item in items:
            name = item.get("name")
            if not name or str(name).upper() in ("NA", "NULL", "NONE", ""):
                continue
            area = _extract_area(str(item.get("area") or "") + " " + url, city)

            broker = {
                "name": name,
                "area": area,
                "phone": item.get("phone"),
                "source": "google_search",
                "website_data": {
                    "has_website": True,
                    # If the URL itself is a blog page, credit has_blog even if LLM missed it
                    "has_blog": bool(item.get("has_blog")) or is_blog,
                    "has_contact_page": bool(item.get("has_contact_page")),
                    "has_listings_page": bool(item.get("has_listings_page")),
                    "seo_title": item.get("seo_title"),
                    "social_links": item.get("social_links") or [],
                },
            }

            # Set portal key if it's a portal URL, else website_url
            if portal_key:
                broker[portal_key] = url
            else:
                broker["website_url"] = url

            # If ScrapegraphAI found a Google Maps URL on the page, save it too
            maps_url = item.get("google_maps_url")
            if maps_url and "google.com/maps" in str(maps_url):
                broker["google_maps_url"] = maps_url

            brokers.append(broker)

        logger.info(f"ScrapegraphAI {url[:60]}: extracted {len(brokers)} brokers")
        return brokers
    except Exception as e:
        logger.warning(f"Scrape failed for {url}: {e}")
        return []


async def discover_brokers(city: str = "Bangalore", max_results: int = 25) -> list[dict]:
    brokers = []
    seen_urls = set()
    scrape_urls = []

    # Phase 1: collect all URLs via DDG
    for query_template in SEARCH_QUERIES:
        query = query_template.replace("bangalore", city.lower())
        try:
            results = await asyncio.to_thread(_run_search, query)
            logger.info(f"DDG '{query[:55]}...': {len(results)} results")

            for result in results:
                url = result.get("href", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Skip bot-blocked portal listing pages and binary files / junk domains
                if _is_listing_page(url) or _is_junk(url) or _is_binary(url):
                    continue

                title = result.get("title", "")
                body = result.get("body", "")
                area = _extract_area(title + " " + body + " " + url, city)

                # Portal profile URLs — save directly without scraping (bot-blocked anyway)
                portal_key = _portal_url_key(url)
                if portal_key:
                    brokers.append({
                        "name": _extract_name(title, url),
                        "area": area,
                        "source": "google_search",
                        portal_key: url,
                    })
                else:
                    # Everything else — broker website, blog, portfolio — send to ScrapegraphAI
                    scrape_urls.append((url, area))

        except Exception as e:
            logger.error(f"DDG search failed for '{query}': {e}")

    logger.info(f"Phase 1: {len(brokers)} portal URLs, {len(scrape_urls)} sites to scrape")

    # Phase 2: ScrapegraphAI on all non-portal URLs
    for url, area in scrape_urls:
        if len(brokers) >= max_results:
            break
        extracted = await _scrape_site(url, area)
        brokers.extend(extracted)
        await asyncio.sleep(1)

    logger.info(f"Google Search: {len(brokers)} brokers total")
    return brokers[:max_results]
