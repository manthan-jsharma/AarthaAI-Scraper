import google.generativeai as genai
from loguru import logger

from config import settings
from database.client import upsert_broker

genai.configure(api_key=settings.google_api_key)
client = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite",
    system_instruction="""You are a digital marketing consultant specializing in Indian real estate.
Analyze a broker's digital presence data and provide actionable insights.
Be specific, concise, and direct. Focus on what matters for lead generation.""",
)


def build_prompt(broker: dict) -> str:
    scores = {
        "Website": broker.get("score_website", 0),
        "Social Media": broker.get("score_social_media", 0),
        "LinkedIn": broker.get("score_linkedin", 0),
        "Google Business": broker.get("score_google_business", 0),
        "Property Portals": broker.get("score_property_portals", 0),
        "Listings": broker.get("score_listings", 0),
        "Video": broker.get("score_video", 0),
        "Total": broker.get("total_score", 0),
    }

    website_data   = broker.get("website_data") or {}
    linkedin_data  = broker.get("linkedin_data") or {}
    instagram_data = broker.get("instagram_data") or {}
    google_data    = broker.get("google_business_data") or {}
    portal_data    = broker.get("portal_data") or {}

    return f"""
Broker: {broker.get('name')}
Area: {broker.get('area')}, Bangalore
Scores: {scores}

Website: has_website={website_data.get('has_website')}, has_blog={website_data.get('has_blog')}, seo_title={website_data.get('seo_title')}
Google Business: rating={google_data.get('rating')}, reviews={google_data.get('review_count')}
Active Portals: {list(portal_data.keys())}
LinkedIn: followers={linkedin_data.get('followers')}, posts_last_30_days={linkedin_data.get('posts_last_30_days')}, has_property_content={linkedin_data.get('has_property_content')}
Instagram: followers={instagram_data.get('followers')}, posts_last_30_days={instagram_data.get('posts_last_30_days')}, has_property_content={instagram_data.get('has_property_content')}

Based on this data, provide:
1. STRENGTHS (2-3 bullet points of what they're doing well)
2. WEAKNESSES (2-3 bullet points of what's missing or weak)
3. MISSED OPPORTUNITIES (2-3 specific things they should start doing)
4. SALES PITCH (1-2 sentences — why would a property owner choose this broker? Use their strengths.)

Keep each section to 2-3 lines max. Be specific to their actual data.
"""


def generate_insights(broker: dict) -> dict:
    prompt = build_prompt(broker)

    try:
        response = client.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(temperature=0.4, max_output_tokens=600),
        )
        raw = response.text
        insights = _parse_insights(raw)
    except Exception as e:
        logger.error(f"Gemini insight generation failed for {broker.get('name')}: {e}")
        insights = {
            "strengths": None,
            "weaknesses": None,
            "missed_opportunities": None,
            "sales_pitch": None,
        }

    upsert_broker({**broker, **insights})
    logger.info(f"Insights generated for {broker.get('name')}")
    return insights


def _parse_insights(raw: str) -> dict:
    sections = {"strengths": "", "weaknesses": "", "missed_opportunities": "", "sales_pitch": ""}
    current = None

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        if "strength" in lower:
            current = "strengths"
        elif "weakness" in lower:
            current = "weaknesses"
        elif "missed" in lower or "opportunit" in lower:
            current = "missed_opportunities"
        elif "sales pitch" in lower or "pitch" in lower:
            current = "sales_pitch"
        elif current:
            sections[current] += line + "\n"

    return {k: v.strip() or None for k, v in sections.items()}


def generate_insights_for_all():
    from database.client import get_all_brokers
    brokers = get_all_brokers()
    logger.info(f"Generating insights for {len(brokers)} brokers...")
    for broker in brokers:
        if broker.get("total_score", 0) > 0:
            generate_insights(broker)
