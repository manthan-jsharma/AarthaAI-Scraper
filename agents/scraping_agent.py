import asyncio
from datetime import datetime
from loguru import logger

from config import settings
from database.client import upsert_broker
from agents.sources import linkedin, instagram, google_maps
from agents.smart_scraper import smart_scrape


WEBSITE_PROMPT = """
Extract the following from this real estate broker website and return as JSON:
- has_website: true
- has_contact_page: boolean — is there a contact page or section?
- has_listings_page: boolean — are property listings shown?
- has_blog: boolean — is there a blog or news section?
- seo_title: the page title
- meta_description: meta description if present
- phone: any phone number found (or null)
- email: any email found (or null)
- social_links: list of any social media URLs found
"""

PORTAL_PROMPT = """
Extract the following from this real estate agent profile page and return as JSON:
- name: agent/broker full name
- agency: agency or company name if shown (or null)
- area: area or locality they serve
- listings_count: number of active listings shown (or 0)
- rating: rating score if shown e.g. 4.5 (or null)
- review_count: number of reviews (or 0)
- years_experience: years of experience if mentioned (or null)
- phone: phone number if visible (or null)
- profile_complete: boolean — does profile have photo, bio, and listings?
"""

SOCIAL_PROMPT = """
Extract the following from this social media profile page and return as JSON:
- followers: follower count (or null)
- posts_count: total posts (or null)
- posts_last_30_days: estimated count of posts in last 30 days (or null)
- avg_likes: average likes on recent posts (or null)
- avg_comments: average comments on recent posts (or null)
- has_property_content: boolean — do posts seem to be about real estate?
"""


async def scrape_broker(broker_id: str):
    from database.client import get_client
    client = get_client()
    result = client.table("brokers").select("*").eq("id", broker_id).execute()
    if not result.data:
        logger.warning(f"Broker {broker_id} not found")
        return

    broker = result.data[0]
    updates = {"last_scraped_at": datetime.utcnow().isoformat()}

    # Website scrape
    if broker.get("website_url"):
        logger.info(f"Scraping website for {broker['name']}")
        result_data = await smart_scrape(broker["website_url"], WEBSITE_PROMPT)
        updates["website_data"] = result_data if isinstance(result_data, dict) else {}

    # Property portal scrapes
    portal_data = {}
    for portal_key, url_key in [
        ("magicbricks", "magicbricks_url"),
        ("99acres", "acres99_url"),
        ("housing", "housing_url"),
        ("nobroker", "nobroker_url"),
        ("justdial", "justdial_url"),
    ]:
        if broker.get(url_key):
            logger.info(f"Scraping {portal_key} for {broker['name']}")
            result_data = await smart_scrape(broker[url_key], PORTAL_PROMPT)
            portal_data[portal_key] = result_data if isinstance(result_data, dict) else {}
    if portal_data:
        updates["portal_data"] = portal_data

    # Google Business — always scrape detail page for phone; merge with existing rating data
    if broker.get("google_maps_url"):
        existing = broker.get("google_business_data") or {}
        logger.info(f"Scraping Google Maps details for {broker['name']}")
        scraped = await google_maps.get_business_details(broker["google_maps_url"])
        if scraped:
            # Keep existing rating/review_count from discovery if detail scrape missed them
            merged = {**existing, **{k: v for k, v in scraped.items() if v}}
            updates["google_business_data"] = merged
            # Promote website and phone to top-level broker fields if not already set
            if scraped.get("phone") and not broker.get("phone"):
                updates["phone"] = scraped["phone"]
            if scraped.get("website") and not broker.get("website_url"):
                updates["website_url"] = scraped["website"]
        else:
            updates["google_business_data"] = existing

    # LinkedIn (stubbed)
    if broker.get("linkedin_url"):
        updates["linkedin_data"] = await linkedin.get_profile_data(broker["linkedin_url"])

    # Instagram (stubbed)
    if broker.get("instagram_url"):
        updates["instagram_data"] = await instagram.get_profile_data(broker["instagram_url"])

    updated_broker = {**broker, **updates}
    upsert_broker(updated_broker)
    logger.info(f"Scrape complete for {broker['name']}")

    from scoring.engine import calculate_and_save_scores
    calculate_and_save_scores(updated_broker)
    logger.info(f"Scores calculated for {broker['name']}")


async def scrape_all_brokers():
    from database.client import get_client
    client = get_client()
    result = client.table("brokers").select("id, name").execute()
    brokers = result.data or []

    logger.info(f"Scraping {len(brokers)} brokers...")
    for broker in brokers:
        await scrape_broker(broker["id"])
        await asyncio.sleep(settings.request_delay_seconds)

    logger.info("All brokers scraped.")
