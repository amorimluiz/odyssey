---
status: completed
title: FastHTML app factory, base layout, shared FT components
type: backend
complexity: medium
dependencies:
  - task_01
  - task_02
  - task_03
---

# Task 05: FastHTML app factory, base layout, shared FT components

## Overview
Wire the FastHTML application together: a `main.py` app factory, startup hook that calls `init_schema`, a base HTML layout (header, content slot, htmx script), and the small library of shared FT components every route reuses (auth-aware nav, error fragments, layout shell). This is the convergence point all route tasks depend on; after this task, the app boots, serves `/healthz`, and renders the layout even without any business routes.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
- INVOKE `/context7` before writing FastHTML code (project rule in AGENTS.md)
</critical>

<requirements>
- MUST expose `create_app() -> FastHTML` in `main.py` returning a configured `FastHTML` application.
- MUST register a startup hook that opens the DB via `app.db.get_db()` and calls `app.db.init_schema()` exactly once.
- MUST mount a `static/` directory (created here, populated by task_10).
- MUST provide a `base_layout(*content, request=None, title=None)` FT helper returning the full HTML shell (`<html><head><body>`) with the HTMX script tag included.
- MUST provide a `nav_header(request)` FT component that renders different links for unauthenticated, member, and admin users based on `current_user(request)`.
- MUST provide an `error_fragment(message, retryable=False)` FT component used by route tasks for 422/502 inline errors.
- MUST expose a `GET /healthz` route returning HTTP 200 with body `"ok"` for liveness checks.
- MUST log each request at INFO with method, path, `user_id` (or `anon`), status, and latency in ms (per TechSpec **Monitoring and Observability**).
- MUST warn at startup when `ADMIN_EMAIL` is set but contains no `@` (per ADR-006).
- MUST configure cookie / session settings consistent with the helpers from task_03 (no duplication).
- MUST NOT import anything from `app/routes.py` to keep the import graph acyclic — routes register themselves on the returned app via a `register_routes(app)` function exposed by `app/routes.py`.
</requirements>

## Subtasks
- [x] 5.1 Implement `create_app()` with startup hook, static mount, and request logging middleware.
- [x] 5.2 Implement `base_layout`, `nav_header`, and `error_fragment` FT components.
- [x] 5.3 Implement the `ADMIN_EMAIL` validation warning at startup.
- [x] 5.4 Implement `GET /healthz` and verify it boots end-to-end via `TestClient`.
- [x] 5.5 Expose `app = create_app()` at module scope so `uvicorn main:app` works.
- [x] 5.6 Document the `register_routes(app)` contract that tasks 06–09 will implement.

## Implementation Details
Follow TechSpec **System Architecture → Component Overview** for the module layout and **Development Sequencing → Build Order** for why `main.py` lands last in the dependency chain. The base layout must include the HTMX script via CDN (or vendored in `static/`); pick one and lock it in a comment so task_10's CSS strategy can plan accordingly.

The `nav_header` component drives the auth-aware UX: when logged out it shows "Login"; when a member is signed in it shows "Logout"; when the admin is signed in it adds an "Admin" link. This is the only UI surface in this task — everything else is layout primitives.

Keep `main.py` lean: factory, hook, middleware, healthz. Move components into `app/components.py` so route modules can import them without circular imports.

### Relevant Files
- `.compozy/tasks/group-house-voting/_techspec.md` — System Architecture, Monitoring and Observability sections.
- `.compozy/tasks/group-house-voting/adrs/adr-003.md` — cookie config for the session.
- `.compozy/tasks/group-house-voting/adrs/adr-006.md` — `ADMIN_EMAIL` startup warning rules.
- `app/config.py` (task_01) — supplies `DB_PATH`, `SECRET_KEY`, `ADMIN_EMAIL`.
- `app/db.py` (task_02) — `init_schema`, `get_db`.
- `app/auth.py` (task_03) — `current_user` consumed by `nav_header`.
- `DESIGN.md` — informs the structure of base layout markup (task_10 styles it).

### Dependent Files
- `main.py` (new) — app factory, startup wiring.
- `app/components.py` (new) — shared FT components (`base_layout`, `nav_header`, `error_fragment`).
- `app/routes.py` (tasks 06–09) — implements `register_routes(app)` consumed by the factory.
- `static/` (empty dir created here; populated by task_10).
- `tests/test_app.py` (new) — boot smoke tests.

### Related ADRs
- [ADR-003: JWT Stored in HttpOnly Cookie](adrs/adr-003.md) — session cookie attributes.
- [ADR-004: SQLite-Utils as the Database Layer](adrs/adr-004.md) — startup hook calls `init_schema`.
- [ADR-006: ADMIN_EMAIL Env Var for Admin Bootstrap](adrs/adr-006.md) — startup warning logic.

## Deliverables
- `main.py` exposing `app = create_app()`.
- `app/components.py` with `base_layout`, `nav_header`, `error_fragment`.
- `register_routes(app)` contract defined as a docstring or `Protocol` in `app/routes.py` placeholder.
- `GET /healthz` route returning 200.
- Request logging middleware emitting structured INFO logs.
- Unit tests with 80%+ coverage **(REQUIRED)**.
- Integration tests booting the app via FastHTML/Starlette `TestClient` **(REQUIRED)**.

## Tests
- Unit tests:
  - [x] `base_layout("hello", title="Houses")` renders `<title>Houses</title>` and contains the HTMX script tag.
  - [x] `nav_header(request)` returns the logged-out variant when no `session` cookie is set.
  - [x] `nav_header(request)` returns the admin variant when the decoded payload has `role="admin"`.
  - [x] `error_fragment("nope", retryable=True)` renders the retry affordance.
  - [x] Startup hook calls `init_schema` exactly once against a `:memory:` DB.
  - [x] When `ADMIN_EMAIL="not-an-email"` is set, a `WARNING` log line is emitted at startup.
- Integration tests:
  - [x] `TestClient(app).get("/healthz")` returns 200 with body `"ok"`.
  - [x] `TestClient(app).get("/")` renders the base layout and `nav_header` even when no business route is mounted.
  - [x] Two consecutive boots against the same DB file do not raise (idempotent startup).
  - [x] A request logs an INFO line containing method, path, status, and latency.
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing.
- Test coverage >=80%.
- `uvicorn main:app` boots without error against a fresh DB file.
- `register_routes(app)` contract is the only coupling between `main.py` and route modules (no direct imports of route handlers in `main.py`).
- Startup logs include the `ADMIN_EMAIL` warning when misconfigured.
- Base layout renders identical structure for both authenticated and unauthenticated users (only nav differs).
