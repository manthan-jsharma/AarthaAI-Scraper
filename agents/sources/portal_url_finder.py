"""
DDG-based URL finder for brokers.

Query strategy:
  Primary:  "{agency}" {name} real estate {city} {platform}
            — agency quoted (exact), individual name unquoted (context hint)
            — when name == agency, name is omitted to avoid redundancy
  Fallback: "{agency}" real estate {city} {platform}
            — agency only, no individual name

Quoting only the agency name (not the individual name) avoids false positives
from common first names hitting unrelated results (e.g. "Salman" → Salman Khan).

MagicBricks and 99acres excluded — noindex/nofollow, DDG has never indexed them.
"""
import asyncio
from ddgs import DDGS
from loguru import logger


_WEBSITE_EXCLUDE = [
    # property portals
    "magicbricks", "99acres", "housing.com", "nobroker", "justdial",
    "realestateindia.com", "commonfloor", "proptiger", "squareyards",
    "makaan", "sulekha", "olx", "indiamart",
    # social / search
    "linkedin", "instagram", "facebook", "youtube", "twitter", "google.com",
    # knowledge / forums
    "wikipedia", "quora", "reddit",
    # RE associations (not a broker's own site)
    "brai.in", "naredco", "credai",
    # news sites
    "timesofindia", "ndtv", "thehindu", "hindustantimes",
    "mumbainewsexpress", "economictimes", "moneycontrol",
]

# {agency} = quoted company name anchor
# {name}   = unquoted individual name (only appended when different from agency)
# {city}   = city (default: Bangalore)
SEARCH_TARGETS: dict[str, dict] = {
    "linkedin_url": {
        "queries": [
            '"{agency}" {name} real estate {city} linkedin',
            '"{agency}" real estate {city} linkedin',
        ],
        "valid": lambda u: (
            "linkedin.com/in/" in u.lower() or
            "linkedin.com/company/" in u.lower()
        ),
    },
    "housing_url": {
        "queries": [
            '"{agency}" {name} real estate {city} housing.com',
            '"{agency}" real estate {city} housing.com',
        ],
        "valid": lambda u: "housing.com" in u.lower(),
    },
    "nobroker_url": {
        "queries": [
            '"{agency}" {name} real estate {city} nobroker',
            '"{agency}" real estate {city} nobroker',
        ],
        "valid": lambda u: "nobroker.in" in u.lower(),
    },
    "justdial_url": {
        "queries": [
            '"{agency}" {name} real estate {city} justdial',
            '"{agency}" real estate {city} justdial',
        ],
        "valid": lambda u: "justdial.com" in u.lower(),
    },
    "website_url": {
        "queries": [
            '"{agency}" {name} real estate broker {city}',
            '"{agency}" real estate broker {city}',
            '"{agency}" property consultants {city}',
        ],
        "valid": lambda u: not any(x in u.lower() for x in _WEBSITE_EXCLUDE),
    },
    "google_maps_url": {
        "queries": [
            '"{agency}" {name} real estate {city} google maps',
            '"{agency}" real estate {city} google maps',
        ],
        "valid": lambda u: (
            "google.com/maps" in u.lower() or
            "maps.app.goo.gl" in u.lower()
        ),
    },
}


def _ddg_search(query: str) -> list[str]:
    try:
        results = DDGS().text(query, max_results=5)
        return [r["href"] for r in results if r.get("href")]
    except Exception:
        return []


async def find_missing_urls(
    broker: dict,
    individual_name: str | None = None,
    agency: str | None = None,
) -> dict[str, str]:
    """
    Search DDG for any URL fields not yet in the broker record.
    Returns {field_key: url} for newly found URLs only.
    """
    missing = [k for k in SEARCH_TARGETS if not broker.get(k)]
    if not missing:
        return {}

    org  = agency or broker.get("agency") or broker["name"]
    name = individual_name or ""
    city = broker.get("city", "Bangalore")

    # When individual name is the same as agency (JustDial/Maps case), don't repeat it
    name_differs = name and name.lower().strip() != org.lower().strip()

    logger.info(f"DDG — agency='{org}' individual='{name or '—'}' city='{city}' targets={missing}")
    found: dict[str, str] = {}

    for field_key in missing:
        cfg = SEARCH_TARGETS[field_key]

        for query_template in cfg["queries"]:
            # Skip queries containing {name} when we have no distinct individual name
            if "{name}" in query_template and not name_differs:
                continue

            query = query_template.format(
                agency=org,
                name=name if name_differs else "",
                city=city,
            ).strip()

            urls = await asyncio.to_thread(_ddg_search, query)
            logger.debug(f"  query: {query!r} → {len(urls)} results")

            for url in urls:
                if cfg["valid"](url):
                    found[field_key] = url
                    logger.info(f"DDG found {field_key} for '{org}': {url[:70]}")
                    break

            if field_key in found:
                break

        await asyncio.sleep(0.5)

    if not found:
        logger.info(f"DDG: no new URLs found for '{org}'")

    return found
