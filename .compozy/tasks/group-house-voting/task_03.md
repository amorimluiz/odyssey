---
status: completed
title: JWT auth and password hashing in `app/auth.py`
type: backend
complexity: medium
dependencies:
  - task_01
  - task_02
---

# Task 03: JWT auth and password hashing in `app/auth.py`

## Overview
Provide the credential primitives every protected route needs: bcrypt password hashing/verification, HS256 JWT issuance and decoding, and a `current_user(request)` helper that reads the `session` cookie and returns the decoded payload or `None`. Per ADR-003, sessions are stateless — `current_user()` MUST NOT touch the DB.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST expose `hash_password(plain) -> str` and `verify_password(plain, hashed) -> bool` using `passlib[bcrypt]`.
- MUST expose `issue_token(user_id: int, role: str) -> str` producing an HS256 JWT signed with `settings.SECRET_KEY`, with `exp` set to now + 30 days (UTC) and `sub` = `user_id` as integer.
- MUST expose `decode_token(token: str) -> dict | None` returning the payload on success or `None` on any failure (invalid signature, expired, malformed).
- MUST expose `current_user(request) -> dict | None` that reads the `session` cookie and delegates to `decode_token`. The function MUST NOT issue any DB query.
- MUST expose a `require_user` and `require_admin` dependency/decorator usable from FastHTML routes — returning a 401 redirect (`/login`) or 403 response respectively when the check fails.
- MUST set cookie attributes via a shared helper: `httponly=True`, `samesite="lax"`, `secure=True` in production (driven by an env flag), `max_age=30 * 86400`, `path="/"`.
- MUST NOT log the raw JWT, raw password, or password hash.
</requirements>

## Subtasks
- [x] 3.1 Implement `hash_password` and `verify_password` using `passlib.context.CryptContext(schemes=["bcrypt"])`.
- [x] 3.2 Implement `issue_token` / `decode_token` using `pyjwt` with HS256 and explicit `exp` claim.
- [x] 3.3 Implement `current_user(request)` reading the `session` cookie and decoding it.
- [x] 3.4 Implement `require_user` and `require_admin` route gates returning the correct status codes (per TechSpec API table).
- [x] 3.5 Implement `set_session_cookie(response, token)` and `clear_session_cookie(response)` helpers so login/logout/register routes do not duplicate cookie attributes.

## Implementation Details
See TechSpec **Core Interfaces** for `app/auth.py` signatures, and **Implementation Design → JWT payload** for the exact claim shape (`sub`, `role`, `exp`). Use `datetime.now(tz=timezone.utc)` for `exp` to avoid naive-datetime warnings under Python 3.12+. PyJWT raises `ExpiredSignatureError`, `InvalidTokenError`; catch broadly and return `None` so route code can treat any failure uniformly.

The `require_user`/`require_admin` shape depends on the FastHTML idiom chosen in task_05; expose them as both a callable (`require_user(request)`) and a Starlette-compatible dependency so either style works.

### Relevant Files
- `.compozy/tasks/group-house-voting/_techspec.md` — Core Interfaces section defines `auth.py` signatures and the JWT payload shape.
- `.compozy/tasks/group-house-voting/adrs/adr-003.md` — explains why a JWT-in-cookie was chosen over FastHTML's built-in session.
- `app/config.py` (task_01) — supplies `SECRET_KEY`.
- `app/db.py` (task_02) — used by callers of `auth.py` to look up users by email; `auth.py` itself stays DB-free.

### Dependent Files
- `app/auth.py` (new) — the module implemented here.
- `app/routes.py` (tasks 06–09) — every protected route consumes `current_user`, `require_user`, `require_admin`.
- `main.py` (task_05) — wires `require_user` into the base layout's auth-aware header.
- `tests/test_auth.py` (new) — unit tests covering the round-trips and failure modes.

### Related ADRs
- [ADR-003: JWT Stored in HttpOnly Cookie](adrs/adr-003.md) — token format, cookie attributes, statelessness.

## Deliverables
- `app/auth.py` implementing all primitives, route gates, and cookie helpers.
- Cookie-attribute helper shared by register / login / logout flows.
- Unit tests with 80%+ coverage **(REQUIRED)**.
- Integration tests verifying the cookie attributes and 401/403 behavior with a stub route **(REQUIRED)**.

## Tests
- Unit tests:
  - [x] `hash_password` then `verify_password` round-trip returns `True` for the original plain text.
  - [x] `verify_password` returns `False` for a different plain text against the same hash.
  - [x] `issue_token` then `decode_token` round-trip returns a dict with `sub`, `role`, `exp`.
  - [x] `decode_token` returns `None` for a token signed with a different key.
  - [x] `decode_token` returns `None` for a token whose `exp` is in the past (freeze time or hand-craft an expired token).
  - [x] `decode_token` returns `None` for malformed input (`"not.a.jwt"`).
  - [x] `current_user(request)` returns `None` when the `session` cookie is absent.
  - [x] `current_user(request)` returns the decoded payload when the cookie holds a valid token.
- Integration tests:
  - [x] A stub route decorated with `require_user` returns 401/redirect when no cookie is set.
  - [x] A stub route decorated with `require_admin` returns 403 when the cookie's `role` is `"member"`.
  - [x] Cookie set via `set_session_cookie` has `HttpOnly`, `SameSite=Lax`, and `Max-Age=2592000`.
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing.
- Test coverage >=80%.
- `current_user` performs zero DB queries (verifiable by passing a `Database` that raises on any call).
- All JWTs verifiable by an external library (e.g., `jwt.io` debugger) using `SECRET_KEY`.
- No raw secrets in logs.
