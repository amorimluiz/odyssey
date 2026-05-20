from __future__ import annotations

import importlib
import logging
from pathlib import Path

from starlette.testclient import TestClient

from app.auth import hash_password, issue_token
from app import db as app_db
from app.db import get_db, init_schema, insert_house, insert_user
from app.scraper import OGData, ParsedURL
from app.components import house_card


EXAMPLE_URLS_PATH = Path(
    ".compozy/tasks/group-house-voting/fixtures/example-urls.md"
)


def _build_client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    import main

    importlib.reload(main)
    return TestClient(main.create_app())


def _login_cookie(client: TestClient, *, role: str = "member") -> int:
    db = get_db()
    init_schema(db)
    user_id = insert_user(
        db,
        name="Member",
        username="member",
        password_hash=hash_password("verysecure"),
        role=role,
    )
    client.cookies.set("session", issue_token(user_id, role))
    return user_id


def _example_urls() -> tuple[str, str]:
    text = EXAMPLE_URLS_PATH.read_text(encoding="utf-8")
    blocks = [part.strip() for part in text.split("```") if part.strip().startswith("http")]
    return blocks[0], blocks[1]


def test_house_card_placeholder_when_image_missing() -> None:
    html = repr(
        house_card(
            {
                "id": 1,
                "source": "airbnb",
                "url": "https://www.airbnb.com/rooms/123",
                "title": "Casa",
                "image_url": None,
                "description": "Desc",
                "price": "$100",
                "vote_count": 0,
            }
        )
    )
    assert "Imagem indisponível" in html


def test_house_card_hides_price_when_missing() -> None:
    html = repr(
        house_card(
            {
                "id": 1,
                "source": "airbnb",
                "url": "https://www.airbnb.com/rooms/123",
                "title": "Casa",
                "image_url": None,
                "description": "Desc",
                "price": None,
                "vote_count": 0,
            }
        )
    )
    assert "house-card-price" not in html
    assert "Abrir anúncio" in html


def test_house_card_source_badge_mapping() -> None:
    airbnb_html = repr(
        house_card(
            {
                "id": 1,
                "source": "airbnb",
                "url": "https://www.airbnb.com/rooms/123",
                "title": "Casa",
                "image_url": None,
                "description": "Desc",
                "price": None,
                "vote_count": 0,
            }
        )
    )
    booking_html = repr(
        house_card(
            {
                "id": 2,
                "source": "booking",
                "url": "https://www.booking.com/hotel/br/abc.html",
                "title": "Hotel",
                "image_url": None,
                "description": "Desc",
                "price": None,
                "vote_count": 0,
            }
        )
    )
    assert "Airbnb" in airbnb_html
    assert "Booking" in booking_html


