from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    groq_api_key: str
    google_api_key: str = ""
    supabase_url: str
    supabase_key: str
    scrapfly_key: str = ""

    google_sheets_credentials_path: str = "credentials.json"
    google_sheet_id: str = ""

    max_brokers_per_source: int = 15
    search_city: str = "Bangalore"
    request_delay_seconds: int = 2
    linkedin_scrape_per_run: int = 10

    class Config:
        env_file = ".env"


settings = Settings()
