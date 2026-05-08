from loguru import logger
from agents.scrapfly_scraper import scrapfly_fetch, extract_profile_links

# TODO: replace with real 99acres agent directory URL once found in browser
DIRECTORY_URL = ""
BASE_URL = "https://www.99acres.com"
PROFILE_PATTERN = "/agent-profile/"


async def discover_brokers(city: str = "Bangalore", max_results: int = 5) -> list[dict]:
    if not DIRECTORY_URL:
        logger.info("99acres directory URL not set — skipping")
        return []

    logger.info(f"99acres directory: {DIRECTORY_URL}")
    html = await scrapfly_fetch(DIRECTORY_URL, rendering_wait=4000)
    if not html:
        return []

    links = extract_profile_links(html, PROFILE_PATTERN, BASE_URL)
    logger.info(f"99acres: extracted {len(links)} profile links from HTML")

    brokers = []
    for item in links[:max_results]:
        name = item["name"].strip()
        if not name:
            continue
        brokers.append({
            "name": name,
            "area": city,
            "source": "99acres",
            "acres99_url": item["profile_url"],
        })

    logger.info(f"99acres discovery: {len(brokers)} brokers")
    return brokers
