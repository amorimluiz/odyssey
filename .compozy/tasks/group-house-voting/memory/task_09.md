# Task Memory: task_09.md

Keep only task-local execution context here. Do not duplicate facts that are obvious from the repository, task file, PRD documents, or git history.

## Objective Snapshot
- Implement admin-only `GET /admin` and `POST /admin/rotate-invite` with invite link display/copy, rotation, and read-only member list.
- Add test coverage for admin gating, invite URL rendering precedence (`BASE_URL` then request host), rotation behavior, and old-token invalidation.

## Important Decisions
- Token generation for rotation uses `uuid.uuid4().hex` to match invite-token string style already used by invite validation flow.
- Invite absolute URL precedence is fixed to `BASE_URL` from settings when present; fallback is `<request.scheme>://<request.headers['host']>`.
- Unauthenticated admin-route behavior remains project-standard `307` redirect to `/login` via `require_user`/`require_admin` chain.

## Learnings
- `ctx7` CLI is not installed in this environment, so mandatory context7 lookup could not run; implementation followed existing FastHTML project patterns and was validated by tests.
- A misplaced refactor temporarily broke `house_card` return flow; fixed before final verification.

## Files / Surfaces
- `app/config.py`
- `app/db.py`
- `app/components.py`
- `app/routes.py`
- `tests/test_routes_admin.py`

## Errors / Corrections
- Initial component edit accidentally moved part of `house_card` body below `admin_panel`, causing multiple house-route test failures; function body restored and regressions cleared.
- Initial sort assertion for member ordering was brittle because page title contains "Admin"; assertion switched to joined-date order checks.

## Ready for Next Run
- Task implementation and verification complete locally (`pytest -q`, 99 passed, coverage 96.40%).
