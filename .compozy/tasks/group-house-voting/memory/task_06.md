# Task Memory: task_06.md

Keep only task-local execution context here. Do not duplicate facts that are obvious from the repository, task file, PRD documents, or git history.

## Objective Snapshot
- Implement authentication entry routes: `GET /invite/{token}`, `POST /register`, `GET /login`, `POST /login`, `POST /logout` with ADR-001 token-gated registration and ADR-006 role bootstrap.
- Add integration/unit coverage for registration, login, logout, invite token validation, duplicate handling, and generic error behavior.

## Important Decisions
- `/invite/{token}` always renders the same registration shell and returns `403` for invalid tokens while disabling form inputs; no early plain-text rejection path.
- `/register` performs strict server-side token re-validation from DB before any account action, enforces minimum password length `>=8`, lowercases emails, and uses shared cookie helpers for session issuance.
- Login failure path uses one generic message (`Invalid email or password.`) for both unknown email and wrong password to avoid user enumeration.
- Added explicit `db.conn.commit()` in `set_invite_token()` so token rotation/updates persist across separate DB connections used by different requests.

## Learnings
- `sqlite-utils` raw `db.execute(...)` upsert in this project needed explicit commit to guarantee visibility from fresh `get_db()` connections in subsequent requests/tests.

## Files / Surfaces
- `app/routes.py`
- `app/db.py`
- `tests/test_routes_auth.py`
- `.compozy/tasks/group-house-voting/task_06.md` (tracking update)
- `.compozy/tasks/group-house-voting/_tasks.md` (tracking update)

## Errors / Corrections
- Initial invite/registration tests failed because invite token writes were not committed for cross-connection reads; corrected by committing inside `set_invite_token`.
- Initial invalid-invite shape assertion compared full HTML strings including hidden token value; corrected to assert consistent disabled-form shell indicators instead.

## Ready for Next Run
- Task 06 route surface is complete and verified (`72 passed`, coverage `95.81%`).
- Next route tasks can reuse `register_routes(app)` and existing auth form/error layout helpers now present in `app/routes.py`.
