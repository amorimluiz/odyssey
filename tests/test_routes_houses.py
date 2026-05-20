from __future__ import annotations

import importlib
import logging

from starlette.testclient import TestClient

from app.auth import hash_password, issue_token
from app.db import count_votes_for_house, get_db, init_schema, insert_house, insert_manual_house, insert_user
from app.scraper import OGData, ParsedURL
from app.components import house_card


EXAMPLE_AIRBNB_URL = "https://www.airbnb.com/rooms/32311963"
EXAMPLE_BOOKING_URL = (
    "https://www.booking.com/hotel/br/villa-inn-economic.html"
    "?checkin=2026-12-30&checkout=2027-01-03&group_adults=11&group_children=0"
    "&highlighted_blocks=691479801_285025048_5_1_0%2C691479801_285025048_3_1_0%2C691479801_285025048_3_1_0"
    "&matching_block_id=691479801_285025048_5_1_0&no_rooms=5&room1=A%2CA&room2=A%2CA&room3=A%2CA"
    "&room4=A%2CA&room5=A%2CA%2CA&sb_price_type=total&type=total"
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
    return EXAMPLE_AIRBNB_URL, EXAMPLE_BOOKING_URL


def _assert_card_contract(html: str, *, expect_delete: bool) -> None:
    assert 'class="house-card-link"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    assert 'class="house-card-action-zone"' in html
    assert "Abrir anúncio" not in html
    if expect_delete:
        assert 'hx-delete="/houses/' in html
    else:
        assert 'hx-delete="/houses/' not in html


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
    _assert_card_contract(html, expect_delete=False)


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
    _assert_card_contract(html, expect_delete=False)


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
    assert 'class="house-submit-row"' in response.text
    assert 'class="btn house-submit-icon-btn"' in response.text
    assert 'aria-label="Adicionar casa pela URL"' in response.text
    assert "Cadastrar manualmente" in response.text
    assert 'hx-get="/houses/manual/new"' in response.text
    assert 'id="house-modal"' in response.text
    assert 'hx-on-click="window.__houseModalTrigger = this"' in response.text


def test_get_root_admin_renders_delete_controls(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _login_cookie(client, role="admin")
        db = get_db()
        insert_house(
            db,
            source="manual",
            external_id="manual-admin",
            url="https://example.com/manual-admin",
            title="Casa admin",
            submitted_by=user_id,
        )

        response = client.get("/")

    assert response.status_code == 200
    _assert_card_contract(response.text, expect_delete=True)
    assert 'aria-label="Excluir casa"' in response.text
    assert "🗑" in response.text


def test_get_root_member_does_not_render_delete_controls(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _login_cookie(client, role="member")
        db = get_db()
        insert_house(
            db,
            source="manual",
            external_id="manual-member",
            url="https://example.com/manual-member",
            title="Casa member",
            submitted_by=user_id,
        )

        response = client.get("/")

    assert response.status_code == 200
    _assert_card_contract(response.text, expect_delete=False)
    assert 'aria-label="Excluir casa"' not in response.text


def test_manual_house_full_flow_updates_root_and_preserves_vote_state(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        creator_id = _login_cookie(client, role="member")
        db = get_db()

        create_response = client.post(
            "/houses/manual",
            data={
                "title": "Casa manual original",
                "url": "https://example.com/manual-original",
            },
        )
        house_row = list(
            db.query(
                "SELECT id FROM houses WHERE submitted_by = ? AND url = ?",
                [creator_id, "https://example.com/manual-original"],
            )
        )[0]
        house_id = int(house_row["id"])

        list_response = client.get("/")

        voter_id = insert_user(
            db,
            name="Voter",
            username="voter",
            password_hash=hash_password("verysecure"),
            role="member",
        )
        client.cookies.set("session", issue_token(voter_id, "member"))
        vote_response = client.post(f"/houses/{house_id}/vote")

        edit_response = client.put(
            f"/houses/{house_id}",
            data={
                "title": "Casa manual atualizada",
                "url": "https://example.com/manual-atualizada",
                "image_url": "",
                "description": "Descrição atualizada",
                "price": "$250",
            },
        )
        updated_list_response = client.get("/")

    assert create_response.status_code == 200
    assert "Casa manual original" in create_response.text
    assert "Manual" in create_response.text
    _assert_card_contract(create_response.text, expect_delete=False)

    assert list_response.status_code == 200
    assert "Casa manual original" in list_response.text
    _assert_card_contract(list_response.text, expect_delete=False)

    assert vote_response.status_code == 200
    assert 'aria-pressed="true"' in vote_response.text
    assert 'aria-label="Remover voto desta casa"' in vote_response.text
    assert "♥" in vote_response.text
    assert ">1<" in vote_response.text

    assert edit_response.status_code == 200
    assert "Casa manual atualizada" in edit_response.text
    _assert_card_contract(edit_response.text, expect_delete=False)
    assert "♥" in edit_response.text
    assert ">1<" in edit_response.text

    assert updated_list_response.status_code == 200
    assert "Casa manual atualizada" in updated_list_response.text
    _assert_card_contract(updated_list_response.text, expect_delete=False)


def test_manual_house_duplicate_urls_are_allowed(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _login_cookie(client)
        db = get_db()

        first_response = client.post(
            "/houses/manual",
            data={
                "title": "Casa manual 1",
                "url": "https://example.com/manual-duplicate",
            },
        )
        second_response = client.post(
            "/houses/manual",
            data={
                "title": "Casa manual 2",
                "url": "https://example.com/manual-duplicate",
            },
        )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    rows = list(
        db.query(
            "SELECT title, url, source FROM houses WHERE submitted_by = ? ORDER BY id ASC",
            [user_id],
        )
    )
    assert len(rows) == 2
    assert [row["title"] for row in rows] == ["Casa manual 1", "Casa manual 2"]
    assert all(row["source"] == "manual" for row in rows)
    assert {row["url"] for row in rows} == {"https://example.com/manual-duplicate"}


def test_get_manual_house_form_unauthenticated_redirects(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        response = client.get("/houses/manual/new", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/login"


def test_get_manual_house_form_authenticated_returns_modal(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _login_cookie(client)
        response = client.get("/houses/manual/new")

    assert response.status_code == 200
    assert 'id="house-modal"' in response.text
    assert 'role="dialog"' in response.text
    assert 'aria-modal="true"' in response.text
    assert 'aria-labelledby="house-modal-title"' in response.text
    assert 'hx-post="/houses/manual"' in response.text
    assert 'hx-target="#house-list"' in response.text
    assert 'autofocus' in response.text
    assert 'tabindex="-1"' in response.text
    assert "this.querySelector('#title')?.focus()" in response.text
    assert "hx-on-keydown" in response.text
    assert "event.target !== this" in response.text
    assert "event.stopPropagation()" in response.text
    assert "Cadastrar casa manualmente" in response.text


def test_post_manual_house_unauthenticated_redirects(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        response = client.post("/houses/manual", data={"title": "Casa", "url": "https://example.com/manual"}, follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/login"


def test_post_manual_house_creates_manual_house(monkeypatch, tmp_path, caplog) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _login_cookie(client)
        with caplog.at_level(logging.INFO):
            response = client.post(
                "/houses/manual",
                data={
                    "title": "Casa manual",
                    "url": "https://example.com/manual",
                },
            )

    assert response.status_code == 200
    assert 'hx-swap-oob="true"' in response.text
    assert "window.__houseModalTrigger?.focus?.()" in response.text
    assert "Manual" in response.text
    _assert_card_contract(response.text, expect_delete=False)
    rows = list(get_db().query("SELECT id, source, external_id, submitted_by, title, url, image_url, description, price FROM houses"))
    assert len(rows) == 1
    assert rows[0]["source"] == "manual"
    assert str(rows[0]["external_id"]).startswith("manual-")
    assert int(rows[0]["submitted_by"]) == user_id
    assert rows[0]["title"] == "Casa manual"
    assert rows[0]["url"] == "https://example.com/manual"
    assert rows[0]["image_url"] is None
    assert rows[0]["description"] is None
    assert rows[0]["price"] is None
    assert "event=manual_house_created" in caplog.text
    assert "https://example.com/manual" not in caplog.text


def test_post_manual_house_invalid_url_returns_422(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _login_cookie(client)
        response = client.post(
            "/houses/manual",
            data={
                "title": "Casa manual",
                "url": "notaurl",
            },
        )

    assert response.status_code == 422
    assert response.headers["hx-retarget"] == "#house-modal"
    assert response.headers["hx-reswap"] == "outerHTML"
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "error-fragment" in response.text
    assert 'id="house-modal"' in response.text
    assert 'role="alert"' in response.text
    assert "URL" in response.text
    assert 'hx-swap-oob="true"' not in response.text
    assert get_db()["houses"].count == 0


def test_get_edit_house_form_authenticated_returns_prefilled_modal(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _login_cookie(client)
        db = get_db()
        house_id = insert_house(
            db,
            source="airbnb",
            external_id="edit-form",
            url="https://www.airbnb.com/rooms/edit-form",
            title="Original title",
            image_url="https://example.com/original.jpg",
            description="Original description",
            price="$100",
            submitted_by=user_id,
        )
        response = client.get(f"/houses/{house_id}/edit")

    assert response.status_code == 200
    assert 'id="house-modal"' in response.text
    assert 'role="dialog"' in response.text
    assert 'aria-modal="true"' in response.text
    assert 'aria-labelledby="house-modal-title"' in response.text
    assert 'hx-put="/houses/' in response.text
    assert 'autofocus' in response.text
    assert 'tabindex="-1"' in response.text
    assert "this.querySelector('#title')?.focus()" in response.text
    assert "event.target !== this" in response.text
    assert "event.stopPropagation()" in response.text
    assert 'value="Original title"' in response.text
    assert 'value="https://www.airbnb.com/rooms/edit-form"' in response.text
    assert 'value="https://example.com/original.jpg"' in response.text


def test_put_house_updates_scraped_house_and_preserves_vote_state(monkeypatch, tmp_path, caplog) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _login_cookie(client)
        db = get_db()
        house_id = insert_house(
            db,
            source="airbnb",
            external_id="update-me",
            url="https://www.airbnb.com/rooms/update-me",
            title="Original title",
            image_url="https://example.com/original.jpg",
            description="Original description",
            price="$100",
            submitted_by=user_id,
        )
        vote_response = client.post(f"/houses/{house_id}/vote")
        assert vote_response.status_code == 200
        assert count_votes_for_house(db, house_id) == 1

        with caplog.at_level(logging.INFO):
            response = client.put(
                f"/houses/{house_id}",
                data={
                    "title": "Updated title",
                    "url": "https://example.com/updated",
                    "image_url": "",
                    "description": "Updated description",
                    "price": "$200",
                },
            )

    assert response.status_code == 200
    assert 'hx-swap-oob="true"' in response.text
    assert "window.__houseModalTrigger?.focus?.()" in response.text
    assert "Updated title" in response.text
    assert 'aria-label="Remover voto desta casa"' in response.text
    assert "♥" in response.text
    assert ">1<" in response.text
    row = list(get_db().query("SELECT source, external_id, title, url, image_url, description, price FROM houses WHERE id = ?", [house_id]))[0]
    assert row["source"] == "airbnb"
    assert row["external_id"] == "update-me"
    assert row["title"] == "Updated title"
    assert row["url"] == "https://example.com/updated"
    assert row["image_url"] is None
    assert row["description"] == "Updated description"
    assert row["price"] == "$200"
    assert "event=house_updated" in caplog.text
    assert "https://example.com/updated" not in caplog.text


def test_put_house_invalid_image_url_returns_422_and_keeps_row(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _login_cookie(client)
        db = get_db()
        house_id = insert_manual_house(
            db,
            url="https://example.com/original",
            title="Original title",
            image_url="https://example.com/original.jpg",
            description="Original description",
            price="$100",
            submitted_by=user_id,
        )

        response = client.put(
            f"/houses/{house_id}",
            data={
                "title": "Original title",
                "url": "https://example.com/original",
                "image_url": "nota-url",
                "description": "Original description",
                "price": "$100",
            },
        )

        row = list(
            db.query(
                "SELECT title, url, image_url, description, price FROM houses WHERE id = ?",
                [house_id],
            )
        )[0]

    assert response.status_code == 422
    assert response.headers["hx-retarget"] == "#house-modal"
    assert response.headers["hx-reswap"] == "outerHTML"
    assert 'id="house-modal"' in response.text
    assert 'role="alert"' in response.text
    assert "URL da imagem" in response.text
    assert 'hx-swap-oob="true"' not in response.text
    assert row["title"] == "Original title"
    assert row["url"] == "https://example.com/original"
    assert row["image_url"] == "https://example.com/original.jpg"
    assert row["description"] == "Original description"
    assert row["price"] == "$100"


def test_put_house_unknown_id_returns_404(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _login_cookie(client)
        response = client.put(
            "/houses/999",
            data={
                "title": "Updated title",
                "url": "https://example.com/updated",
            },
        )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/plain; charset=utf-8")
    assert response.text == "Casa não encontrada."


def test_get_edit_house_unknown_id_returns_404(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _login_cookie(client)
        response = client.get("/houses/999/edit")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/plain; charset=utf-8")
    assert response.text == "Casa não encontrada."


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

        async def fake_fetch(_url: str):
            return OGData(title="Fetched title", image_url=None, description="Desc", price=None)

        monkeypatch.setattr(routes_module.scraper, "fetch_og", fake_fetch)
        monkeypatch.setattr(routes_module.scraper, "last_fetch_meta", lambda: {"status": 200, "elapsed_ms": 11})

        response = client.post(
            "/houses",
            data={"url": "https://www.airbnb.com/rooms/123456"},
        )

    assert response.status_code == 200
    assert "house-" in response.text
    _assert_card_contract(response.text, expect_delete=False)
    assert 'aria-pressed="false"' in response.text
    assert "house-card-vote-btn" in response.text
    assert "♡" in response.text
    rows = list(get_db().query("SELECT id, submitted_by, source, external_id FROM houses"))
    assert len(rows) == 1
    assert f'id="house-{rows[0]["id"]}"' in response.text
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
    _assert_card_contract(response.text, expect_delete=False)
    assert 'aria-pressed="false"' in response.text
    assert "house-card-vote-btn" in response.text
    assert "♡" in response.text
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


def test_post_houses_booking_missing_metadata_uses_manual_recovery(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _login_cookie(client)
        import app.routes as routes_module

        async def fake_fetch(_url: str):
            return None

        monkeypatch.setattr(routes_module.scraper, "fetch_og", fake_fetch)
        monkeypatch.setattr(
            routes_module.scraper,
            "last_fetch_meta",
            lambda: {"status": 202, "elapsed_ms": 19, "failure_reason": "missing_title"},
        )

        response = client.post("/houses", data={"url": EXAMPLE_BOOKING_URL})

    assert response.status_code == 502
    assert "role=\"alert\"" in response.text
    assert "Booking" in response.text
    assert "Cadastrar manualmente" in response.text
    assert "Tente novamente em alguns segundos." in response.text
    assert get_db()["houses"].count == 0


def test_post_houses_airbnb_missing_metadata_keeps_generic_recovery(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _login_cookie(client)
        import app.routes as routes_module

        async def fake_fetch(_url: str):
            return None

        monkeypatch.setattr(routes_module.scraper, "fetch_og", fake_fetch)
        monkeypatch.setattr(
            routes_module.scraper,
            "last_fetch_meta",
            lambda: {"status": 202, "elapsed_ms": 19, "failure_reason": "missing_title"},
        )

        response = client.post("/houses", data={"url": EXAMPLE_AIRBNB_URL})

    assert response.status_code == 502
    assert "role=\"alert\"" in response.text
    assert "Não foi possível buscar os metadados do anúncio." in response.text
    assert "Cadastrar manualmente" not in response.text
    assert "Tente novamente em alguns segundos." in response.text
    assert get_db()["houses"].count == 0


def test_post_houses_booking_success_creates_house(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _login_cookie(client)
        import app.routes as routes_module

        async def fake_fetch(_url: str):
            return OGData(
                title="Booking House",
                image_url="https://example.com/booking.jpg",
                description="Description",
                price="R$ 250",
            )

        monkeypatch.setattr(routes_module.scraper, "fetch_og", fake_fetch)
        monkeypatch.setattr(routes_module.scraper, "last_fetch_meta", lambda: {"status": 202, "elapsed_ms": 19})

        response = client.post("/houses", data={"url": EXAMPLE_BOOKING_URL})

    assert response.status_code == 200
    assert "Booking House" in response.text
    assert "house-card-price" in response.text
    rows = list(get_db().query("SELECT submitted_by, source, external_id, url, title, image_url, description, price FROM houses"))
    assert len(rows) == 1
    row = rows[0]
    assert int(row["submitted_by"]) == user_id
    assert row["source"] == "booking"
    assert row["external_id"] == "villa-inn-economic"
    assert row["url"] == "https://www.booking.com/hotel/br/villa-inn-economic.html"
    assert row["title"] == "Booking House"
    assert row["image_url"] == "https://example.com/booking.jpg"
    assert row["description"] == "Description"
    assert row["price"] == "R$ 250"


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
    _assert_card_contract(response.text, expect_delete=False)
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
    _assert_card_contract(response.text, expect_delete=False)


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
