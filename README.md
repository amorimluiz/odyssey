# Group House Voting

A lightweight web app for groups to collaboratively shortlist and vote on Airbnb and Booking.com rentals — built for our Réveillon house search.

Paste a listing URL, the app scrapes the title, photo, and price automatically, and everyone votes on their favourites. The house with the most votes rises to the top.

---

## Features

- **Invite-only registration** — admin generates a single-use invite link; anyone with it can create an account
- **Airbnb & Booking.com scraping** — Open Graph metadata (title, image, description, price) fetched on submission; URLs are normalised and deduplicated
- **Toggle voting** — one click to cast or retract a vote per listing
- **Ranked list** — houses sorted live by vote count
- **Admin panel** — rotate the invite link, view the member list
- **Health check** — `GET /healthz` for uptime monitoring

---

## Stack

| Layer | Technology |
|---|---|
| Web framework | [FastHTML](https://fastht.ml) + [Starlette](https://www.starlette.io) |
| Database | SQLite via [sqlite-utils](https://sqlite-utils.datasette.io) |
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

### Run tests

```bash
pytest
```

Coverage is enforced at 80%. To see the HTML report:

```bash
pytest --cov-report=html
open htmlcov/index.html
```

---

## How to Use

1. Start the server and open `http://localhost:8000`.
2. The first registered user becomes admin automatically (or the email matching `ADMIN_EMAIL`).
3. As admin, go to `/admin` to copy the invite link and share it with your group.
4. Everyone registers via the invite link and lands on the voting page.
5. Paste any Airbnb (`airbnb.com/rooms/<id>`) or Booking.com (`booking.com/hotel/...`) URL into the form.
6. Click the vote button on any listing to cast or retract your vote.
7. The house with the most votes floats to the top — that's your pick.

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
