# Workflow Memory

Keep only durable, cross-task context here. Do not duplicate facts that are obvious from the repository, PRD documents, or git history.

## Current State

## Shared Decisions
- `app.config.Settings` keeps optional Hugging Face fields with defaults so existing `Settings(...)` call sites stay compatible.
- `app.db` write helpers use a safe local sync wrapper that no-ops when `SECRET_KEY` is absent, preserving direct helper usage in non-app test contexts.
- Auth, navigation, invite, and admin shell copy in `app/components.py` and `app/routes.py` is now pt-BR by default, including the shared `error_fragment()` retry hint and the base layout page title.

## Shared Learnings
- Remote SQLite restore/sync logic is isolated in `app/persistence.py`; local writes remain non-blocking because sync failures are swallowed and only logged.

## Open Risks

## Handoffs
