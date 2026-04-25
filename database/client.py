from supabase import create_client, Client
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger
from config import settings

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_key)
    return _client


def _reset_client() -> Client:
    global _client
    _client = create_client(settings.supabase_url, settings.supabase_key)
    return _client


_READONLY_FIELDS = {"id", "created_at"}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def upsert_broker(broker: dict) -> dict:
    try:
        client = get_client()
        if broker.get("phone"):
            existing = (
                client.table("brokers")
                .select("id")
                .eq("phone", broker["phone"])
                .execute()
            )
        else:
            existing = (
                client.table("brokers")
                .select("id")
                .eq("name", broker["name"])
                .eq("area", broker.get("area", ""))
                .execute()
            )

        if existing.data:
            broker_id = existing.data[0]["id"]
            current = (
                client.table("brokers").select("*").eq("id", broker_id).execute()
            ).data[0]
            update_data = {k: v for k, v in broker.items() if k not in _READONLY_FIELDS}

            # Don't blank out phone we already have
            if current.get("phone") and not update_data.get("phone"):
                update_data.pop("phone", None)

            # Merge JSON blobs — prefer existing True booleans, keep existing non-null values
            for field in ("website_data", "google_business_data", "portal_data",
                          "social_data", "linkedin_data", "instagram_data"):
                current_val = current.get(field)
                new_val = update_data.get(field)
                if current_val and isinstance(current_val, dict) and new_val and isinstance(new_val, dict):
                    merged = {**current_val, **new_val}
                    for key, val in merged.items():
                        # For boolean flags, True wins over False
                        if isinstance(val, bool):
                            merged[key] = current_val.get(key) or new_val.get(key, False)
                        # For scalar values, keep existing if new is null/empty
                        elif not val and current_val.get(key):
                            merged[key] = current_val[key]
                    update_data[field] = merged

            result = (
                client.table("brokers")
                .update(update_data)
                .eq("id", broker_id)
                .execute()
            )
        else:
            insert_data = {k: v for k, v in broker.items() if k not in _READONLY_FIELDS}
            result = client.table("brokers").insert(insert_data).execute()

        return result.data[0] if result.data else {}
    except Exception as e:
        # Reset the singleton so the next retry gets a fresh connection
        logger.warning(f"Supabase error, resetting client: {e}")
        _reset_client()
        raise


def get_all_brokers(order_by: str = "total_score", limit: int = 100) -> list[dict]:
    client = get_client()
    result = (
        client.table("brokers")
        .select("*")
        .order(order_by, desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_brokers_by_area(area: str) -> list[dict]:
    client = get_client()
    result = (
        client.table("brokers")
        .select("*")
        .ilike("area", f"%{area}%")
        .order("total_score", desc=True)
        .execute()
    )
    return result.data or []
