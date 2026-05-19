# Task Memory: task_04.md

Keep only task-local execution context here. Do not duplicate facts that are obvious from the repository, task file, PRD documents, or git history.

## Objective Snapshot
- Implement `app/scraper.py` with URL parsing/normalization for Airbnb + Booking and async OG fetch with httpx + BeautifulSoup.
- Add offline parser fixtures and unit/integration tests for parser and fetch behavior.

## Important Decisions
- Airbnb normalization is locked to `https://www.airbnb.com/rooms/<id>` regardless of regional TLD input to guarantee deduplication.
- Booking parsing accepts `/hotel/<cc>/<slug>(.<locale>)?.html`; locale suffix is stripped before deriving `external_id` and normalized URL.
- OG parsing requires `og:title`; other fields are optional and failure modes flatten to `None` in `fetch_og`.

## Learnings
- Price extraction regex must preserve backslash escapes in raw string; accidental double-edit via shell replacement can silently break matching.

## Files / Surfaces
- `app/scraper.py`
- `tests/test_scraper.py`
- `tests/fixtures/airbnb_listing.html`
- `tests/fixtures/booking_listing.html`
- `tests/fixtures/no_og_listing.html`

## Errors / Corrections
- Initial price regex variant did not return a value for fixture description; corrected regex and revalidated with full suite.

## Ready for Next Run
- `parse_url` and `fetch_og` are ready for route integration in task_07.
