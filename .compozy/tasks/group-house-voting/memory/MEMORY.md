# Workflow Memory

Keep only durable, cross-task context here. Do not duplicate facts that are obvious from the repository, PRD documents, or git history.

## Current State
- Task 01 scaffold completed: project metadata, dependency declarations, base `app/` package, env config helper, pytest wiring, and smoke tests are established.
- Task 04 scraper primitives completed: `app.scraper` now exposes `parse_url` and async `fetch_og` with test coverage and mocked-network integration tests.
- Task 05 app shell completed: `main.py` now exposes `create_app()` and module-level `app`, mounts `/static`, registers `/healthz`, initializes schema on startup, warns for invalid `ADMIN_EMAIL`, and wires route registration through `app.routes.register_routes`.

## Shared Decisions
- `app.config.get_settings()` is the canonical env-loading entrypoint for app modules; it uses `python-dotenv`, requires `SECRET_KEY`, defaults `DB_PATH` to `./app.db`, and treats missing `ADMIN_EMAIL` as `None`.
- Auth route gates in `app.auth` are callable helpers returning either decoded payload (`dict`) or immediate Starlette responses (`307` redirect to `/login` for unauthenticated, `403` for non-admin), so downstream routes should short-circuit on `Response`.
- Session cookie helpers in `app.auth` centralize cookie attributes (`httponly`, `samesite=lax`, `max_age=30d`, `path=/`) and compute `secure=True` only when `APP_ENV`/`ENV` is production-like.
- URL normalization contract is locked for deduplication: Airbnb regional hosts collapse to `www.airbnb.com` and Booking locale suffixes (`.<lang>-<region>`) are stripped from the listing slug before deriving `external_id`.
- FastHTML request observability should use app `before`/`after` hooks instead of Starlette middleware decorators, since `FastHTML` does not expose `@app.middleware`.

## Shared Learnings
- Tests that modify env vars must clear `get_settings()` cache to avoid cross-test pollution.
- In this repository/runtime, `sqlite-utils` `table.insert(...)` returns a table handle rather than row id; callers needing inserted ids should query `SELECT last_insert_rowid()` on the same DB connection.
- In FastHTML `after` hooks, `resp` may be an FT tuple before response conversion; status logging must handle non-`Response` return types.

## Open Risks
- Local environment may not support `venv` creation (`ensurepip` missing); verification may require user-level installs with `--break-system-packages` unless environment tooling changes.

## Handoffs
- Next tasks can assume stable import paths: `app.db`, `app.auth`, `app.scraper`, `app.routes`, and `app.config`.
- Route tasks should only extend `app.routes.register_routes(app)` and consume shared components from `app.components`.
