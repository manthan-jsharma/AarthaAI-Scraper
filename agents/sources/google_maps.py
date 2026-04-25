from playwright.async_api import async_playwright
from loguru import logger


async def discover_brokers(city: str = "Bangalore", max_results: int = 50) -> list[dict]:
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
            data["website"] = await _safe_attr_page(page, "a[data-item-id='authority']", "href")

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
            data["phone"] = phone

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
