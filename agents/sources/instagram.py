# STUB — Instagram scraping requires session cookies + paid proxies.
# Wire this up when BrightData/Oxylabs proxy is available.
# ScrapeGraphAI config will remain identical; just add proxy + cookie auth.

from loguru import logger


async def discover_brokers(city: str = "Bangalore", max_results: int = 20) -> list[dict]:
    logger.warning("Instagram scraping is stubbed — returning empty list")
    return []


async def get_profile_data(instagram_url: str) -> dict:
    logger.warning(f"Instagram profile scrape stubbed for {instagram_url}")
    return {
        "posts_last_30_days": None,
        "followers": None,
        "avg_likes": None,
        "avg_comments": None,
        "is_active": None,
    }
