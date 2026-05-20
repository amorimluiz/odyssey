from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

from app.scraper import (
    OGData,
    AirbnbScraper,
    BookingScraper,
    _parse_og_markup,
    fetch_og,
    last_fetch_meta,
    parse_url,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures"
EXAMPLE_AIRBNB_URL = "https://www.airbnb.com/rooms/32311963"
EXAMPLE_BOOKING_URL = (
    "https://www.booking.com/hotel/br/villa-inn-economic.html"
    "?checkin=2026-12-30&checkout=2027-01-03&group_adults=11&group_children=0"
    "&highlighted_blocks=691479801_285025048_5_1_0%2C691479801_285025048_3_1_0%2C691479801_285025048_3_1_0"
    "&matching_block_id=691479801_285025048_5_1_0&no_rooms=5&room1=A%2CA&room2=A%2CA&room3=A%2CA"
    "&room4=A%2CA&room5=A%2CA%2CA&sb_price_type=total&type=total"
)
EXAMPLE_URLS = f"{EXAMPLE_AIRBNB_URL}\n{EXAMPLE_BOOKING_URL}"


def _extract_urls(text: str) -> tuple[str, str]:
    urls = [line.strip() for line in text.splitlines() if line.strip().startswith("https://")]
    assert len(urls) >= 2
    return urls[0], urls[1]


def _read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parse_airbnb_example_url_contract() -> None:
    airbnb_url, _ = _extract_urls(EXAMPLE_URLS)

    parsed = parse_url(airbnb_url)

    assert parsed is not None
    assert parsed.source == "airbnb"
    assert parsed.external_id == "32311963"
    assert parsed.normalized == "https://www.airbnb.com/rooms/32311963"
    assert parsed.fetch_url == "https://www.airbnb.com/rooms/32311963"


def test_parse_booking_example_url_contract() -> None:
    _, booking_url = _extract_urls(EXAMPLE_URLS)

    parsed = parse_url(booking_url)

    assert parsed is not None
    assert parsed.source == "booking"
    assert parsed.external_id == "villa-inn-economic"
    assert parsed.normalized == "https://www.booking.com/hotel/br/villa-inn-economic.html"
    assert parsed.fetch_url == (
        "https://www.booking.com/hotel/br/villa-inn-economic.html"
        "?checkin=2026-12-30&checkout=2027-01-03&group_adults=11&group_children=0"
        "&highlighted_blocks=691479801_285025048_5_1_0%2C691479801_285025048_3_1_0%2C691479801_285025048_3_1_0"
        "&matching_block_id=691479801_285025048_5_1_0&no_rooms=5&room1=A%2CA&room2=A%2CA&room3=A%2CA"
        "&room4=A%2CA&room5=A%2CA%2CA&sb_price_type=total&type=total"
    )


def test_parse_airbnb_deduplicates_tracking_params() -> None:
    canonical = "https://www.airbnb.com/rooms/32311963"
    with_tracking = (
        "https://www.airbnb.com/rooms/32311963"
        "?source_impression_id=abc&check_in=2026-12-30"
    )

    parsed_canonical = parse_url(canonical)
    parsed_tracking = parse_url(with_tracking)

    assert parsed_canonical == parsed_tracking


def test_parse_booking_preserves_allowlisted_query_params_for_fetch_url() -> None:
    parsed = parse_url(
        "https://www.booking.com/hotel/br/villa-inn-economic.html"
        "?checkin=2026-08-01&checkout=2026-08-03&group_adults=2&no_rooms=1&selected_currency=BRL"
        "&utm_source=newsletter"
    )

    assert parsed is not None
    assert parsed.normalized == "https://www.booking.com/hotel/br/villa-inn-economic.html"
    assert (
        parsed.fetch_url
        == "https://www.booking.com/hotel/br/villa-inn-economic.html"
        "?checkin=2026-08-01&checkout=2026-08-03&group_adults=2&no_rooms=1&selected_currency=BRL"
    )


def test_parse_booking_strips_unsupported_tracking_params_from_fetch_url() -> None:
    parsed = parse_url(
        "https://www.booking.com/hotel/br/villa-inn-economic.html"
        "?utm_source=ad&affiliate_id=123&checkin=2026-08-01"
    )

    assert parsed is not None
    assert parsed.fetch_url == "https://www.booking.com/hotel/br/villa-inn-economic.html?checkin=2026-08-01"


def test_parse_airbnb_strips_fragment() -> None:
    parsed = parse_url("https://www.airbnb.com/rooms/32311963#photos")

    assert parsed is not None
    assert parsed.external_id == "32311963"
    assert parsed.normalized == "https://www.airbnb.com/rooms/32311963"
    assert parsed.fetch_url == "https://www.airbnb.com/rooms/32311963"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.vrbo.com/123456",
        "https://example.com/hotel/br/villa-inn-economic.html",
        "not-a-url",
        "",
    ],
)
def test_parse_url_rejects_unsupported_or_malformed_inputs(url: str) -> None:
    assert parse_url(url) is None


