import asyncio
from datetime import datetime
from loguru import logger

from config import settings
from database.client import upsert_broker
from agents.sources import instagram, google_maps
from agents.smart_scraper import smart_scrape
from agents.scrapfly_scraper import scrapfly_scrape
from agents.sources.portal_url_finder import find_portal_urls
from agents.schemas import WebsiteData, PortalProfile, LinkedInProfile


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

LINKEDIN_PROMPT = """
Extract the following from this LinkedIn profile page and return as JSON:
- followers: follower or connection count (or null)
- posts_last_30_days: estimated number of posts in the last 30 days (or null)
- avg_likes: average likes on recent posts (or null)
- avg_comments: average comments on recent posts (or null)
- has_property_content: boolean — do posts mention real estate, properties, or listings?
- bio: short professional headline or summary (or null)
"""

# Portal URL keys that Scrapfly should scrape (bot-protected sites)
PORTAL_KEYS = [
    ("magicbricks", "magicbricks_url"),
    ("99acres",     "acres99_url"),
    ("housing",     "housing_url"),
    ("nobroker",    "nobroker_url"),
    ("justdial",    "justdial_url"),
]

# LinkedIn Scrapfly config — US proxy works better than IN for LinkedIn
_LINKEDIN_SCRAPE_KWARGS = {
    "country": "US",
    "headers": {"Accept-Language": "en-US,en;q=0.5"},
}


def _presence_score(broker: dict) -> int:
    """
    Count how many key data sources a broker has a presence on.
    Used to decide whether LinkedIn scraping is worth spending credits on.
    """
    score = 0
    if broker.get("google_maps_url"):
        score += 1
    if broker.get("website_url"):
        score += 1
    if any(broker.get(url_key) for _, url_key in PORTAL_KEYS):
        score += 1
    return score


def _should_scrape_linkedin(broker: dict, budget: dict) -> bool:
    """
    Only scrape LinkedIn if:
    - broker has a linkedin_url
    - broker has presence on at least 2 other sources (worth the credit spend)
    - pipeline budget for LinkedIn scrapes hasn't been exhausted
    """
    if not broker.get("linkedin_url"):
        return False
    if budget["remaining"] <= 0:
        logger.info("LinkedIn budget exhausted for this pipeline run")
        return False
    if _presence_score(broker) < 2:
        logger.info(f"Skipping LinkedIn for '{broker['name']}' — low presence score")
        return False
    return True


def _promote_social_links(broker: dict, website_data: dict) -> dict:
    """
    Scan social_links from website scrape and promote instagram/linkedin URLs
    to top-level broker fields if not already set.
    """
    social_links = website_data.get("social_links") or []
    if not social_links:
        return {}

    promoted = {}
    for url in social_links:
        if not isinstance(url, str):
            continue
        url = url.strip()
        if not url:
            continue
        url_lower = url.lower()

        if "instagram.com" in url_lower and not broker.get("instagram_url"):
            promoted["instagram_url"] = url
        elif "linkedin.com" in url_lower and not broker.get("linkedin_url"):
            promoted["linkedin_url"] = url

    if promoted:
        logger.info(f"Promoted social links for '{broker['name']}': {list(promoted.keys())}")

    return promoted


async def _discover_missing_portal_urls(broker: dict) -> dict:
    """
    For any portal URL not yet in the broker record, run a DDG lookup
    to find their profile page. Returns only newly found {key: url} pairs.
    """
    missing = [key for _, key in PORTAL_KEYS if not broker.get(key)]
    if not missing:
        return {}

    logger.info(f"Finding portal URLs for '{broker['name']}' (missing: {missing})")
    found = await find_portal_urls(broker["name"], broker.get("city", "Bangalore"))

    return {k: v for k, v in found.items() if k in missing}


