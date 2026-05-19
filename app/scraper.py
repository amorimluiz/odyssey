"""URL parsing and Open Graph scraping primitives.

Normalization rules locked for MVP deduplication:
- Airbnb: accept any host matching `airbnb.<tld>` (including regional TLDs),
  but canonicalize to `https://www.airbnb.com/rooms/<id>`.
- Booking: accept `booking.com` (with or without `www`), require
  `/hotel/<cc>/<slug>(.<locale>)?.html`, strip locale suffix from slug,
  and canonicalize to `https://www.booking.com/hotel/<cc>/<slug>.html`.
- Query strings, fragments, and trailing slashes are removed by reconstruction.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import httpx


AIRBNB_CANONICAL_HOST = "www.airbnb.com"
BOOKING_CANONICAL_HOST = "www.booking.com"
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}
_TIMEOUT = httpx.Timeout(connect=5.0, read=8.0, write=5.0, pool=5.0)
_PRICE_RE = re.compile(
    r"(?:US\$|R\$|€|£|\$)\s?\d[\d.,]*(?:\s?(?:/|per|por)\s?[A-Za-z]+)?"
)


@dataclass(frozen=True)
class ParsedURL:
    source: str
    external_id: str
    normalized: str


@dataclass(frozen=True)
class OGData:
    title: str
    image_url: str | None
    description: str | None
    price: str | None


def parse_url(raw: str) -> ParsedURL | None:
    if not raw or not raw.strip():
        return None

    parsed = urlparse(raw.strip())
    if parsed.scheme not in {"http", "https"}:
        return None

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return None

    path = parsed.path.rstrip("/")
    path_parts = [segment for segment in path.split("/") if segment]

    if _is_airbnb_host(hostname):
        return _parse_airbnb(path_parts)
    if _is_booking_host(hostname):
        return _parse_booking(path_parts)
    return None


def _is_airbnb_host(hostname: str) -> bool:
    plain = hostname[4:] if hostname.startswith("www.") else hostname
    return bool(re.fullmatch(r"airbnb\..+", plain))


def _is_booking_host(hostname: str) -> bool:
    return hostname in {"booking.com", BOOKING_CANONICAL_HOST}


def _parse_airbnb(path_parts: list[str]) -> ParsedURL | None:
    if len(path_parts) < 2 or path_parts[0] != "rooms":
        return None

    room_id = path_parts[1]
    if not room_id.isdigit():
        return None

    normalized = f"https://{AIRBNB_CANONICAL_HOST}/rooms/{room_id}"
    return ParsedURL(source="airbnb", external_id=room_id, normalized=normalized)


def _parse_booking(path_parts: list[str]) -> ParsedURL | None:
    if len(path_parts) != 3:
        return None
    if path_parts[0] != "hotel":
        return None

    cc = path_parts[1].lower()
    filename = path_parts[2]
    if not filename.endswith(".html"):
        return None

    stem = filename[: -len(".html")]
    slug = _strip_locale_suffix(stem)
    if not slug:
        return None

    normalized = f"https://{BOOKING_CANONICAL_HOST}/hotel/{cc}/{slug}.html"
    return ParsedURL(source="booking", external_id=slug, normalized=normalized)


def _strip_locale_suffix(stem: str) -> str:
    locale_match = re.fullmatch(r"(?P<slug>.+)\.[a-z]{2}(?:-[a-z]{2})", stem)
    if locale_match:
        return locale_match.group("slug")
    return stem


def _extract_og_content(soup: BeautifulSoup, property_name: str) -> str | None:
    tag = soup.find("meta", attrs={"property": property_name})
    if not tag:
        return None
    content = tag.get("content")
    if content is None:
        return None
    stripped = content.strip()
    return stripped or None


def _extract_price(description: str | None) -> str | None:
    if not description:
        return None
    match = _PRICE_RE.search(description)
    if not match:
        return None
    return match.group(0).strip()


def _parse_og_markup(markup: str) -> OGData | None:
    soup = BeautifulSoup(markup, "html.parser")

    title = _extract_og_content(soup, "og:title")
    if not title:
        return None

    image_url = _extract_og_content(soup, "og:image")
    description = _extract_og_content(soup, "og:description")
    price = _extract_price(description)

    return OGData(
        title=title,
        image_url=image_url,
        description=description,
        price=price,
    )


async def fetch_og(url: str) -> OGData | None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_BROWSER_HEADERS) as client:
            response = await client.get(url)
    except httpx.HTTPError:
        return None

    if not (200 <= response.status_code < 300):
        return None

    return _parse_og_markup(response.text)