def test_parse_booking_locale_and_plain_slug_same_external_id() -> None:
    localized = "https://www.booking.com/hotel/br/villa-inn-economic.pt-br.html"
    plain = "https://www.booking.com/hotel/br/villa-inn-economic.html"

    parsed_localized = parse_url(localized)
    parsed_plain = parse_url(plain)

    assert parsed_localized is not None
    assert parsed_plain is not None
    assert parsed_localized.external_id == "villa-inn-economic"
    assert parsed_plain.external_id == "villa-inn-economic"
    assert parsed_localized.normalized == parsed_plain.normalized


def test_parse_accepts_airbnb_regional_tld() -> None:
    parsed = parse_url("https://www.airbnb.com.br/rooms/32311963")

    assert parsed is not None
    assert parsed.normalized == "https://www.airbnb.com/rooms/32311963"


def test_airbnb_enrich_from_html_matches_fixture() -> None:
    markup = _read_fixture("airbnb_html_price.html")
    soup = BeautifulSoup(markup, "html.parser")

    assert AirbnbScraper().enrich_from_html(soup) == "R$ 450"


def test_airbnb_enrich_from_html_returns_none_without_match() -> None:
    soup = BeautifulSoup("<html><body><span class='other'>R$ 450</span></body></html>", "html.parser")

    assert AirbnbScraper().enrich_from_html(soup) is None


def test_booking_enrich_from_html_matches_fixture() -> None:
    markup = _read_fixture("booking_html_price.html")
    soup = BeautifulSoup(markup, "html.parser")

    assert BookingScraper().enrich_from_html(soup) == "R$ 900"


def test_booking_enrich_from_html_returns_none_without_match() -> None:
    soup = BeautifulSoup("<html><body><span class='other'>R$ 900</span></body></html>", "html.parser")

    assert BookingScraper().enrich_from_html(soup) is None


@pytest.mark.parametrize(
    "selectors",
    [
        AirbnbScraper._PRICE_SELECTORS,
        BookingScraper._PRICE_SELECTORS,
    ],
)
def test_price_selector_depth_invariant(selectors: list[str]) -> None:
    for selector in selectors:
        combinator_count = sum(selector.count(char) for char in (">", "+", "~", " "))
        assert combinator_count <= 3


def test_og_parser_full_data_fixture() -> None:
    markup = (FIXTURE_DIR / "airbnb_listing.html").read_text(encoding="utf-8")

    parsed = _parse_og_markup(markup)

    assert parsed == OGData(
        title="Casa na Praia em Ilha Grande",
        image_url="https://images.example.com/airbnb-house.jpg",
        description="Vista para o mar, 4 quartos. R$ 1.250 por noite",
        price="R$ 1.250 por noite",
    )


def test_og_parser_jsonld_price_fixture() -> None:
    markup = (FIXTURE_DIR / "booking_jsonld_price.html").read_text(encoding="utf-8")

    parsed = _parse_og_markup(markup)

    assert parsed == OGData(
        title="Villa Inn Economic",
        image_url=None,
        description=None,
        price="R$ 1.250",
    )


def test_og_parser_meta_price_fixture() -> None:
    markup = (FIXTURE_DIR / "booking_meta_price.html").read_text(encoding="utf-8")

    parsed = _parse_og_markup(markup)

    assert parsed == OGData(
        title="Villa Inn Economic",
        image_url=None,
        description=None,
        price="R$ 1.250",
    )


def test_og_parser_og_description_fixture() -> None:
    markup = (FIXTURE_DIR / "booking_listing.html").read_text(encoding="utf-8")

    parsed = _parse_og_markup(markup)

    assert parsed == OGData(
        title="Villa Inn Economic",
        image_url=None,
        description=None,
        price=None,
    )


def test_og_parser_airbnb_html_fallback_fixture() -> None:
    body = _read_fixture("airbnb_html_price.html")
    markup = f"""
    <html>
      <head>
        <meta property="og:title" content="Airbnb Fallback Listing" />
        <meta property="og:description" content="Simple listing without trusted price" />
      </head>
      <body>{body}</body>
    </html>
    """

    parsed = _parse_og_markup(markup, source="airbnb")

    assert parsed == OGData(
        title="Airbnb Fallback Listing",
        image_url=None,
        description="Simple listing without trusted price",
        price="R$ 450",
    )


