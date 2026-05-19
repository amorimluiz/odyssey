---
status: completed
title: Admin panel — invite link, rotate, member list
type: backend
complexity: medium
dependencies:
  - task_02
  - task_03
  - task_05
---

# Task 09: Admin panel — invite link, rotate, member list

## Overview
Implement the admin-only surface defined by the PRD: `GET /admin` shows the active invite link (with copy affordance) plus a read-only member list (name, email, join date), and `POST /admin/rotate-invite` replaces the active token with a freshly-generated UUID so the old invite link stops working immediately. Only users whose JWT carries `role="admin"` may reach these routes.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST implement `GET /admin` (admin-gated) rendering the current invite link (full URL with token), a one-click copy button, the rotate-link button, and a member list (name, email, join date) sorted by `created_at ASC`.
- MUST implement `POST /admin/rotate-invite` (admin-gated) replacing `settings.invite_token` with a fresh UUID and returning the updated invite-link fragment for HTMX swap.
- MUST return 403 when the requester's JWT has `role != "admin"`.
- MUST return 401 (redirect to `/login`) when no `session` cookie is present.
- MUST render the invite link as the full external URL (scheme + host + `/invite/{token}`), reading the base URL from `settings` (e.g., `BASE_URL` env var) or from the request's `Host` header as a fallback.
- MUST NOT expose any per-user action (delete, demote, promote) — those are explicit non-goals in the PRD.
- MUST ensure rotation is atomic at the DB layer (single UPDATE on the `settings` row).
- SHOULD log a structured event when the token rotates (without logging the token value itself).
</requirements>

## Subtasks
- [x] 9.1 Implement `GET /admin` rendering the invite link, member list, and rotate button.
- [x] 9.2 Implement `POST /admin/rotate-invite` using `db.set_invite_token(new_uuid)` and returning the updated link fragment.
- [x] 9.3 Implement the invite-link copy button using a small inline JS snippet (`navigator.clipboard.writeText(...)`) — HTMX cannot do this server-side.
- [x] 9.4 Implement the member list table component.
- [x] 9.5 Confirm role-gating via `require_admin` on both routes.

## Implementation Details
Follow TechSpec **API Endpoints → /admin, /admin/rotate-invite** for paths, methods, and gating. Use `uuid.uuid4().hex` (or `secrets.token_urlsafe`) for tokens; document the choice and keep it consistent between this task and task_06's validation logic.

The "current invite link" rendering needs an absolute URL. Prefer a configured `BASE_URL` env var (read in `app.config`) and fall back to constructing it from `request.url_for(...)` or `request.headers["host"]` when unset. Lock the precedence rule and document it.

For the copy button: avoid pulling in a JS framework; a 6-line inline `<script>` using `navigator.clipboard` is sufficient. The button must still work without JS — fall back to a readable, selectable input element.

### Relevant Files
- `.compozy/tasks/group-house-voting/_techspec.md` — API Endpoints, Implementation Design.
- `.compozy/tasks/group-house-voting/_prd.md` — Admin Panel feature spec.
- `app/auth.py` (task_03) — `require_admin`.
- `app/db.py` (task_02) — `get_invite_token`, `set_invite_token`, `list_users`.
- `app/components.py` (task_05) — `base_layout`, `error_fragment`.

### Dependent Files
- `app/routes.py` (extends task_08) — adds the two admin routes.
- `app/components.py` (extends task_08) — adds `admin_panel` and `invite_link_fragment` components.
- `tests/test_routes_admin.py` (new) — integration tests for the admin surface.

### Related ADRs
- [ADR-001: Shareable Rotatable Invite Link as Group Access Control](adrs/adr-001.md) — token rotation behavior and "old link stops working immediately" requirement.
- [ADR-003: JWT Stored in HttpOnly Cookie](adrs/adr-003.md) — role gating reads `role` from JWT.
- [ADR-006: ADMIN_EMAIL Env Var for Admin Bootstrap](adrs/adr-006.md) — defines who reaches these routes.

## Deliverables
- `GET /admin` and `POST /admin/rotate-invite` registered via `register_routes(app)`.
- Member list table sorted by join date (ascending).
- Invite link rendered as a full external URL with a working copy button.
- Atomic token rotation at the DB layer.
- Structured rotation log line (no token in payload).
- Unit tests with 80%+ coverage **(REQUIRED)**.
- Integration tests covering admin gating, rotation, and old-token invalidation **(REQUIRED)**.

## Tests
- Unit tests:
  - [x] Invite-link rendering uses `BASE_URL` when set; otherwise falls back to `request` host.
  - [x] Rotation log line contains the rotating admin's user_id but NOT the new (or old) token value.
  - [x] Member list rendering sorts by `created_at ASC`.
- Integration tests:
  - [x] Unauthenticated `GET /admin` returns 401 / redirect to `/login`.
  - [x] Member-role `GET /admin` returns 403.
  - [x] Admin-role `GET /admin` returns 200, includes the current invite link and the member list.
  - [x] `POST /admin/rotate-invite` as admin: response contains a new token (different from the previous one), DB `settings.invite_token` is updated, response is the swapped invite-link fragment.
  - [x] After rotation, `GET /invite/<old-token>` returns 403 (the rotation invalidates the prior link).
  - [x] After rotation, `GET /invite/<new-token>` returns 200 and renders the registration form.
  - [x] Member list returns all registered users with no per-user action buttons (no `/admin/users/.../delete` link in markup).
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing.
- Test coverage >=80%.
- Old invite tokens are invalidated immediately after rotation (verified end-to-end).
- Admin gating returns 403 (not 404 or 401) for members — distinct from the unauthenticated case.
- No per-user actions present in the admin UI (PRD non-goal enforced).
- Token values never appear in logs.
