# STUB — LinkedIn scraping requires authenticated sessions + paid proxies.
# Wire this up when BrightData/Oxylabs proxy is available.
# ScrapeGraphAI config will remain identical; just add proxy + cookie auth.

from loguru import logger


async def discover_brokers(city: str = "Bangalore", max_results: int = 20) -> list[dict]:
    logger.warning("LinkedIn scraping is stubbed — returning empty list")
    return []


async def get_profile_data(linkedin_url: str) -> dict:
    logger.warning(f"LinkedIn profile scrape stubbed for {linkedin_url}")
    return {
        "posts_last_30_days": None,
        "followers": None,
        "connections": None,
        "is_active": None,
    }
