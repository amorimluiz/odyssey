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

import json
from dataclasses import dataclass
import time
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, urlencode, urlparse

from bs4 import BeautifulSoup
import httpx


AIRBNB_CANONICAL_HOST = "www.airbnb.com"
BOOKING_CANONICAL_HOST = "www.booking.com"
BOOKING_ALLOWED_QUERY_KEYS = {
    "checkin",
    "checkout",
    "group_adults",
    "group_children",
    "highlighted_blocks",
    "matching_block_id",
    "no_rooms",
    "room1",
    "room2",
    "room3",
    "room4",
    "room5",
    "sb_price_type",
    "selected_currency",
    "type",
}
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
_last_fetch_meta: dict[str, str | int | bool | None] = {
    "source": None,
    "status": "unknown",
    "elapsed_ms": 0,
    "failure_reason": None,
    "price_found": False,
    "fetch_url_host": None,
}


@dataclass(frozen=True)
class ParsedURL:
    source: str
    external_id: str
    normalized: str
    fetch_url: str


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
        return _parse_booking(path_parts, parsed)
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
    return ParsedURL(source="airbnb", external_id=room_id, normalized=normalized, fetch_url=normalized)


def _parse_booking(path_parts: list[str], parsed_url) -> ParsedURL | None:
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
    fetch_url = _build_booking_fetch_url(normalized, parsed_url.query)
    return ParsedURL(source="booking", external_id=slug, normalized=normalized, fetch_url=fetch_url)


def _strip_locale_suffix(stem: str) -> str:
    locale_match = re.fullmatch(r"(?P<slug>.+)\.[a-z]{2}(?:-[a-z]{2})", stem)
    if locale_match:
        return locale_match.group("slug")
    return stem


def _build_booking_fetch_url(normalized: str, raw_query: str) -> str:
    if not raw_query:
        return normalized

    filtered_query = [
        (key, value)
        for key, value in parse_qsl(raw_query, keep_blank_values=True)
        if key in BOOKING_ALLOWED_QUERY_KEYS
    ]
    if not filtered_query:
        return normalized
    return f"{normalized}?{urlencode(filtered_query, doseq=True)}"


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


def _extract_meta_content(
    soup: BeautifulSoup,
    *,
    attrs: dict[str, str],
) -> str | None:
    tag = soup.find("meta", attrs=attrs)
    if not tag:
        return None
    content = tag.get("content")
    if content is None:
        return None
    stripped = content.strip()
    return stripped or None


def _format_price_amount(amount: str, currency: str | None = None) -> str | None:
    cleaned_amount = amount.strip()
    if not cleaned_amount:
        return None

    normalized_amount = cleaned_amount.replace(" ", "").replace("\xa0", "")
    normalized_amount = normalized_amount.replace(",", ".")
    normalized_amount = re.sub(r"[^0-9.]", "", normalized_amount)
    if not normalized_amount:
        return None

    try:
        decimal_amount = Decimal(normalized_amount)
    except InvalidOperation:
        return None

    if decimal_amount == decimal_amount.to_integral():
        amount_text = f"{int(decimal_amount):,}"
        amount_text = amount_text.replace(",", ".")
    else:
        amount_text = format(decimal_amount.normalize(), "f").rstrip("0").rstrip(".")
        amount_text = amount_text.replace(".", ",", 1)

    currency_symbol_map = {
        "BRL": "R$",
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
    }
    if currency:
        currency = currency.strip().upper()
        symbol = currency_symbol_map.get(currency, currency)
        return f"{symbol} {amount_text}"
    return amount_text


