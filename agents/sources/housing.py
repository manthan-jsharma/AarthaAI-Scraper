from loguru import logger
from agents.scrapfly_scraper import scrapfly_fetch, extract_profile_links

# TODO: replace with real Housing.com agent directory URL once found in browser
DIRECTORY_URL = ""
BASE_URL = "https://housing.com"
PROFILE_PATTERN = "/agents/"


async def discover_brokers(city: str = "Bangalore", max_results: int = 5) -> list[dict]:
    if not DIRECTORY_URL:
        logger.info("Housing directory URL not set — skipping")
        return []

    logger.info(f"Housing directory: {DIRECTORY_URL}")
    html = await scrapfly_fetch(DIRECTORY_URL, rendering_wait=4000)
    if not html:
        return []

    links = extract_profile_links(html, PROFILE_PATTERN, BASE_URL)
    logger.info(f"Housing: extracted {len(links)} profile links from HTML")

    brokers = []
    for item in links[:max_results]:
        name = item["name"].strip()
        if not name:
            continue
        brokers.append({
            "name": name,
            "area": city,
            "source": "housing",
            "housing_url": item["profile_url"],
        })

    logger.info(f"Housing discovery: {len(brokers)} brokers")
    return brokers
