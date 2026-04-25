import gspread
from google.oauth2.service_account import Credentials
from loguru import logger

from config import settings
from database.client import get_all_brokers

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "Name", "Area", "Total Score",
    "Website Score", "Social Score", "LinkedIn Score",
    "Google Business Score", "Portals Score", "Listings Score", "Video Score",
    "Phone", "Website URL", "Google Maps URL",
    "Google Rating", "Google Reviews",
    "Strengths", "Weaknesses", "Missed Opportunities", "Sales Pitch",
    "Source", "Last Scraped",
]


def export_brokers_to_sheets():
    if not settings.google_sheet_id:
        logger.warning("GOOGLE_SHEET_ID not set — skipping Sheets export")
        return

    try:
        creds = Credentials.from_service_account_file(
            settings.google_sheets_credentials_path, scopes=SCOPES
        )
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(settings.google_sheet_id).sheet1
    except Exception as e:
        logger.error(f"Google Sheets connection failed: {e}")
        return

    brokers = get_all_brokers(order_by="total_score", limit=500)
    if not brokers:
        logger.warning("No brokers to export")
        return

    rows = [HEADERS]
    for b in brokers:
        google_data = b.get("google_business_data") or {}
        rows.append([
            b.get("name", ""),
            b.get("area", ""),
            b.get("total_score", 0),
            b.get("score_website", 0),
            b.get("score_social_media", 0),
            b.get("score_linkedin", 0),
            b.get("score_google_business", 0),
            b.get("score_property_portals", 0),
            b.get("score_listings", 0),
            b.get("score_video", 0),
            b.get("phone", ""),
            b.get("website_url", ""),
            b.get("google_maps_url", ""),
            google_data.get("rating", ""),
            google_data.get("review_count", ""),
            b.get("strengths", ""),
            b.get("weaknesses", ""),
            b.get("missed_opportunities", ""),
            b.get("sales_pitch", ""),
            b.get("source", ""),
            b.get("last_scraped_at", ""),
        ])

    sheet.clear()
    sheet.update("A1", rows)
    logger.info(f"Exported {len(brokers)} brokers to Google Sheets")