def _extract_price_from_jsonld(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        price = _find_structured_price(data)
        if price:
            return price
    return None


def _coerce_structured_price(candidate: dict[str, object]) -> str | None:
    price = candidate.get("price")
    if price is None:
        price = candidate.get("lowPrice") or candidate.get("highPrice")
    if price is None:
        return None

    price_text = str(price).strip()
    if not price_text:
        return None

    currency = candidate.get("priceCurrency") or candidate.get("currency")
    currency_text = str(currency).strip() if currency is not None else None
    return _format_price_amount(price_text, currency_text)


def _find_structured_price(value) -> str | None:
    if isinstance(value, dict):
        direct = _coerce_structured_price(value)
        if direct:
            return direct

        prioritized_keys = (
            "offers",
            "priceSpecification",
            "offersFrom",
            "mainEntity",
            "@graph",
        )
        for key in prioritized_keys:
            if key in value:
                found = _find_structured_price(value[key])
                if found:
                    return found

        for child in value.values():
            found = _find_structured_price(child)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_structured_price(item)
            if found:
                return found
    return None


def _extract_price_from_meta(soup: BeautifulSoup) -> str | None:
    direct_tag_attrs = (
        {"property": "price"},
        {"name": "price"},
        {"property": "booking:price"},
        {"name": "booking:price"},
        {"property": "booking:total_price"},
        {"name": "booking:total_price"},
        {"itemprop": "price"},
    )
    for attrs in direct_tag_attrs:
        content = _extract_meta_content(soup, attrs=attrs)
        if content:
            return content

    amount = None
    for amount_attrs in (
        {"property": "product:price:amount"},
        {"name": "product:price:amount"},
        {"itemprop": "price"},
        {"property": "booking:price:amount"},
        {"name": "booking:price:amount"},
    ):
        amount = _extract_meta_content(soup, attrs=amount_attrs)
        if amount:
            break

    if not amount:
        return None

    currency = None
    for currency_attrs in (
        {"property": "product:price:currency"},
        {"name": "product:price:currency"},
        {"itemprop": "priceCurrency"},
        {"property": "booking:price:currency"},
        {"name": "booking:price:currency"},
    ):
        currency = _extract_meta_content(soup, attrs=currency_attrs)
        if currency:
            break

    return _format_price_amount(amount, currency)


def _extract_trusted_price(soup: BeautifulSoup) -> str | None:
    price = _extract_price_from_jsonld(soup)
    if price:
        return price

    price = _extract_price_from_meta(soup)
    if price:
        return price

    description = _extract_og_content(soup, "og:description")
    return _extract_price(description)


def _parse_og_markup(markup: str) -> OGData | None:
    soup = BeautifulSoup(markup, "html.parser")

    title = _extract_og_content(soup, "og:title")
    if not title:
        return None

    image_url = _extract_og_content(soup, "og:image")
    description = _extract_og_content(soup, "og:description")
    price = _extract_trusted_price(soup)

    return OGData(
        title=title,
        image_url=image_url,
        description=description,
        price=price,
    )


async def fetch_og(url: str) -> OGData | None:
    started = time.perf_counter()
    parsed_url = urlparse(url)
    fetch_host = parsed_url.hostname
    source = "booking" if _is_booking_host((fetch_host or "").lower()) else "airbnb" if _is_airbnb_host((fetch_host or "").lower()) else None
    _last_fetch_meta.update(
        {
            "source": source,
            "fetch_url_host": fetch_host,
            "failure_reason": None,
            "price_found": False,
        }
    )
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_BROWSER_HEADERS) as client:
            response = await client.get(url)
    except httpx.TimeoutException:
        _last_fetch_meta["status"] = "timeout"
        _last_fetch_meta["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
        _last_fetch_meta["failure_reason"] = "timeout"
        return None
    except httpx.HTTPError:
        _last_fetch_meta["status"] = "error"
        _last_fetch_meta["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
        _last_fetch_meta["failure_reason"] = "http_error"
        return None

    if not (200 <= response.status_code < 300):
        _last_fetch_meta["status"] = int(response.status_code)
        _last_fetch_meta["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
        _last_fetch_meta["failure_reason"] = "non_2xx"
        return None

    _last_fetch_meta["status"] = int(response.status_code)
    _last_fetch_meta["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    parsed = _parse_og_markup(response.text)
    if parsed is None:
        _last_fetch_meta["failure_reason"] = "missing_title"
        return None

    _last_fetch_meta["price_found"] = bool(parsed.price)
    if not parsed.price:
        _last_fetch_meta["failure_reason"] = "missing_metadata"
    return parsed


def last_fetch_meta() -> dict[str, str | int | bool | None]:
    return dict(_last_fetch_meta)
