"""
Pydantic schemas for every Gemini extraction call in the pipeline.
Passing these to ask_gemini() forces Gemini to return guaranteed valid JSON
matching the schema — no parsing errors, no _safe_json_parse needed.

All fields use `None` as default (not 0, False, or []) because Gemini rejects
Pydantic schemas that include a `default` key in the JSON schema output.
"""
from pydantic import BaseModel


class WebsiteData(BaseModel):
    has_website: bool | None = None
    has_contact_page: bool | None = None
    has_listings_page: bool | None = None
    has_blog: bool | None = None
    seo_title: str | None = None
    meta_description: str | None = None
    phone: str | None = None
    email: str | None = None
    social_links: list[str] | None = None


class PortalProfile(BaseModel):
    name: str | None = None
    agency: str | None = None
    area: str | None = None
    listings_count: int | None = None
    rating: float | None = None
    review_count: int | None = None
    years_experience: int | None = None
    phone: str | None = None
    profile_complete: bool | None = None


class LinkedInProfile(BaseModel):
    followers: int | None = None
    posts_last_30_days: int | None = None
    avg_likes: int | None = None
    avg_comments: int | None = None
    has_property_content: bool | None = None
    bio: str | None = None
    website: str | None = None


class DiscoveredBroker(BaseModel):
    name: str
    area: str | None = None
    phone: str | None = None
    agency: str | None = None
    rating: float | None = None
    listings_count: int | None = None
    has_contact_page: bool | None = None
    has_listings_page: bool | None = None
    has_blog: bool | None = None
    seo_title: str | None = None
    social_links: list[str] | None = None
    google_maps_url: str | None = None


class DiscoveredBrokers(BaseModel):
    brokers: list[DiscoveredBroker]


class PortalAgentListing(BaseModel):
    name: str
    profile_url: str | None = None
    area: str | None = None
    phone: str | None = None
    rating: float | None = None
    listings_count: int | None = None


class PortalAgentListings(BaseModel):
    agents: list[PortalAgentListing]
