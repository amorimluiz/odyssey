---
status: completed
title: Invite, registration, login, and logout routes
type: backend
complexity: high
dependencies:
  - task_02
  - task_03
  - task_05
---

# Task 06: Invite, registration, login, and logout routes

## Overview
Implement the four routes that move a user from "received an invite link" to "signed in to the shared list": `GET /invite/{token}`, `POST /register`, `GET /login`, `POST /login`, `POST /logout`. Per ADR-001, the invite token in the URL is the credential for registration; per ADR-006, the admin role is granted at registration time based on `ADMIN_EMAIL` (with first-registrant fallback). After registration or login, the user receives a `session` cookie and lands on `/`.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
- INVOKE `/context7` for FastHTML route patterns before implementation
</critical>

<requirements>
- MUST implement `GET /invite/{token}` rendering a registration form (name, email, password); MUST return 403 when the token does not match `settings.invite_token`.
- MUST implement `POST /register` accepting `name`, `email`, `password`, and the `token` (as a hidden form field) and: (1) re-validating the token server-side, (2) lowercasing and uniqueness-checking the email, (3) hashing the password via `auth.hash_password`, (4) inserting the user, (5) assigning `role` per ADR-006, (6) issuing a JWT and setting the `session` cookie, (7) redirecting to `/`.
- MUST implement `GET /login` rendering the login form (email + password).
- MUST implement `POST /login` verifying the password and, on success, issuing a JWT and redirecting to `/`. On failure, MUST render the form again with an inline error (no detail about whether the email existed).
- MUST implement `POST /logout` clearing the `session` cookie and redirecting to `/login`.
- MUST validate token strictly server-side (per PRD "backend-only validation").
- MUST NOT leak whether a given token has ever existed (constant-time response shape on `/invite/{bad-token}` and `/register` with a bad token).
- MUST NOT reveal whether an email exists on failed login (return the same generic error for both wrong-email and wrong-password).
- MUST reject registration when the password is shorter than a documented minimum (e.g., 8 chars).
- SHOULD render forms with the `error_fragment` component for consistent UI.
</requirements>

## Subtasks
- [x] 6.1 Implement `GET /invite/{token}` with server-side token validation.
- [x] 6.2 Implement `POST /register` including email lowercasing, password length check, admin-role bootstrap per ADR-006, and JWT issuance.
- [x] 6.3 Implement `GET /login` and `POST /login` with generic error messaging.
- [x] 6.4 Implement `POST /logout` clearing the cookie.
- [x] 6.5 Wire all four routes via `register_routes(app)` so `main.py` picks them up automatically.

## Implementation Details
Follow TechSpec **API Endpoints** table for paths, methods, and auth requirements. Use the cookie helpers from task_03 (`set_session_cookie`, `clear_session_cookie`) — do not re-implement cookie attributes here. Use the form-builder primitives from FastHTML / MonsterUI (`Form`, `Input`, `Button`) and wrap inline error rendering in `error_fragment` from task_05.

Admin role assignment logic per ADR-006:

- If `settings.ADMIN_EMAIL` is set and matches the registering email (case-insensitive), set `role="admin"`.
- Else, if `users` table is empty before this insert, set `role="admin"` (fallback).
- Otherwise, set `role="member"`.

Constant-time response for `/invite/{token}`: regardless of validity, render the same HTML shell; only the form's `disabled` state differs. Avoid leaking timing via early returns before any HTML is generated.

### Relevant Files
- `.compozy/tasks/group-house-voting/_techspec.md` — API Endpoints and Implementation Design sections.
- `.compozy/tasks/group-house-voting/_prd.md` — Invitation and Account Creation feature spec, error states.
- `app/auth.py` (task_03) — `hash_password`, `verify_password`, `issue_token`, cookie helpers.
- `app/db.py` (task_02) — user insert / lookup, invite token getter.
- `app/components.py` (task_05) — `base_layout`, `error_fragment`.
- `app/config.py` (task_01) — `ADMIN_EMAIL`.

### Dependent Files
- `app/routes.py` (new — first time it gets concrete content) — these four routes register into `app`.
- `main.py` (task_05) — calls `register_routes(app)` so this task's routes are mounted.
- `tests/test_routes_auth.py` (new) — integration tests for the flows.

### Related ADRs
- [ADR-001: Shareable Rotatable Invite Link as Group Access Control](adrs/adr-001.md) — token-as-credential model.
- [ADR-003: JWT Stored in HttpOnly Cookie](adrs/adr-003.md) — cookie semantics.
- [ADR-006: ADMIN_EMAIL Env Var for Admin Bootstrap](adrs/adr-006.md) — admin role assignment logic.

## Deliverables
- Five route handlers registered via `register_routes(app)`.
- Generic-error login UX that does not distinguish email-not-found vs. wrong-password.
- Admin role assignment per ADR-006 with documented fallback.
- Constant-time response surface for `/invite/{token}`.
- Unit tests with 80%+ coverage **(REQUIRED)**.
- Integration tests for the full registration + login + logout flow **(REQUIRED)**.

## Tests
- Unit tests:
  - [x] Email is lowercased before insert.
  - [x] Registration with a password shorter than 8 chars renders the form with an error and does not insert a user.
  - [x] When `ADMIN_EMAIL="alice@x.com"` and Alice registers, her `role` is `"admin"`.
  - [x] When `ADMIN_EMAIL` is unset and the `users` table is empty, the first registrant's `role` is `"admin"`.
  - [x] When `ADMIN_EMAIL` is unset and the `users` table is non-empty, the next registrant's `role` is `"member"`.
  - [x] Login with a wrong password returns the same error fragment as login with a non-existent email.
- Integration tests:
  - [x] `GET /invite/<valid>` returns 200 and renders the form.
  - [x] `GET /invite/<bad>` returns 403 with no signal about whether the token ever existed.
  - [x] `POST /register` with valid token + body creates a user, sets the `session` cookie, and redirects to `/`.
  - [x] `POST /register` with a token that was just rotated returns 403.
  - [x] `POST /register` with a duplicate email returns the form with an inline error and does not create a second row.
  - [x] `POST /login` with valid creds returns the `session` cookie and redirects to `/`.
  - [x] `POST /login` with wrong creds returns the form (no cookie set) and an error fragment.
  - [x] `POST /logout` clears the cookie (verify `Set-Cookie` with `Max-Age=0`) and redirects to `/login`.
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing.
- Test coverage >=80%.
- Server-side token validation present on every entry point (no client-trust paths).
- Admin assignment follows ADR-006 in all three documented branches.
- No timing-side-channel between valid and invalid invite tokens visible in the response shape.
- Logout reliably clears the cookie (`Max-Age=0`).