def test_og_parser_booking_html_fallback_fixture() -> None:
    body = _read_fixture("booking_html_price.html")
    markup = f"""
    <html>
      <head>
        <meta property="og:title" content="Booking Fallback Listing" />
        <meta property="og:description" content="Simple listing without trusted price" />
      </head>
      <body>{body}</body>
    </html>
    """

    parsed = _parse_og_markup(markup, source="booking")

    assert parsed == OGData(
        title="Booking Fallback Listing",
        image_url=None,
        description="Simple listing without trusted price",
        price="R$ 900",
    )


def test_og_parser_with_none_source_skips_html_fallback() -> None:
    body = _read_fixture("booking_html_price.html")
    markup = f"""
    <html>
      <head>
        <meta property="og:title" content="Fallback Skipped Listing" />
        <meta property="og:description" content="Simple listing without trusted price" />
      </head>
      <body>{body}</body>
    </html>
    """

    parsed = _parse_og_markup(markup, source=None)

    assert parsed == OGData(
        title="Fallback Skipped Listing",
        image_url=None,
        description="Simple listing without trusted price",
        price=None,
    )


def test_og_parser_visible_body_price_is_ignored() -> None:
    markup = (FIXTURE_DIR / "booking_visible_price_only.html").read_text(encoding="utf-8")

    parsed = _parse_og_markup(markup)

    assert parsed == OGData(
        title="Visible Price Only",
        image_url=None,
        description=None,
        price=None,
    )


def test_og_parser_without_og_title_returns_none() -> None:
    markup = (FIXTURE_DIR / "no_og_listing.html").read_text(encoding="utf-8")

    assert _parse_og_markup(markup) is None


@pytest.mark.asyncio
async def test_fetch_og_success_with_mocked_http_response(
    httpx_mock,
) -> None:
    markup = (FIXTURE_DIR / "airbnb_listing.html").read_text(encoding="utf-8")
    httpx_mock.add_response(status_code=200, text=markup)

    parsed = await fetch_og("https://www.airbnb.com/rooms/32311963")

    assert parsed == OGData(
        title="Casa na Praia em Ilha Grande",
        image_url="https://images.example.com/airbnb-house.jpg",
        description="Vista para o mar, 4 quartos. R$ 1.250 por noite",
        price="R$ 1.250 por noite",
    )
    meta = last_fetch_meta()
    assert meta["status"] == 200
    assert meta["price_found"] is True
    assert meta["failure_reason"] is None
    assert meta["fetch_url_host"] == "www.airbnb.com"


@pytest.mark.asyncio
async def test_fetch_og_non_2xx_returns_none(httpx_mock) -> None:
    httpx_mock.add_response(status_code=403, text="forbidden")

    assert await fetch_og("https://www.booking.com/hotel/br/villa-inn-economic.html") is None
    meta = last_fetch_meta()
    assert meta["status"] == 403
    assert meta["failure_reason"] == "non_2xx"
    assert meta["source"] == "booking"


@pytest.mark.asyncio
async def test_fetch_og_success_without_price_records_missing_metadata(httpx_mock) -> None:
    markup = (FIXTURE_DIR / "booking_listing.html").read_text(encoding="utf-8")
    httpx_mock.add_response(status_code=200, text=markup)

    parsed = await fetch_og("https://www.booking.com/hotel/br/villa-inn-economic.html")

    assert parsed == OGData(
        title="Villa Inn Economic",
        image_url=None,
        description=None,
        price=None,
    )
    meta = last_fetch_meta()
    assert meta["status"] == 200
    assert meta["price_found"] is False
    assert meta["failure_reason"] == "missing_metadata"
    assert meta["source"] == "booking"


@pytest.mark.asyncio
async def test_fetch_og_timeout_returns_none(httpx_mock) -> None:
    httpx_mock.add_exception(httpx.ReadTimeout("timeout"))

    assert await fetch_og("https://www.booking.com/hotel/br/villa-inn-economic.html") is None
    meta = last_fetch_meta()
    assert meta["failure_reason"] == "timeout"
    assert meta["price_found"] is False


@pytest.mark.asyncio
async def test_fetch_og_sends_expected_headers(httpx_mock) -> None:
    markup = (FIXTURE_DIR / "booking_listing.html").read_text(encoding="utf-8")
    httpx_mock.add_response(status_code=200, text=markup)

    await fetch_og("https://www.booking.com/hotel/br/villa-inn-economic.html")

    request = httpx_mock.get_requests()[0]
    assert "Chrome/124.0.0.0" in request.headers["User-Agent"]
    assert request.headers["Accept-Language"] == "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
