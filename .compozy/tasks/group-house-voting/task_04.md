---
status: completed
title: URL parsing and async OG scraper in `app/scraper.py`
type: backend
complexity: medium
dependencies:
  - task_01
---

# Task 04: URL parsing and async OG scraper in `app/scraper.py`

## Overview
Implement the two scraper primitives — `parse_url(raw)` for source detection and URL normalization, and `fetch_og(url)` for Open Graph metadata extraction — so the house-submission route can validate a pasted URL and render a card. The MVP commits to a single HTTP fetch with browser-like headers and an 8-second read timeout; partial OG data (e.g., title without image) is accepted, network failures surface as `None` for routes to convert into a retryable user error.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
- INVOKE `/web-scraping` before writing scraping code (project rule in AGENTS.md)
</critical>

<requirements>
- MUST expose `parse_url(raw: str) -> ParsedURL | None` where `ParsedURL` is a dataclass with `source` (`"airbnb"` or `"booking"`), `external_id` (stable identifier extracted from the URL path), and `normalized` (canonical URL stripped of tracking params and fragments).
- MUST accept Airbnb URLs whose host matches `airbnb.<tld>` (including `.com.br`, `.com`, `.co.uk`, etc.); the canonical normalized host MUST be locked to one form (recommend `www.airbnb.com`) so regional variants collapse to one row.
- MUST accept Booking URLs whose host matches `booking.com` (including `www.`); the path pattern `/hotel/<cc>/<slug>(.<locale>)?.html` MUST yield `external_id = "<slug>"` with any `.<locale>` suffix stripped (e.g. `villa-inn-economic.pt-br.html` → `villa-inn-economic`).
- MUST return `None` for any other domain, malformed input, or path that lacks an identifiable listing ID.
- MUST strip query strings and fragments before duplicate detection; the normalized form MUST be deterministic for the two example URLs in `fixtures/example-urls.md`.
- MUST expose `async def fetch_og(url: str) -> OGData | None` where `OGData` is a dataclass with `title: str`, `image_url: str | None`, `description: str | None`, `price: str | None`.
- MUST use `httpx.AsyncClient` with `httpx.Timeout(connect=5.0, read=8.0, write=5.0, pool=5.0)` and browser-like headers (`User-Agent` for Chrome on macOS, `Accept`, `Accept-Language`, `Accept-Encoding`).
- MUST treat any non-2xx response, timeout, or network exception as `None`.
- MUST accept partial OG data: `title` is required for success; `image_url`, `description`, `price` may be `None`.
- MUST parse HTML with `BeautifulSoup(markup, "html.parser")` (no `lxml` C extension dependency, per TechSpec).
- MUST NOT retry inside `fetch_og` (PRD: "No retry logic in MVP").
- MUST NOT use a headless browser or third-party scraping service.
</requirements>

## Subtasks
- [x] 4.1 Define `ParsedURL` and `OGData` dataclasses.
- [x] 4.2 Implement `parse_url` covering Airbnb (`/rooms/<id>`) and Booking (`/hotel/<cc>/<slug>(.<locale>)?.html`) using `urllib.parse` plus `match`/pattern dispatch.
- [x] 4.3 Implement URL normalization (lowercase host, strip query/fragment, lock canonical host form per source, strip trailing slash).
- [x] 4.4 Implement `fetch_og` with `httpx.AsyncClient`, browser headers, the documented timeout, and structured error handling that returns `None` on any failure.
- [x] 4.5 Implement OG metadata extraction (`og:title`, `og:image`, `og:description`) plus a best-effort price regex over `og:description` (per TechSpec "Known Risks").
- [x] 4.6 Validate against `fixtures/example-urls.md` — both URLs MUST round-trip through `parse_url` with the expected `external_id` and a deterministic `normalized` form.

## Implementation Details
The two real-world URLs in [`fixtures/example-urls.md`](fixtures/example-urls.md) are the canonical inputs for parser tests; treat them as the contract. Lock the TLD-collapse rule and the Booking `.locale` strip rule explicitly in code comments. For `fetch_og`, follow TechSpec **Integration Points → Airbnb / Booking.com (OG Metadata Fetch)** for header values, timeout, and error handling.

