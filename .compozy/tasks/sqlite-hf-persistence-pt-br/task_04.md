---
status: completed
title: Update deployment configuration and documentation
type: docs
complexity: medium
dependencies:
  - task_01
---

# Task 04: Update deployment configuration and documentation

## Overview
This task updates operator-facing configuration and documentation after the persistence implementation exists. It documents the optional Hugging Face Hub variables, local-only fallback, Render-style ephemeral deploy guidance, and Portuguese app behavior while preserving current setup commands.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST update `.env.example` with all required and optional persistence variables from the implemented settings.
- MUST document that missing Hub variables keep the app in local SQLite mode.
- MUST document the deploy expectation for ephemeral platforms such as Render.
- MUST update README setup, environment variable, stack, and how-to-test sections to match the implemented persistence behavior.
- MUST document that tests use mocked Hugging Face Hub calls and require no real token.
- MUST preserve existing local development commands unless implementation changes require an update.
</requirements>

## Subtasks
- [x] 04.1 Add Hugging Face Hub persistence variables to `.env.example`.
- [x] 04.2 Update README stack and environment variable tables.
- [x] 04.3 Add deployment notes for ephemeral filesystems and remote SQLite restore/sync.
- [x] 04.4 Add local-only fallback and testing guidance.
- [x] 04.5 Align README user-facing descriptions with pt-BR app behavior.
- [x] 04.6 Verify documented commands and variables match the implemented settings.

## Implementation Details
Update documentation only after task_01 defines the exact setting names and defaults. Reference TechSpec "Data Models", "Integration Points", and "Development Sequencing" for the configuration names and operational behavior.

### Relevant Files
- `.env.example` — must expose safe placeholders for optional persistence configuration.
- `README.md` — main operator and contributor documentation.
- `pyproject.toml` — dependency list referenced by README stack and install docs.
- `.compozy/tasks/sqlite-hf-persistence-pt-br/_techspec.md` — source of persistence variable names and documented behavior.

### Dependent Files
- `task_05.md` — final verification must check documentation consistency with implementation.
- `app/config.py` — documentation must match actual environment variable names and defaults.
- `app/persistence.py` — documentation must match restore/sync behavior and local fallback.

### Related ADRs
- [ADR-001: Automatic Persistence With Brazilian Portuguese UX](adrs/adr-001.md) — Requires README and `.env.example` updates.
- [ADR-002: Hugging Face Hub Sync Module With Local SQLite Fallback](adrs/adr-002.md) — Requires documenting local fallback and Hub variables.
- [ADR-003: Post-Write WAL Checkpoint File-Set Upload](adrs/adr-003.md) — Requires documenting file-set sync behavior.

## Deliverables
- `.env.example` includes all implemented persistence environment variables with safe example values.
- README documents Hugging Face Hub persistence, local fallback, ephemeral deploy behavior, and test commands.
- README aligns app descriptions with Brazilian Portuguese UI.
- Documentation is consistent with code-level setting names and defaults.
- Unit tests with 80%+ coverage **(REQUIRED)**.
- Integration or documentation consistency checks for config/documentation behavior **(REQUIRED)**.

## Tests
- Unit tests:
  - [x] Existing config tests confirm documented default values match `app.config`.
  - [x] Existing scaffold/config tests remain passing after new env vars are introduced.
- Integration tests:
  - [x] Full test suite can run without `HF_TOKEN` or `HF_REPO_ID`.
  - [x] Documented `pytest` command remains valid.
  - [x] Documentation references implemented variable names exactly.
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80%
- `.env.example` gives deploy operators the variables needed for remote persistence.
- README explains how to run locally, deploy with remote persistence, and test without real Hub credentials.
- Documentation does not claim an admin sync UI exists in the MVP.
