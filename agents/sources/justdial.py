import re
from bs4 import BeautifulSoup
from loguru import logger
from agents.scrapfly_scraper import scrapfly_fetch, extract_profile_links

DIRECTORY_URL = "https://www.justdial.com/Bengaluru/Real-Estate-Agents/nct-10192623"
BASE_URL = "https://www.justdial.com"

PROFILE_PATTERN = "_BZDET"

_ADDRESS_WORDS = re.compile(
    r"-(?:Near|Opp|Opp-To|Opposite|Above|Behind|Besides|Next-To|Adjacent|"
    r"No\.|No-|Shop|First|Second|Third|Ground|Floor|Plot|Flat|House|Building|"
    r"Sbi|Hdfc|Icici|Bank|Main|Road|Street|Nagar|Layout|Stage|Phase|Cross|Circle).*$",
    re.IGNORECASE,
)

# Indian phone: 10 digits starting 6-9, optional +91 prefix
_PHONE_RE = re.compile(r'(?:\+91[-\s]?)?[6-9]\d{9}')


def _name_from_slug(slug: str) -> str:
    """Extract agency name from JustDial URL slug, stripping address suffix."""
    name = re.sub(r"/\d{3}PXX.*$", "", slug)
    name = name.split("/")[-1]
    name = _ADDRESS_WORDS.sub("", name)
    return name.replace("-", " ").strip().title()


def _parse_jd_cards(html: str, max_results: int) -> list[dict]:
    """
    Parse listing cards from JustDial rendered HTML.
    Extracts name (from URL slug), phone, rating, review_count from each card.
    """
    soup = BeautifulSoup(html, "html.parser")
    brokers = []
    seen_names: set[str] = set()

    # JustDial renders cards as <li> elements — try known class patterns
    cards = (
        soup.select("li.cntanr") or
        soup.select("li[class*='resultbox']") or
        soup.select("li[data-id]") or
        []
    )
    logger.info(f"JustDial: {len(cards)} listing cards found in rendered HTML")

    for card in cards:
        # Profile URL from _BZDET anchor within the card
        link = card.find("a", href=lambda h: h and "_BZDET" in h)
        if not link:
            continue
        href = link.get("href", "")
        if not href:
            continue
        # Strip query params — we only need the canonical listing URL
        profile_url = (BASE_URL + href.split("?")[0]) if href.startswith("/") else href.split("?")[0]

        name = _name_from_slug(profile_url)
        if not name or name.lower() in seen_names:
            continue
        seen_names.add(name.lower())

        # Phone — priority order:
        # 1. data-phone attribute (sometimes set by JD's JS)
        # 2. tel: href link
        # 3. element with phone/mob/contact class
        # 4. regex scan of all card text
        phone = None
        phone_el = (
            card.find(attrs={"data-phone": True}) or
            card.find("a", href=re.compile(r"^tel:", re.I)) or
            card.find(class_=re.compile(r"mob|phone|contact", re.I))
        )
        if phone_el:
            raw = (
                phone_el.get("data-phone") or
                phone_el.get("href", "").replace("tel:", "").strip() or
                phone_el.get_text(strip=True)
            )
            # Discard if still masked (JD shows XX/PXX for unrevealed numbers)
            if raw and not re.search(r"XX|PXX", raw, re.I):
                m = _PHONE_RE.search(re.sub(r"[\s\-()]", "", raw))
                if m:
                    phone = m.group()

        # Regex fallback: scan all visible card text for a 10-digit Indian number
        if not phone:
            card_text = re.sub(r"[\s\-()]", "", card.get_text(" ", strip=True))
            m = _PHONE_RE.search(card_text)
            if m:
                phone = m.group()

        # Rating — element with "rat" or "star" in class name
        rating = None
        rat_el = card.find(class_=re.compile(r"\brat\b|star", re.I))
        if rat_el:
            try:
                rating = float(rat_el.get_text(strip=True))
            except (ValueError, TypeError):
                pass

        # Review count — element with "review" or "ratingcount" in class
        review_count = None
        rev_el = card.find(class_=re.compile(r"review|ratingcount|votes", re.I))
        if rev_el:
            nums = re.findall(r"\d+", rev_el.get_text())
            if nums:
                try:
                    review_count = int(nums[0])
                except (ValueError, TypeError):
                    pass

        brokers.append({
            "name": name,
            "phone": phone,
            "rating": rating,
            "review_count": review_count,
            "justdial_url": profile_url,
        })

        if len(brokers) >= max_results:
            break

    return brokers


async def discover_brokers(city: str = "Bangalore", max_results: int = 10) -> list[dict]:
    logger.info(f"JustDial directory: {DIRECTORY_URL}")
    html = await scrapfly_fetch(DIRECTORY_URL, use_js=True, rendering_wait=4000)
    if not html:
        return []

    brokers = _parse_jd_cards(html, max_results)

    # Fallback: card selectors missed — fall back to raw link extraction + slug names
    if not brokers:
        logger.warning("JustDial card parse found 0 — falling back to link extraction")
        links = extract_profile_links(html, PROFILE_PATTERN, BASE_URL)
        seen_names: set[str] = set()
        for item in links[: max_results * 2]:
            profile_url = item["profile_url"]
            name = _name_from_slug(profile_url)
            if not name or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            brokers.append({
                "name": name,
                "justdial_url": profile_url,
            })
            if len(brokers) >= max_results:
                break

    for b in brokers:
        b.setdefault("area", city)
        b["source"] = "justdial"

    logger.info(f"JustDial discovery: {len(brokers)} brokers")
    return brokers