def test_get_root_unauthenticated_redirects_to_login(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/login"


def test_get_root_empty_state(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _login_cookie(client)
        response = client.get("/")

    assert response.status_code == 200
    assert "Cole uma URL do Airbnb ou Booking acima para começar." in response.text


def test_post_houses_invalid_domain_returns_422(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _login_cookie(client)
        response = client.post("/houses", data={"url": "https://example.com/x"})

    assert response.status_code == 422
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "Apenas URLs do Airbnb e Booking são suportadas." in response.text
    assert "error-fragment" in response.text
    assert get_db()["houses"].count == 0


def test_post_houses_success_inserts_and_returns_card(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _login_cookie(client)
        import app.routes as routes_module
        calls: list[str] = []

        async def fake_fetch(_url: str):
            return OGData(title="Fetched title", image_url=None, description="Desc", price=None)

        monkeypatch.setattr(routes_module.scraper, "fetch_og", fake_fetch)
        monkeypatch.setattr(routes_module.scraper, "last_fetch_meta", lambda: {"status": 200, "elapsed_ms": 11})
        monkeypatch.setattr(app_db, "sync_sqlite_files", lambda settings: calls.append(settings.db_path))

        response = client.post(
            "/houses",
            data={"url": "https://www.airbnb.com/rooms/123456"},
        )

    assert response.status_code == 200
    assert "house-" in response.text
    assert "Abrir anúncio" in response.text
    assert calls == [str(tmp_path / "app.db")]
    rows = list(get_db().query("SELECT submitted_by, source, external_id FROM houses"))
    assert len(rows) == 1
    assert int(rows[0]["submitted_by"]) == user_id
    assert rows[0]["source"] == "airbnb"
    assert rows[0]["external_id"] == "123456"


def test_post_houses_booking_submission_uses_fetch_url_and_renders_price(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _login_cookie(client)
        import app.routes as routes_module

        booking_url = (
            "https://www.booking.com/hotel/br/villa-inn-economic.html"
            "?checkin=2026-08-01&checkout=2026-08-03&group_adults=2&no_rooms=1&selected_currency=BRL"
            "&utm_source=newsletter"
        )
        parsed = ParsedURL(
            source="booking",
            external_id="villa-inn-economic",
            normalized="https://www.booking.com/hotel/br/villa-inn-economic.html",
            fetch_url=(
                "https://www.booking.com/hotel/br/villa-inn-economic.html"
                "?checkin=2026-08-01&checkout=2026-08-03&group_adults=2&no_rooms=1&selected_currency=BRL"
            ),
        )
        fetch_calls: list[str] = []

        def fake_parse_url(url: str):
            assert url == booking_url
            return parsed

        async def fake_fetch(url: str):
            fetch_calls.append(url)
            return OGData(
                title="Villa Inn Economic",
                image_url="https://example.com/villa.jpg",
                description="Desc",
                price="R$ 1.250",
            )

        monkeypatch.setattr(routes_module.scraper, "parse_url", fake_parse_url)
        monkeypatch.setattr(routes_module.scraper, "fetch_og", fake_fetch)
        monkeypatch.setattr(routes_module.scraper, "last_fetch_meta", lambda: {"status": 200, "elapsed_ms": 17})

        response = client.post("/houses", data={"url": booking_url})

    assert response.status_code == 200
    assert "house-card-price" in response.text
    assert "R$ 1.250" in response.text
    assert fetch_calls == [parsed.fetch_url]
    rows = list(get_db().query("SELECT submitted_by, url, price, source, external_id FROM houses"))
    assert len(rows) == 1
    assert rows[0]["url"] == parsed.normalized
    assert rows[0]["price"] == "R$ 1.250"
    assert rows[0]["source"] == "booking"
    assert rows[0]["external_id"] == "villa-inn-economic"
    assert int(rows[0]["submitted_by"]) == user_id


def test_post_houses_metadata_failure_returns_502_with_retryable_feedback(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _login_cookie(client)
        import app.routes as routes_module

        async def fake_fetch(_url: str):
            return None

        monkeypatch.setattr(routes_module.scraper, "fetch_og", fake_fetch)
        monkeypatch.setattr(routes_module.scraper, "last_fetch_meta", lambda: {"status": 200, "elapsed_ms": 19})

        response = client.post("/houses", data={"url": "https://www.airbnb.com/rooms/123456"})

    assert response.status_code == 502
    assert "Não foi possível buscar os metadados do anúncio." in response.text
    assert "Tente novamente em alguns segundos." in response.text
    assert "error-fragment retryable" in response.text


def test_post_houses_duplicate_highlight_no_insert(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _login_cookie(client)
        db = get_db()
        house_id = insert_house(
            db,
            source="airbnb",
            external_id="999",
            url="https://www.airbnb.com/rooms/999",
            title="Existing",
            image_url=None,
            description="Existing",
            price=None,
            submitted_by=user_id,
        )

        import app.routes as routes_module

        fetch_called = False

        async def fake_fetch(_url: str):
            nonlocal fetch_called
            fetch_called = True
            raise AssertionError("fetch_og should not be called for duplicate submissions")

        monkeypatch.setattr(routes_module.scraper, "fetch_og", fake_fetch)

        response = client.post("/houses", data={"url": "https://www.airbnb.com/rooms/999?x=1"})

    assert response.status_code == 200
    assert 'hx-swap-oob="true"' in response.text
    assert f'id="house-{house_id}"' in response.text
    assert fetch_called is False
    assert get_db()["houses"].count == 1
    row = list(get_db().query("SELECT price FROM houses WHERE id = ?", [house_id]))[0]
    assert row["price"] is None


def test_post_houses_og_failure_returns_502_and_logs(monkeypatch, tmp_path, caplog) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _login_cookie(client)
        import app.routes as routes_module

        async def fake_fetch(_url: str):
            return None

        monkeypatch.setattr(routes_module.scraper, "fetch_og", fake_fetch)
        monkeypatch.setattr(routes_module.scraper, "last_fetch_meta", lambda: {"status": "timeout", "elapsed_ms": 123})

        with caplog.at_level(logging.ERROR):
            response = client.post("/houses", data={"url": "https://www.airbnb.com/rooms/888"})

    assert response.status_code == 502
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "error-fragment retryable" in response.text
    assert "Tente novamente em alguns segundos." in response.text
    assert get_db()["houses"].count == 0
    assert "status=timeout" in caplog.text
    assert "url=https://www.airbnb.com/rooms/888" in caplog.text


def test_post_then_get_shows_new_card_first(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _login_cookie(client)
        import app.routes as routes_module
        db = get_db()
        async def fake_fetch(_url: str):
            return OGData(title="Newest", image_url=None, description="Desc", price=None)
        monkeypatch.setattr(routes_module.scraper, "fetch_og", fake_fetch)
        monkeypatch.setattr(routes_module.scraper, "last_fetch_meta", lambda: {"status": 200, "elapsed_ms": 8})
        insert_house(
            db,
            source="airbnb",
            external_id="1",
            url="https://www.airbnb.com/rooms/1",
            title="Old",
            image_url=None,
            description="Old",
            price=None,
            submitted_by=user_id,
            submitted_at="2099-01-01T00:00:00+00:00",
        )

        client.post("/houses", data={"url": "https://www.airbnb.com/rooms/2"})
        response = client.get("/")

    assert response.status_code == 200
    assert response.text.find("house-2") < response.text.find("house-1")


def test_submission_pipeline_call_order(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _login_cookie(client)
        import app.routes as routes_module

        calls: list[str] = []

        def fake_parse_url(_url: str):
            calls.append("parse")
            return ParsedURL(
                source="airbnb",
                external_id="123",
                normalized="https://www.airbnb.com/rooms/123",
                fetch_url="https://www.airbnb.com/rooms/123",
            )

        def fake_get_house_by_external_id(*_args, **_kwargs):
            calls.append("dedupe")
            return None

        async def fake_fetch(_url: str):
            calls.append("fetch")
            return OGData(title="Title", image_url=None, description="Desc", price=None)

        def fake_insert_house(*_args, **_kwargs):
            calls.append("insert")
            return 42

        monkeypatch.setattr(routes_module.scraper, "parse_url", fake_parse_url)
        monkeypatch.setattr(routes_module, "get_house_by_external_id", fake_get_house_by_external_id)
        monkeypatch.setattr(routes_module.scraper, "fetch_og", fake_fetch)
        monkeypatch.setattr(routes_module, "insert_house", fake_insert_house)

        response = client.post("/houses", data={"url": "https://www.airbnb.com/rooms/123"})

    assert response.status_code == 200
    assert calls == ["parse", "dedupe", "fetch", "insert"]


def test_example_airbnb_and_booking_urls_success_path(monkeypatch, tmp_path) -> None:
    airbnb_url, booking_url = _example_urls()

    with _build_client(monkeypatch, tmp_path) as client:
        _login_cookie(client)
        import app.routes as routes_module

        async def fake_fetch(url: str):
            if "airbnb" in url:
                return OGData(title="Airbnb", image_url=None, description="Desc", price=None)
            return OGData(title="Booking", image_url=None, description="Desc", price=None)

        monkeypatch.setattr(routes_module.scraper, "fetch_og", fake_fetch)
        monkeypatch.setattr(routes_module.scraper, "last_fetch_meta", lambda: {"status": 200, "elapsed_ms": 10})

        r1 = client.post("/houses", data={"url": airbnb_url})
        r2 = client.post("/houses", data={"url": booking_url})

    assert r1.status_code == 200
    assert r2.status_code == 200
    rows = list(get_db().query("SELECT source, external_id FROM houses ORDER BY id"))
    assert [row["source"] for row in rows] == ["airbnb", "booking"]
