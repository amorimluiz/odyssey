# Group House Voting

A lightweight web app for groups to collaboratively shortlist and vote on Airbnb and Booking.com rentals — built for our Réveillon house search.

Paste a listing URL, the app scrapes the title, photo, and price automatically, and everyone votes on their favourites. The house with the most votes rises to the top.

The visible app UI and user-facing error copy are in Brazilian Portuguese.

---

## Features

- **Bootstrap setup + invite-only registration** - the first user creates the initial admin at `/setup`; after that, admin generates a single-use invite link and anyone with it can create an account
- **Airbnb & Booking.com scraping** - Open Graph metadata (title, image, description, price) fetched on submission; URLs are normalised and deduplicated
- **Toggle voting** - one click to cast or retract a vote per listing
- **Ranked list** - houses sorted live by vote count
- **Admin panel** - rotate the invite link, view the member list
- **Health check** - `GET /healthz` for uptime monitoring

---

## Stack

| Layer | Technology |
|---|---|
| Web framework | [FastHTML](https://fastht.ml) + [Starlette](https://www.starlette.io) |
| Database | SQLite via [sqlite-utils](https://sqlite-utils.datasette.io) |
| Remote persistence | [huggingface_hub](https://huggingface.co/docs/huggingface_hub) |
| Scraping | [httpx](https://www.python-httpx.org) + [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) |
| Auth | JWT (PyJWT) + bcrypt (passlib) |
| Server | [Uvicorn](https://www.uvicorn.org) |
| Testing | pytest + pytest-asyncio + pytest-cov + pytest-httpx |
| Python | 3.12+ |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | **Yes** | — | Secret used to sign JWTs. Use at least 32 random bytes. |
| `DB_PATH` | No | `./app.db` | Path to the SQLite database file. |
| `ADMIN_EMAIL` | No | — | Email that receives the `admin` role on first registration. |
| `BASE_URL` | No | — | Public base URL used to build invite links (e.g. `https://myapp.example.com`). Falls back to the request host when omitted. |
| `HF_TOKEN` | No | — | Hugging Face token used to restore and sync the SQLite file set. Leave empty for local-only mode. |
| `HF_REPO_ID` | No | — | Hugging Face repository id such as `owner/repo`. Leave empty for local-only mode. |
| `HF_REPO_TYPE` | No | `dataset` | Hugging Face repo type for the remote SQLite file set. |
| `HF_DB_PATH_IN_REPO` | No | `app.db` | Path of the SQLite file inside the Hub repository. |
| `HF_SYNC_ENABLED` | No | `true` | Enables remote restore/sync when the other Hugging Face settings are present. |

Generate a safe `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Setup & Commands

### Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
```

### Run the development server

```bash
uvicorn main:app --reload
```

The app will be available at `http://localhost:8000`.

### Deploy Notes

The app keeps working in local SQLite mode when `HF_TOKEN` or `HF_REPO_ID` are missing.

For ephemeral platforms such as Render, configure the Hugging Face settings so the SQLite file set can be restored on startup and synced after writes:

```bash
HF_TOKEN=...
HF_REPO_ID=owner/repo
HF_REPO_TYPE=dataset
HF_DB_PATH_IN_REPO=app.db
HF_SYNC_ENABLED=true
```

The remote repository stores the main database file plus the WAL companions when present. If the filesystem is wiped between deploys, the app restores from Hugging Face Hub before schema initialization.

### Run tests

```bash
pytest
```

Coverage is enforced at 80%. The test suite mocks Hugging Face Hub calls, so it does not require a real token.

To see the HTML report:

```bash
pytest --cov-report=html
open htmlcov/index.html
```

---

## How to Use

1. Start the server and open `http://localhost:8000`.
2. On a fresh database, open `/setup` to create the first admin account.
3. After logging in as admin, go to `/admin` to copy the invite link and share it with your group.
4. Everyone else registers via the invite link and lands on the voting page.
5. Paste any Airbnb (`airbnb.com/rooms/<id>`) or Booking.com (`booking.com/hotel/...`) URL into the form.
6. Click the vote button on any listing to cast or retract your vote.
7. The visible interface, validation messages, and recovery hints are in Brazilian Portuguese.
8. The house with the most votes floats to the top - that's your pick.

---

## Project Structure

```
.
├── app/
│   ├── auth.py         # JWT issuance, session cookies, password hashing
│   ├── components.py   # FastHTML UI components
│   ├── config.py       # Environment-backed settings
│   ├── db.py           # SQLite schema and query helpers
│   ├── persistence.py  # Hugging Face Hub restore/sync helpers
│   ├── errors.py       # Error response helpers
│   ├── routes.py       # All HTTP route handlers
│   └── scraper.py      # URL parsing and Open Graph fetching
├── static/
│   └── style.css       # Design token stylesheet
├── tests/              # pytest suite
├── main.py             # App factory entry point
├── pyproject.toml
└── .env.example
```

---

## License

MIT
