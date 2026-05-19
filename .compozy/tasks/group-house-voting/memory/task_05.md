# Task Memory: task_05.md

Keep only task-local execution context here. Do not duplicate facts that are obvious from the repository, task file, PRD documents, or git history.

## Objective Snapshot
- Implement FastHTML app factory wiring (`main.py`), shared FT components (`app/components.py`), startup schema init + ADMIN_EMAIL warning, health endpoint, logging, static mount, and route-registration contract.

## Important Decisions
- Implemented request logging using FastHTML `before`/`after` hooks (not Starlette `@app.middleware`) because `FastHTML` does not expose `.middleware()`.
- Kept HTMX as CDN in `base_layout` with pinned URL + integrity and an inline comment to preserve this decision for task_10.
- Kept `main.py` decoupled from concrete route handlers by dynamically loading `app.routes.register_routes` via `importlib`.

## Learnings
- FastHTML `after` receives the pre-conversion route return value, which can be an FT tuple; status extraction must handle non-`Response` values (default 200).
- FastHTML `after` functions must make `resp` optional in signature to avoid parameter resolution failing with `Missing required field: resp`.

## Files / Surfaces
- `main.py`
- `app/components.py`
- `app/routes.py`
- `tests/test_app.py`
- `static/` (new directory)
- tracking updates pending in task files

## Errors / Corrections
- Initial middleware implementation with `@app.middleware("http")` failed because `FastHTML` lacks this API.
- Corrected by switching to `before=Beforeware(...)` and `after=...` hooks.

## Ready for Next Run
- Route tasks (06-09) can implement `app.routes.register_routes(app)` without changing factory internals.
