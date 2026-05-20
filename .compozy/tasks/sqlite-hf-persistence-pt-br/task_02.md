---
status: completed
title: Translate auth, navigation, and admin UI to pt-BR
type: frontend
complexity: medium
dependencies: []
---

# Task 02: Translate auth, navigation, and admin UI to pt-BR

## Overview
This task converts the visible authentication, navigation, setup, invite, and admin UI copy to Brazilian Portuguese while preserving the current FastHTML structure. It updates affected tests so the translated flows remain verified without changing auth behavior or admin capabilities.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST translate visible navigation labels for logged-out, member, and admin states.
- MUST translate setup, invite, register, login, logout, and validation copy shown to users.
- MUST translate admin invite, member table, and metadata refresh controls that are part of the admin UI.
- MUST preserve routes, form field names, HTMX attributes, auth logic, and authorization behavior.
- MUST keep internal log event names unchanged unless they are visible to users.
- MUST update affected assertions in auth, admin, app, and styling tests.
</requirements>

## Subtasks
- [x] 02.1 Translate navigation and base layout visible labels.
- [x] 02.2 Translate registration, invite, setup, login, and logout visible copy.
- [x] 02.3 Translate admin invite controls, member table labels, and metadata refresh controls.
- [x] 02.4 Preserve all existing route paths, form names, cookies, and auth redirects.
- [x] 02.5 Update component and route tests that assert auth/admin UI copy.
- [x] 02.6 Search for remaining English strings in the scoped auth/admin UI paths.

## Implementation Details
Modify only user-visible strings in `app/components.py` and `app/routes.py` for the auth/admin scope. Reference TechSpec "API Endpoints" and "Impact Analysis" for the expected translated surfaces; do not introduce a language switcher or UI redesign.

### Relevant Files
- `app/components.py` — contains navigation, invite link fragment, admin panel, and metadata refresh fragment.
- `app/routes.py` — contains register, login, setup, invite, and admin page copy.
- `tests/test_app.py` — asserts navigation and retry copy from shared components.
- `tests/test_routes_auth.py` — asserts setup, invite, register, login, logout, and validation messages.
- `tests/test_routes_admin.py` — asserts admin invite and member table rendering.
- `tests/test_styling.py` — renders auth/admin pages for styling invariants.

### Dependent Files
- `task_03.md` — depends on this task because it continues translation work in shared route/component files.
- `README.md` — later documentation should describe the app as pt-BR after this task lands.

### Related ADRs
- [ADR-001: Automatic Persistence With Brazilian Portuguese UX](adrs/adr-001.md) — Requires pt-BR visible UX without adding admin sync UI in MVP.

## Deliverables
- Auth, setup, invite, navigation, and admin UI visible copy translated to pt-BR.
- Route paths, form fields, auth behavior, and HTMX wiring preserved.
- Tests updated for translated auth/admin expectations.
- Unit tests with 80%+ coverage **(REQUIRED)**.
- Integration tests for auth/admin translated flows **(REQUIRED)**.

## Tests
- Unit tests:
  - [ ] `nav_header()` logged-out state renders Portuguese login navigation and no English `Login`.
  - [ ] `nav_header()` admin state renders Portuguese admin/logout navigation and preserves POST logout form.
  - [ ] `admin_panel()` renders Portuguese invite controls and member table headings.
  - [ ] `metadata_refresh_fragment()` renders Portuguese summary text for scanned, updated, and failed counts.
- Integration tests:
  - [ ] `/setup` renders Portuguese first-admin setup guidance on a fresh database.
  - [ ] `/invite/{token}` renders Portuguese invalid invite feedback for a rotated token.
  - [ ] `/register` renders Portuguese short-password and duplicate-username validation messages.
  - [ ] `/login` renders Portuguese invalid-credentials feedback.
  - [ ] `/admin` renders Portuguese admin controls for an authenticated admin.
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80%
- Auth/admin pages no longer show English UI copy in the scoped visible strings.
- Existing authentication, registration, invite, and admin flows behave unchanged except for translated copy.
