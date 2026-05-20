import asyncio
import json
import re
import google.generativeai as genai
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from loguru import logger
from config import settings

genai.configure(api_key=settings.google_api_key)
_model = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite",
    system_instruction=(
        "You are a data extraction assistant. "
        "Always respond with valid JSON only. No explanation, no markdown, just raw JSON."
    ),
)


async def fetch_html(url: str, wait_ms: int = 4000) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            extra_http_headers={
                "Accept-Language": "en-IN,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            },
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()
        try:
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(wait_ms)

            # Scroll to bottom to trigger lazy-loaded footer content
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)

            # Query social + contact links directly from the live DOM via JS.
            # More reliable than BeautifulSoup on serialized HTML — sees the
            # fully rendered state including JS-injected footer/nav links.
            live_links: list[str] = await page.evaluate("""() => {
                const domains = ['instagram.com','linkedin.com','facebook.com',
                                 'youtube.com','twitter.com','x.com'];
                return [...document.querySelectorAll('a[href]')]
                    .map(a => a.href)
                    .filter(href => domains.some(d => href.toLowerCase().includes(d)));
            }""")

            html = await page.content()

            # Inject the live links back into the HTML as a plain section
            # so clean_html's BeautifulSoup pass can see them
            if live_links:
                unique = list(dict.fromkeys(live_links))
                injected = '<div id="__social_links__">' + "".join(
                    f'<a href="{h}">{h}</a>' for h in unique
                ) + "</div>"
                html = html.replace("</body>", injected + "</body>", 1) or html + injected
                logger.info(f"fetch_html: injected {len(unique)} social links for {url[:60]}")

        except Exception as e:
            logger.warning(f"fetch_html failed for {url}: {e}")
            html = ""
        finally:
            await browser.close()
    return html


_SOCIAL_DOMAINS = [
    "instagram.com", "linkedin.com", "facebook.com",
    "youtube.com", "twitter.com", "x.com",
]

def clean_html(html: str, max_chars: int = 12000) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Extract social + tel + mailto links BEFORE stripping nav/footer
    # (social icons live in footer/nav which we remove below)
    preserved_links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if any(d in href.lower() for d in _SOCIAL_DOMAINS):
            preserved_links.append(href)
        elif href.startswith("tel:") or href.startswith("mailto:"):
            preserved_links.append(href)

    for tag in soup(["script", "style", "nav", "footer", "head", "iframe", "svg"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    cleaned = "\n".join(lines)

    # Truncate main content FIRST, then append links — ensures links are never cut off
    cleaned = cleaned[:max_chars]
    if preserved_links:
        unique_links = list(dict.fromkeys(preserved_links))  # deduplicate, preserve order
        cleaned += "\n\nLinks found on page:\n" + "\n".join(unique_links)

    return cleaned


def ask_gemini(
    content: str,
    prompt: str,
    response_schema: type | None = None,
) -> list | dict:
    """
    Call Gemini to extract structured data from content.
    Always uses response_mime_type=application/json to force valid JSON output.
    If response_schema (Pydantic model) is provided, validates and fills defaults
    after parsing — avoids Gemini API rejecting Pydantic's `default` schema fields.
    """
    try:
        gen_config = genai.GenerationConfig(
            temperature=0.1,
            max_output_tokens=2048,
            response_mime_type="application/json",
        )
        response = _model.generate_content(
            f"{prompt}\n\nPage content:\n{content}",
            generation_config=gen_config,
        )
        raw = response.text.strip()
        raw = re.sub(r"^```json\s*|^```\s*|```$", "", raw, flags=re.MULTILINE).strip()
        result = _safe_json_parse(raw)

        if response_schema and result:
            try:
                validated = response_schema.model_validate(result)
                return validated.model_dump()
            except Exception:
                return result

        return result

    except Exception as e:
        logger.error(f"Gemini extraction failed: {e}")
        return {}


def _safe_json_parse(raw: str) -> list | dict:
    """Fallback JSON parser with truncation recovery — only used without response_schema."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    try:
        if raw.startswith("["):
            last_close = raw.rfind("},")
            if last_close == -1:
                last_close = raw.rfind("}")
            if last_close != -1:
                return json.loads(raw[: last_close + 1] + "]")
    except Exception:
        pass

    try:
        if raw.startswith("{"):
            last_close = raw.rfind("}")
            if last_close != -1:
                return json.loads(raw[: last_close + 1])
    except Exception:
        pass

    return {}


async def smart_scrape(
    url: str,
    prompt: str,
    response_schema: type | None = None,
) -> list | dict:
    html = await fetch_html(url)
    if not html:
        return {}
    content = clean_html(html)
    return await asyncio.to_thread(ask_gemini, content, prompt, response_schema)
