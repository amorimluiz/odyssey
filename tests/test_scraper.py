from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.scraper import OGData, _parse_og_markup, fetch_og, parse_url


FIXTURE_DIR = Path(__file__).parent / "fixtures"
EXAMPLE_URLS = Path(".compozy/tasks/group-house-voting/fixtures/example-urls.md").read_text(
    encoding="utf-8"
)


def _extract_urls(text: str) -> tuple[str, str]:
    urls = [line.strip() for line in text.splitlines() if line.strip().startswith("https://")]
    assert len(urls) >= 2
    return urls[0], urls[1]


def test_parse_airbnb_example_url_contract() -> None:
    airbnb_url, _ = _extract_urls(EXAMPLE_URLS)

    parsed = parse_url(airbnb_url)

    assert parsed is not None
    assert parsed.source == "airbnb"
    assert parsed.external_id == "32311963"
    assert parsed.normalized == "https://www.airbnb.com/rooms/32311963"


def test_parse_booking_example_url_contract() -> None:
    _, booking_url = _extract_urls(EXAMPLE_URLS)

    parsed = parse_url(booking_url)

    assert parsed is not None
    assert parsed.source == "booking"
    assert parsed.external_id == "villa-inn-economic"
    assert parsed.normalized == "https://www.booking.com/hotel/br/villa-inn-economic.html"


def test_parse_airbnb_deduplicates_tracking_params() -> None:
    canonical = "https://www.airbnb.com/rooms/32311963"
    with_tracking = (
        "https://www.airbnb.com/rooms/32311963"
        "?source_impression_id=abc&check_in=2026-12-30"
    )

    parsed_canonical = parse_url(canonical)
    parsed_tracking = parse_url(with_tracking)

    assert parsed_canonical == parsed_tracking


def test_parse_airbnb_strips_fragment() -> None:
    parsed = parse_url("https://www.airbnb.com/rooms/32311963#photos")

    assert parsed is not None
    assert parsed.external_id == "32311963"
    assert parsed.normalized == "https://www.airbnb.com/rooms/32311963"


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


def test_og_parser_full_data_fixture() -> None:
    markup = (FIXTURE_DIR / "airbnb_listing.html").read_text(encoding="utf-8")

    parsed = _parse_og_markup(markup)

    assert parsed == OGData(
        title="Casa na Praia em Ilha Grande",
        image_url="https://images.example.com/airbnb-house.jpg",
        description="Vista para o mar, 4 quartos. R$ 1.250 por noite",
        price="R$ 1.250 por noite",
    )


def test_og_parser_title_only_fixture() -> None:
    markup = (FIXTURE_DIR / "booking_listing.html").read_text(encoding="utf-8")

    parsed = _parse_og_markup(markup)

    assert parsed == OGData(
        title="Villa Inn Economic",
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


@pytest.mark.asyncio
async def test_fetch_og_non_2xx_returns_none(httpx_mock) -> None:
    httpx_mock.add_response(status_code=403, text="forbidden")

    assert await fetch_og("https://www.booking.com/hotel/br/villa-inn-economic.html") is None


@pytest.mark.asyncio
async def test_fetch_og_timeout_returns_none(httpx_mock) -> None:
    httpx_mock.add_exception(httpx.ReadTimeout("timeout"))

    assert await fetch_og("https://www.booking.com/hotel/br/villa-inn-economic.html") is None


@pytest.mark.asyncio
async def test_fetch_og_sends_expected_headers(httpx_mock) -> None:
    markup = (FIXTURE_DIR / "booking_listing.html").read_text(encoding="utf-8")
    httpx_mock.add_response(status_code=200, text=markup)

    await fetch_og("https://www.booking.com/hotel/br/villa-inn-economic.html")

    request = httpx_mock.get_requests()[0]
    assert "Chrome/124.0.0.0" in request.headers["User-Agent"]
    assert request.headers["Accept-Language"] == "en-US,en;q=0.9"
