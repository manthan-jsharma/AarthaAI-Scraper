import re
from urllib.parse import unquote
from playwright.async_api import async_playwright
from loguru import logger


def _unwrap_google_url(url: str | None) -> str | None:
    """Extract clean URL from Google redirect wrapper (/url?q=https://...)."""
    if not url:
        return None
    match = re.search(r'[?&]q=(https?://[^&]+)', url)
    if match:
        return unquote(match.group(1))
    return url


async def find_on_google_maps(name: str, city: str = "Bangalore") -> dict:
    """
    Search Google Maps for a specific broker by name.
    Returns {google_maps_url, google_business_data} or {} if not found.
    Used to find Maps listings for brokers discovered from other sources.
    """
    query = f"{name} real estate {city}"
    url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
    logger.info(f"Google Maps lookup: {query!r}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0"})
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(3000)

            results = await page.query_selector_all("[class*='Nv2PK'], [role='article']")
            if not results:
                await browser.close()
                return {}

            # Take only the first result — most relevant match
            first = results[0]
            maps_link = await _safe_attr(first, "a", "href")
            rating    = await _safe_text(first, "[class*='MW4etd']")
            reviews   = await _safe_text(first, "[class*='UY7F9']")
            address   = await _safe_text(first, "[class*='W4Efsd']:last-child")
            await browser.close()

            if not maps_link:
                return {}

            logger.info(f"Google Maps found for '{name}': {maps_link[:70]}")
            return {
                "google_maps_url": maps_link,
                "google_business_data": {
                    "rating": rating,
                    "review_count": reviews,
                    "address": address,
                },
            }
    except Exception as e:
        logger.error(f"Google Maps lookup failed for '{name}': {e}")
        return {}


async def discover_brokers(city: str = "Bangalore", max_results: int = 10) -> list[dict]:
    brokers = []
    query = f"real estate broker {city}"
    url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0"})
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(3000)

            # Scroll the results feed to load more listings
            feed = await page.query_selector("[role='feed']")
            if feed:
                prev_count = 0
                for _ in range(10):
                    await feed.evaluate("el => el.scrollTop += 3000")
                    await page.wait_for_timeout(2000)
                    cards = await page.query_selector_all("[class*='Nv2PK'], [role='article']")
                    if len(cards) >= max_results:
                        break
                    if len(cards) == prev_count:
                        break  # no new results loaded
                    prev_count = len(cards)

            results = await page.query_selector_all("[class*='Nv2PK'], [role='article']")
            logger.info(f"Google Maps: found {len(results)} results after scrolling")

            for result in results[:max_results]:
                try:
                    name = await _safe_text(result, "[class*='qBF1Pd'], h3, [class*='fontHeadlineSmall']")
                    rating = await _safe_text(result, "[class*='MW4etd']")
                    reviews = await _safe_text(result, "[class*='UY7F9']")
                    address = await _safe_text(result, "[class*='W4Efsd']:last-child")
                    link = await _safe_attr(result, "a", "href")

                    if name:
                        brokers.append({
                            "name": name.strip(),
                            "area": city,
                            "google_maps_url": link,
                            "source": "google_maps",
                            "google_business_data": {
                                "rating": rating,
                                "review_count": reviews,
                                "address": address,
                            },
                        })
                except Exception:
                    continue

            await browser.close()
    except Exception as e:
        logger.error(f"Google Maps discovery failed: {e}")

    return brokers


async def get_business_details(maps_url: str) -> dict:
    data = {}
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0"})
            await page.goto(maps_url, timeout=30000)
            await page.wait_for_timeout(4000)

            data["rating"] = await _safe_text_page(page, "[class*='fontDisplayLarge']")
            data["review_count"] = await _safe_text_page(page, "[class*='fontBodySmall'] span[aria-label*='review']")
            data["website"] = _unwrap_google_url(
                await _safe_attr_page(page, "a[data-item-id='authority']", "href")
            )

            # Phone: try aria-label on the phone button first (most reliable)
            phone = await _safe_attr_page(page, "button[data-item-id*='phone']", "aria-label")
            if not phone:
                phone = await _safe_text_page(page, "[data-item-id*='phone'] .fontBodyMedium")
            if not phone:
                # Fallback: find any element whose aria-label looks like a phone number
                phone = await page.evaluate("""() => {
                    const els = document.querySelectorAll('[aria-label]');
                    for (const el of els) {
                        const label = el.getAttribute('aria-label') || '';
                        if (/^[+\\d][\\d\\s\\-().]{7,}$/.test(label.trim())) return label.trim();
                    }
                    return null;
                }""")
            # Strip "Phone: " prefix that sometimes appears in aria-label
            if phone:
                phone = re.sub(r"^Phone:\s*", "", phone.strip(), flags=re.IGNORECASE)
            data["phone"] = phone or None

            await browser.close()
    except Exception as e:
        logger.error(f"Google Maps detail scrape failed: {e}")

    return data


async def _safe_text(element, selector: str) -> str | None:
    try:
        el = await element.query_selector(selector)
        return await el.inner_text() if el else None
    except Exception:
        return None


async def _safe_attr(element, selector: str, attr: str) -> str | None:
    try:
        el = await element.query_selector(selector)
        return await el.get_attribute(attr) if el else None
    except Exception:
        return None


async def _safe_text_page(page, selector: str) -> str | None:
    try:
        el = await page.query_selector(selector)
        return await el.inner_text() if el else None
    except Exception:
        return None


async def _safe_attr_page(page, selector: str, attr: str) -> str | None:
    try:
        el = await page.query_selector(selector)
        return await el.get_attribute(attr) if el else None
    except Exception:
        return None