async def scrape_broker(
    broker_id: str,
    linkedin_budget: dict | None = None,
    pipeline_run_id: str | None = None,
    run_number: int | None = None,
):
    from database.client import get_client
    client = get_client()
    result = client.table("brokers").select("*").eq("id", broker_id).execute()
    if not result.data:
        logger.warning(f"Broker {broker_id} not found")
        return

    broker = result.data[0]
    updates = {"last_scraped_at": datetime.utcnow().isoformat()}

    # --- Step 1: discover missing portal profile URLs via DDG ---
    new_portal_urls = await _discover_missing_portal_urls(broker)
    if new_portal_urls:
        updates.update(new_portal_urls)
        broker = {**broker, **new_portal_urls}
        logger.info(f"Discovered portal URLs for '{broker['name']}': {list(new_portal_urls.keys())}")

    # --- Step 2: website scrape (local Playwright — broker sites aren't bot-protected) ---
    if broker.get("website_url"):
        logger.info(f"Scraping website for {broker['name']}")
        result_data = await smart_scrape(broker["website_url"], WEBSITE_PROMPT, WebsiteData)
        website_data = result_data if isinstance(result_data, dict) else {}
        updates["website_data"] = website_data

        # Promote instagram/linkedin found on the website to top-level fields
        social_promoted = _promote_social_links(broker, website_data)
        if social_promoted:
            updates.update(social_promoted)
            broker = {**broker, **social_promoted}

    # --- Step 3: portal scrapes via Scrapfly ---
    portal_data = {}
    for portal_key, url_key in PORTAL_KEYS:
        if broker.get(url_key):
            logger.info(f"Scraping {portal_key} for {broker['name']}")
            result_data = await scrapfly_scrape(broker[url_key], PORTAL_PROMPT, response_schema=PortalProfile)
            portal_data[portal_key] = result_data if isinstance(result_data, dict) else {}
    if portal_data:
        updates["portal_data"] = portal_data

    # --- Step 4: Google Maps detail (always — gets phone + website) ---
    if broker.get("google_maps_url"):
        existing = broker.get("google_business_data") or {}
        logger.info(f"Scraping Google Maps details for {broker['name']}")
        scraped = await google_maps.get_business_details(broker["google_maps_url"])
        if scraped:
            merged = {**existing, **{k: v for k, v in scraped.items() if v}}
            updates["google_business_data"] = merged
            if scraped.get("phone") and not broker.get("phone"):
                updates["phone"] = scraped["phone"]
            if scraped.get("website") and not broker.get("website_url"):
                updates["website_url"] = scraped["website"]
        else:
            updates["google_business_data"] = existing

    # --- Step 5: LinkedIn — only for high-presence brokers, capped per pipeline run ---
    _budget = linkedin_budget or {"remaining": 0}
    if _should_scrape_linkedin(broker, _budget):
        logger.info(f"Scraping LinkedIn for '{broker['name']}' "
                    f"(budget remaining: {linkedin_budget['remaining']})")
        result_data = await scrapfly_scrape(
            broker["linkedin_url"],
            LINKEDIN_PROMPT,
            response_schema=LinkedInProfile,
            **_LINKEDIN_SCRAPE_KWARGS,
        )
        updates["linkedin_data"] = result_data if isinstance(result_data, dict) else {}
        _budget["remaining"] -= 1

    # --- Step 6: Instagram (stubbed — URL promoted from website, content not scraped yet) ---
    if broker.get("instagram_url"):
        updates["instagram_data"] = await instagram.get_profile_data(broker["instagram_url"])

    updated_broker = {**broker, **updates}
    upsert_broker(updated_broker)
    logger.info(f"Scrape complete for {broker['name']}")

    from scoring.engine import calculate_and_save_scores
    calculate_and_save_scores(updated_broker, pipeline_run_id=pipeline_run_id, run_number=run_number)
    logger.info(f"Scores calculated for {broker['name']}")


async def scrape_all_brokers(pipeline_run_id: str | None = None, run_number: int | None = None):
    from database.client import get_client
    client = get_client()
    result = client.table("brokers").select("id, name").execute()
    brokers = result.data or []

    logger.info(f"Scraping {len(brokers)} brokers...")

    linkedin_budget = {"remaining": settings.linkedin_scrape_per_run}

    for broker in brokers:
        await scrape_broker(
            broker["id"],
            linkedin_budget,
            pipeline_run_id=pipeline_run_id,
            run_number=run_number,
        )
        await asyncio.sleep(settings.request_delay_seconds)

    logger.info(
        f"All brokers scraped. "
        f"LinkedIn scrapes used: {settings.linkedin_scrape_per_run - linkedin_budget['remaining']}"
    )
