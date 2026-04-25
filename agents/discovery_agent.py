import asyncio
from loguru import logger

from config import settings
from database.client import upsert_broker
from agents.sources import magicbricks, acres99, housing, nobroker, justdial, google_maps, google_search


SOURCES = [
    ("magicbricks", magicbricks.discover_brokers),
    ("99acres", acres99.discover_brokers),
    ("housing", housing.discover_brokers),
    ("nobroker", nobroker.discover_brokers),
    ("justdial", justdial.discover_brokers),
    ("google_maps", google_maps.discover_brokers),
    ("google_search", google_search.discover_brokers),
]


async def run_discovery():
    logger.info(f"Starting broker discovery for {settings.search_city}")
    all_brokers = []

    for source_name, source_fn in SOURCES:
        logger.info(f"Running source: {source_name}")
        try:
            result = await source_fn(city=settings.search_city, max_results=settings.max_brokers_per_source)
            logger.info(f"{source_name}: collected {len(result)} brokers")
            all_brokers.extend(result)
        except Exception as e:
            logger.error(f"{source_name} failed: {e}")
        await asyncio.sleep(1)

    # Deduplicate in memory by name before DB upsert
    seen_names = set()
    unique_brokers = []
    for broker in all_brokers:
        key = broker["name"].lower().strip()
        if key not in seen_names:
            seen_names.add(key)
            unique_brokers.append(broker)

    unique_brokers = unique_brokers[:30]
    logger.info(f"Total unique brokers after dedup: {len(unique_brokers)}")

    saved = 0
    for broker in unique_brokers:
        broker["city"] = settings.search_city
        try:
            upsert_broker(broker)
            saved += 1
        except Exception as e:
            logger.error(f"Failed to save broker {broker.get('name')}: {e}")

    logger.info(f"Discovery complete. Saved {saved} brokers to DB.")
    return unique_brokers
