# Task Memory: task_03.md

Keep only task-local execution context here. Do not duplicate facts that are obvious from the repository, task file, PRD documents, or git history.

## Objective Snapshot
- Implement stateless auth primitives in `app/auth.py` for password hashing, JWT issue/decode, session-cookie access, auth gates, and cookie helpers; validate with unit + integration tests.

## Important Decisions
- `require_user(request)` and `require_admin(request)` return either decoded payload dicts or Starlette `Response` objects so routes can use them directly without framework-specific decorator coupling.
- 401 behavior is a `RedirectResponse` to `/login` with status `307`; 403 behavior is a plain `Response` with status `403`.
- Session-cookie `secure` flag is driven by env (`APP_ENV` or `ENV` equal to `prod`/`production`).

## Learnings
- Running only `tests/test_auth.py` fails repository verification because global coverage gate (`--cov-fail-under=80`) applies to the full suite; full `pytest` run is required for pass/fail evidence.

## Files / Surfaces
- `app/auth.py`
- `tests/test_auth.py`

## Errors / Corrections
- Initial `require_user`/`require_admin` implementation raised `HTTPException`; corrected to return concrete HTTP responses to satisfy task requirement for direct 401 redirect / 403 response behavior.

## Ready for Next Run
- Auth helpers and tests are in place for downstream route tasks (`task_05` onward) to consume directly.
