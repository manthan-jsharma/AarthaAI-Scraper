"""
DDG-based portal profile URL lookup.
For each broker we already know, searches each portal site to find their
individual agent profile URL, which Scrapfly then scrapes.
"""
import asyncio
from ddgs import DDGS
from loguru import logger


# Each portal: DDG site-search query + URL validation rule
PORTAL_SEARCH: dict[str, dict] = {
    "magicbricks_url": {
        "query": 'site:magicbricks.com "{name}" bangalore real estate agent',
        "valid": lambda u: "magicbricks.com" in u and (
            "agent-profile" in u or "realestate-agent" in u
        ),
    },
    "acres99_url": {
        "query": 'site:99acres.com "{name}" bangalore agent',
        "valid": lambda u: "99acres.com" in u and "agent" in u,
    },
    "housing_url": {
        "query": 'site:housing.com "{name}" bangalore agent',
        "valid": lambda u: "housing.com" in u and ("agent" in u or "broker" in u),
    },
    "nobroker_url": {
        "query": 'site:nobroker.in "{name}" bangalore',
        "valid": lambda u: "nobroker.in" in u and "agent" in u,
    },
    "justdial_url": {
        "query": 'site:justdial.com "{name}" bangalore real estate',
        "valid": lambda u: "justdial.com" in u and "bangalore" in u.lower(),
    },
}


def _ddg_search(query: str) -> list[str]:
    try:
        results = DDGS().text(query, max_results=5)
        return [r["href"] for r in results if r.get("href")]
    except Exception:
        return []


async def find_portal_urls(name: str, city: str = "Bangalore") -> dict[str, str]:
    """
    Search DDG for each portal's agent profile page for a given broker name.
    Returns only portal keys where a valid profile URL was found.
    """
    found: dict[str, str] = {}

    for portal_key, cfg in PORTAL_SEARCH.items():
        query = cfg["query"].format(name=name, city=city)
        urls = await asyncio.to_thread(_ddg_search, query)

        for url in urls:
            if cfg["valid"](url.lower()):
                found[portal_key] = url
                logger.info(f"portal_url_finder | {portal_key} for '{name}': {url}")
                break

        await asyncio.sleep(0.5)  # avoid DDG rate limiting between portal searches

    if not found:
        logger.info(f"portal_url_finder | no portal profiles found for '{name}'")

    return found
