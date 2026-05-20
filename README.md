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
| Production persistence | Direct Turso/libSQL via [libsql](https://github.com/tursodatabase/libsql-client-py) |
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
| `APP_ENV` | No | `development` | Environment selector. Use `production` to require Turso/libSQL settings and direct remote persistence. |
| `DB_PATH` | No | `./app.db` | Path to the SQLite database file. |
| `ADMIN_EMAIL` | No | — | Email that receives the `admin` role on first registration. |
| `BASE_URL` | No | — | Public base URL used to build invite links (e.g. `https://myapp.example.com`). Falls back to the request host when omitted. |
| `TURSO_DATABASE_URL` | No, but required when `APP_ENV=production` | — | Turso/libSQL database URL used for direct production connections. |
| `TURSO_AUTH_TOKEN` | No, but required when `APP_ENV=production` | — | Turso auth token used with the production database URL. |

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

Development and tests run against local SQLite by default.

Production must set `APP_ENV=production` and provide both Turso settings. The app fails fast during startup if either value is missing.

```bash
APP_ENV=production
TURSO_DATABASE_URL=libsql://<your-database>.turso.io
TURSO_AUTH_TOKEN=<your-turso-auth-token>
```

Production connects directly to Turso/libSQL and commits writes remotely. It does not rely on a local SQLite file.

### Run tests

```bash
pytest
```

Coverage is enforced at 80%. The test suite mocks libSQL connections, so it does not require a live Turso database or real Turso credentials.

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
