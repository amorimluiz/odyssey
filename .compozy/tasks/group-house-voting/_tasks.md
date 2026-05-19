# Group House Voting MVP — Task List

## Tasks

| # | Title | Status | Complexity | Dependencies |
|---|-------|--------|------------|--------------|
| 01 | Project scaffold, dependencies, env config | completed | low | — |
| 02 | SQLite schema and `app/db.py` query helpers | completed | medium | task_01 |
| 03 | JWT auth and password hashing in `app/auth.py` | completed | medium | task_01, task_02 |
| 04 | URL parsing and async OG scraper in `app/scraper.py` | completed | medium | task_01 |
| 05 | FastHTML app factory, base layout, shared FT components | completed | medium | task_01, task_02, task_03 |
| 06 | Invite, registration, login, and logout routes | completed | high | task_02, task_03, task_05 |
| 07 | House list and submission routes (HTMX) | completed | high | task_02, task_03, task_04, task_05 |
| 08 | Vote toggle route | completed | low | task_02, task_03, task_05 |
| 09 | Admin panel: invite link, rotate, member list | completed | medium | task_02, task_03, task_05 |
| 10 | UI styling and DESIGN.md token application | pending | medium | task_05, task_06, task_07, task_09 |
