# AGENTS.md — Odyssey Project

Skill and implementation rules for all agents operating in this repository.
Skills marked **[global]** are installed in `~/.claude/`; **[local]** in `.claude/skills/`.

---

## Skill Map

| Trigger | Skill | Scope | Invoke with |
|---|---|---|---|
| Web scraping / data extraction / crawling / HTML parsing | `web-scraping` | local | `/web-scraping` |
| Tests / pytest / test coverage / fixtures / mocking | `testing-python` | local | `/testing-python` |
| Frontend / UI / design tokens / styling / new components | `design-md` | global | `/design-md` |
| Any FastHTML usage / MonsterUI / HTMX / Starlette via Python | `context7` | global | `/context7` |

---

## Mandatory Rules

### 1. Web Scraping
**ALWAYS** invoke `/web-scraping` before writing any scraping, crawling, or HTML extraction code.
Do not use `requests` + `BeautifulSoup` ad-hoc without consulting the skill first — the skill enforces the correct tool selection (httpx, playwright, selectolax, etc.) based on the target.

### 2. Python Tests
**ALWAYS** invoke `/testing-python` before writing any `pytest` test, fixture, mock, or coverage configuration.
Do not write tests by guessing patterns — the skill enforces project conventions (async, integration vs unit boundaries, fixture scope).

### 3. Frontend / UI (FastHTML and any HTML output)
**ALWAYS** invoke `/design-md` first to analyse `DESIGN.md` before creating or modifying any UI component, page, or visual element.

Then **adhere to `DESIGN.md`** as the source of truth for:
- Color tokens (never hardcode hex values that exist in `DESIGN.md`)
- Typography scale and font families
- Spacing, border-radius, and shadow tokens
- Button variants, card patterns, and component structure

Treat any deviation from `DESIGN.md` as a bug unless the design system itself must be evolved (in which case update `DESIGN.md` first, then implement).

### 4. FastHTML Implementation
**ALWAYS** invoke `/context7` to retrieve current FastHTML documentation before implementing any FastHTML route, component, or middleware.

FastHTML-specific requirements:
- Retrieve docs for the exact API being used (`ft`, `FastHTML`, `serve`, MonsterUI components, HTMX attributes)
- Do not rely on model knowledge for FastHTML — the framework evolves quickly and context7 provides authoritative, version-accurate docs
- After fetching docs via context7, cross-check the implementation against `DESIGN.md` (rule 3 applies in full)
- HTMX attributes, swap strategies, and SSE patterns must be verified against context7 docs, not assumed

---

## Execution Order for FastHTML UI Work

1. `/context7` — fetch FastHTML / MonsterUI / HTMX docs for the feature being built
2. `/design-md` — sync `DESIGN.md` if new components or patterns are introduced
3. Implement using tokens and patterns from `DESIGN.md`
4. `/testing-python` — write tests for any server-side logic added

---

## Skill Locations

```
.claude/skills/
  testing-python  →  .agents/skills/testing-python/SKILL.md   (local)
  web-scraping    →  .agents/skills/web-scraping/SKILL.md      (local)

~/.claude/  (global, available in all projects)
  design-md
  context7
```
