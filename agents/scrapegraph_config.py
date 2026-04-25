from config import settings

SCRAPEGRAPH_CONFIG = {
    "llm": {
        "model": "google_genai/gemini-2.5-flash-lite",
        "api_key": settings.google_api_key,
          "model_tokens": 1048576,
    },
    "embeddings": {
        "model": "fastembed/BAAI/bge-small-en-v1.5",
    },
    "headless": True,
}
