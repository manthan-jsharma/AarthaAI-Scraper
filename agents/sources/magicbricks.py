from loguru import logger
from agents.scrapfly_scraper import scrapfly_fetch, extract_profile_links

DIRECTORY_URL = "https://www.magicbricks.com/Real-estate-property-top-agents/agent-in-Bangalore?cityName=Bangalore&postedSince=-1&isNRI=N&page=1&category=S&multiLang=en"
BASE_URL = "https://www.magicbricks.com"
PROFILE_PATTERN = "/top-agent-details/"


async def discover_brokers(city: str = "Bangalore", max_results: int = 10) -> list[dict]:
    logger.info(f"MagicBricks directory: {DIRECTORY_URL}")
    html = await scrapfly_fetch(DIRECTORY_URL, rendering_wait=4000)
    if not html:
        return []

    links = extract_profile_links(html, PROFILE_PATTERN, BASE_URL)
    logger.info(f"MagicBricks: extracted {len(links)} profile links from HTML")

    brokers = []
    for item in links[:max_results]:
        name = item["name"].strip()
        if not name:
            continue
        brokers.append({
            "name": name,
            "area": city,
            "source": "magicbricks",
            "magicbricks_url": item["profile_url"],
        })

    logger.info(f"MagicBricks discovery: {len(brokers)} brokers")
    return brokers