Important guardrails:

- HTML parsing must tolerate badly-formed pages and missing tags — use `soup.find("meta", attrs={"property": "og:title"})` and treat any absent tag as `None`.
- Price extraction is best-effort; if no price is found, return `None` rather than guessing. The card hides the price slot when absent.
- Never expose `httpx.HTTPError` to callers — convert to `None` so routes don't bind to httpx exception types.

### Relevant Files
- `.compozy/tasks/group-house-voting/_techspec.md` — Core Interfaces, Integration Points, Known Risks sections.
- `.compozy/tasks/group-house-voting/_prd.md` — Source allowlist, URL normalization, OG fetch failure UX.
- `fixtures/example-urls.md` — real-world example URLs for unit tests and normalization decisions.
- `.agents/skills/web-scraping/SKILL.md` — project-mandated scraping conventions.
- `app/config.py` (task_01) — exists but not consumed by this module (scraper is config-free).

### Dependent Files
- `app/scraper.py` (new) — the module implemented here.
- `app/routes.py` (task_07) — calls `parse_url` then `fetch_og` from `POST /houses`.
- `tests/test_scraper.py` (new) — unit tests over the parser and OG extractor.
- `tests/fixtures/airbnb_listing.html`, `tests/fixtures/booking_listing.html` (new) — captured HTML snippets for OG extraction tests.

### Related ADRs
- [ADR-005: httpx Async for Open Graph Fetching](adrs/adr-005.md) — pins httpx async, timeout values, and header rationale.

## Deliverables
- `app/scraper.py` implementing `ParsedURL`, `OGData`, `parse_url`, `fetch_og`.
- Captured HTML fixtures committed under `tests/fixtures/` for offline OG parsing tests.
- Documented (in module docstring) the normalization rules locked in for both sources.
- Unit tests with 80%+ coverage **(REQUIRED)**.
- Integration tests covering the `fetch_og` happy path with mocked HTTP **(REQUIRED)**.

## Tests
- Unit tests:
  - [x] `parse_url` on the Airbnb example URL returns `source="airbnb"`, `external_id="32311963"`, and the documented normalized form.
  - [x] `parse_url` on the Booking example URL returns `source="booking"`, `external_id="villa-inn-economic"`, and the documented normalized form (no query string, locale suffix stripped).
  - [x] `parse_url` on a canonical Airbnb URL (no query, no fragment) returns the same `external_id` and `normalized` as the version with tracking params — confirms deduplication.
  - [x] `parse_url` on `https://www.airbnb.com/rooms/32311963#photos` strips the fragment.
  - [x] `parse_url` on a Vrbo or random URL returns `None`.
  - [x] `parse_url` on `https://www.booking.com/hotel/br/villa-inn-economic.html` (no locale suffix) yields the same `external_id` as the `.pt-br.html` variant.
  - [x] OG parser against a fixture containing `og:title` + `og:image` + `og:description` returns a fully-populated `OGData`.
  - [x] OG parser against a fixture with `og:title` only returns `OGData(title=..., image_url=None, description=None, price=None)`.
  - [x] OG parser against a fixture with no OG tags returns `None` (title is required).
- Integration tests:
  - [x] `fetch_og` with a mocked 200 response and a valid OG fixture returns a fully-populated `OGData`.
  - [x] `fetch_og` with a mocked 403 response returns `None`.
  - [x] `fetch_og` with a simulated `httpx.ReadTimeout` returns `None`.
  - [x] `fetch_og` sends the documented `User-Agent` and `Accept-Language` headers (assert via the mocking layer).
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing.
- Test coverage >=80%.
- Both example URLs in `fixtures/example-urls.md` parse to the documented `(source, external_id, normalized)` triples.
- No network calls in CI (all `fetch_og` tests use a mock).
- `fetch_og` never raises to callers — all failure modes flatten to `None`.
- Module docstring documents the locked-in normalization rules so future tasks can extend without breaking dedup.
