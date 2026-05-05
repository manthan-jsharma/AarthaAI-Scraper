"""
Pydantic schemas for every Gemini extraction call in the pipeline.
Passing these to ask_gemini() forces Gemini to return guaranteed valid JSON
matching the schema — no parsing errors, no _safe_json_parse needed.
"""
from pydantic import BaseModel


class WebsiteData(BaseModel):
    has_website: bool = True
    has_contact_page: bool = False
    has_listings_page: bool = False
    has_blog: bool = False
    seo_title: str | None = None
    meta_description: str | None = None
    phone: str | None = None
    email: str | None = None
    social_links: list[str] = []


class PortalProfile(BaseModel):
    name: str | None = None
    agency: str | None = None
    area: str | None = None
    listings_count: int = 0
    rating: float | None = None
    review_count: int = 0
    years_experience: int | None = None
    phone: str | None = None
    profile_complete: bool = False


class LinkedInProfile(BaseModel):
    followers: int | None = None
    posts_last_30_days: int | None = None
    avg_likes: int | None = None
    avg_comments: int | None = None
    has_property_content: bool = False
    bio: str | None = None


class DiscoveredBroker(BaseModel):
    name: str
    area: str | None = None
    phone: str | None = None
    agency: str | None = None
    rating: float | None = None
    listings_count: int = 0
    has_contact_page: bool = False
    has_listings_page: bool = False
    has_blog: bool = False
    seo_title: str | None = None
    social_links: list[str] = []
    google_maps_url: str | None = None


class DiscoveredBrokers(BaseModel):
    brokers: list[DiscoveredBroker] = []
