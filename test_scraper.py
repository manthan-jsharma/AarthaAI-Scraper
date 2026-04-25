import asyncio
from agents.smart_scraper import fetch_html, clean_html

async def test():
    print("Fetching MagicBricks...")
    html = await fetch_html("https://www.magicbricks.com/real-estate-agents/bangalore")
    content = clean_html(html)
    print(f"Got {len(content)} chars")
    print(content[:500])

asyncio.run(test())
