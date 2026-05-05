from loguru import logger
from database.client import upsert_broker


def score_website(data: dict) -> int:
    """Max 30 points."""
    if not data:
        return 0
    score = 0
    if data.get("has_website"):
        score += 10
    if data.get("has_listings_page"):
        score += 5
    if data.get("has_contact_page"):
        score += 5
    if data.get("has_blog"):
        score += 5
    if data.get("seo_title"):
        score += 3
    if data.get("meta_description"):
        score += 2
    return min(score, 30)


def score_social_media(data: dict) -> int:
    """Max 20 points — Instagram/Facebook activity signals."""
    if not data:
        return 0
    score = 0

    followers = _to_int(data.get("followers"))
    if followers:
        if followers >= 5000:
            score += 5
        elif followers >= 1000:
            score += 3
        elif followers >= 200:
            score += 1

    posts_30d = _to_int(data.get("posts_last_30_days"))
    if posts_30d:
        if posts_30d >= 12:
            score += 8
        elif posts_30d >= 4:
            score += 5
        elif posts_30d >= 1:
            score += 2

    avg_likes = _to_int(data.get("avg_likes"))
    if avg_likes:
        if avg_likes >= 100:
            score += 4
        elif avg_likes >= 20:
            score += 2
        elif avg_likes >= 5:
            score += 1

    if data.get("has_property_content"):
        score += 3

    return min(score, 20)


def score_linkedin(data: dict) -> int:
    """Max 10 points."""
    if not data:
        return 0
    score = 0

    posts_30d = _to_int(data.get("posts_last_30_days"))
    if posts_30d and posts_30d >= 1:
        score += 5

    connections = _to_int(data.get("connections") or data.get("followers"))
    if connections:
        if connections >= 500:
            score += 3
        elif connections >= 100:
            score += 1

    if data.get("is_active"):
        score += 2

    return min(score, 10)


def score_google_business(data: dict) -> int:
    """Max 15 points."""
    if not data:
        return 0
    score = 0

    rating = _to_float(data.get("rating"))
    if rating:
        if rating >= 4.5:
            score += 8
        elif rating >= 4.0:
            score += 5
        elif rating >= 3.0:
            score += 2

    review_count = _to_int(data.get("review_count"))
    if review_count:
        if review_count >= 50:
            score += 5
        elif review_count >= 10:
            score += 3
        elif review_count >= 1:
            score += 1

    if data.get("website"):
        score += 2

    return min(score, 15)


def score_property_portals(portal_data: dict) -> int:
    """Max 15 points — across all portals combined."""
    if not portal_data:
        return 0
    score = 0
    active_portals = 0

    for portal_name, data in portal_data.items():
        if not data:
            continue
        active_portals += 1
        if data.get("profile_complete"):
            score += 2
        rating = _to_float(data.get("rating"))
        if rating and rating >= 4.0:
            score += 1

    score += min(active_portals * 2, 8)
    return min(score, 15)


def score_listings(portal_data: dict) -> int:
    """Max 5 points."""
    if not portal_data:
        return 0
    total_listings = 0
    for data in portal_data.values():
        if data:
            total_listings += _to_int(data.get("listings_count")) or 0

    if total_listings >= 20:
        return 5
    elif total_listings >= 10:
        return 4
    elif total_listings >= 5:
        return 3
    elif total_listings >= 1:
        return 2
    return 0


def score_video(website_data: dict, social_data: dict) -> int:
    """Max 5 points — YouTube or video content presence."""
    score = 0
    social_links = (website_data or {}).get("social_links", [])
    if any("youtube" in str(link).lower() for link in social_links):
        score += 5
    elif any("video" in str(link).lower() or "reel" in str(link).lower() for link in social_links):
        score += 3
    return min(score, 5)


def calculate_and_save_scores(
    broker: dict,
    pipeline_run_id: str | None = None,
    run_number: int | None = None,
) -> dict:
    from database.client import save_score_history

    website_data = broker.get("website_data") or {}
    if broker.get("website_url") and not website_data.get("has_website"):
        website_data = {**website_data, "has_website": True}
    social_data = broker.get("social_data") or {}
    linkedin_data = broker.get("linkedin_data") or {}
    google_data = broker.get("google_business_data") or {}
    portal_data = broker.get("portal_data") or {}
    instagram_data = broker.get("instagram_data") or {}

    combined_social = {**social_data, **instagram_data}

    scores = {
        "score_website": score_website(website_data),
        "score_social_media": score_social_media(combined_social),
        "score_linkedin": score_linkedin(linkedin_data),
        "score_google_business": score_google_business(google_data),
        "score_property_portals": score_property_portals(portal_data),
        "score_listings": score_listings(portal_data),
        "score_video": score_video(website_data, combined_social),
    }
    scores["total_score"] = sum(scores.values())

    logger.info(f"{broker.get('name')} → total score: {scores['total_score']}/100")
    upsert_broker({**broker, **scores})

    # Save snapshot to history if this is part of a tracked pipeline run
    if pipeline_run_id and run_number is not None and broker.get("id"):
        try:
            save_score_history(broker["id"], pipeline_run_id, run_number, scores)
        except Exception as e:
            logger.warning(f"Failed to save score history for {broker.get('name')}: {e}")

    return scores


def _to_int(val) -> int | None:
    import re
    try:
        # Handle formats like "(123)", "1,234", "500+", "123 reviews"
        s = re.sub(r"[^\d]", " ", str(val))
        nums = s.split()
        return int(nums[0]) if nums else None
    except Exception:
        return None


def _to_float(val) -> float | None:
    import re
    try:
        # Handle formats like "4.7\n(89)" or "4.7 stars"
        match = re.search(r"\d+\.\d+|\d+", str(val))
        return float(match.group()) if match else None
    except Exception:
        return None
