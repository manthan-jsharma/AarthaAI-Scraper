from loguru import logger


async def discover_brokers(city: str = "Bangalore", max_results: int = 20) -> list[dict]:
    # Stubbed — bot-blocked without residential proxies. Wire up ZenRows here when ready.
    logger.info(f"{__name__}: skipped (requires residential proxies)")
    return []
