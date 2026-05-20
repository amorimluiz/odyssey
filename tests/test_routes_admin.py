from __future__ import annotations

import importlib
import logging

from starlette.testclient import TestClient

from app.auth import hash_password, issue_token
from app.db import count_votes_for_house, get_db, get_invite_token, init_schema, insert_house, insert_manual_house, insert_user, set_invite_token
from app.scraper import OGData


def _build_client(monkeypatch, tmp_path, *, base_url: str | None = None) -> TestClient:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    if base_url is None:
        monkeypatch.delenv("BASE_URL", raising=False)
    else:
        monkeypatch.setenv("BASE_URL", base_url)
    import main

    importlib.reload(main)
    return TestClient(main.create_app())


def _make_user(*, name: str, username: str, role: str, created_at: str) -> int:
    db = get_db()
    init_schema(db)
    return insert_user(
        db,
        name=name,
        username=username,
        password_hash=hash_password("verysecure"),
        role=role,
        created_at=created_at,
    )


def _set_session(client: TestClient, user_id: int, role: str) -> None:
    client.cookies.set("session", issue_token(user_id, role))


def test_get_admin_unauthenticated_redirects_to_login(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/login"


def test_get_admin_member_forbidden(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _make_user(
            name="Member",
            username="member",
            role="member",
            created_at="2026-01-01T00:00:00+00:00",
        )
        _set_session(client, user_id, "member")

        response = client.get("/admin")

    assert response.status_code == 403


def test_get_admin_uses_base_url_and_sorts_member_list(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path, base_url="https://trip.example.com") as client:
        admin_id = _make_user(
            name="Admin",
            username="admin-user",
            role="admin",
            created_at="2026-01-02T00:00:00+00:00",
        )
        _make_user(
            name="Alice",
            username="alice",
            role="member",
            created_at="2026-01-01T00:00:00+00:00",
        )
        _make_user(
            name="Bob",
            username="bob",
            role="member",
            created_at="2026-01-03T00:00:00+00:00",
        )
        set_invite_token(get_db(), "seed-token")
        _set_session(client, admin_id, "admin")

        response = client.get("/admin")

    assert response.status_code == 200
    assert "https://trip.example.com/invite/seed-token" in response.text
    assert "Copiar" in response.text
    assert "Rotacionar" in response.text
    assert "Atualizar" in response.text
    assert "admin-controls" in response.text
    assert "admin-members" in response.text
    assert "admin-invite-input" in response.text
    assert (
        response.text.find("2026-01-01T00:00:00+00:00")
        < response.text.find("2026-01-02T00:00:00+00:00")
        < response.text.find("2026-01-03T00:00:00+00:00")
    )
    assert "/admin/users/" not in response.text
    assert "copyInviteLink" in response.text


def test_get_admin_falls_back_to_request_host_for_invite_url(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        admin_id = _make_user(
            name="Admin",
            username="admin-user",
            role="admin",
            created_at="2026-01-01T00:00:00+00:00",
        )
        set_invite_token(get_db(), "seed-token")
        _set_session(client, admin_id, "admin")

        response = client.get("/admin", headers={"host": "myhouse.local"})

    assert response.status_code == 200
    assert "http://myhouse.local/invite/seed-token" in response.text


def test_post_rotate_invite_updates_db_returns_fragment_and_invalidates_old_token(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path, base_url="https://trip.example.com") as client:
        admin_id = _make_user(
            name="Admin",
            username="admin-user",
            role="admin",
            created_at="2026-01-01T00:00:00+00:00",
        )
        set_invite_token(get_db(), "oldtoken")
        _set_session(client, admin_id, "admin")

        response = client.post("/admin/rotate-invite")
        new_token = get_invite_token(get_db())

        old_invite = client.get("/invite/oldtoken")
        new_invite = client.get(f"/invite/{new_token}")

    assert response.status_code == 200
    assert 'id="invite-link-fragment"' in response.text
    assert "Copiar" in response.text
    assert "Rotacionar" in response.text
    assert 'hx-post="/admin/rotate-invite"' in response.text
    assert new_token is not None
    assert new_token != "oldtoken"
    assert get_invite_token(get_db()) == new_token
    assert f"https://trip.example.com/invite/{new_token}" in response.text
    assert old_invite.status_code == 403
    assert new_invite.status_code == 200
    assert "Criar conta" in new_invite.text


def test_post_rotate_invite_logs_admin_id_without_token(monkeypatch, tmp_path, caplog) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        admin_id = _make_user(
            name="Admin",
            username="admin-user",
            role="admin",
            created_at="2026-01-01T00:00:00+00:00",
        )
        set_invite_token(get_db(), "oldtoken")
        _set_session(client, admin_id, "admin")

        with caplog.at_level(logging.INFO):
            response = client.post("/admin/rotate-invite")

    assert response.status_code == 200
    assert f"admin_user_id={admin_id}" in caplog.text
    assert "event=invite_rotated" in caplog.text

    db_token = get_invite_token(get_db()) or ""
    assert db_token
    assert db_token not in caplog.text
    assert "oldtoken" not in caplog.text


def test_post_rotate_invite_member_forbidden(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _make_user(
            name="Member",
            username="member",
            role="member",
            created_at="2026-01-01T00:00:00+00:00",
        )
        _set_session(client, user_id, "member")

        response = client.post("/admin/rotate-invite")

    assert response.status_code == 403


def test_delete_house_member_forbidden(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        member_id = _make_user(
            name="Member",
            username="member-delete",
            role="member",
            created_at="2026-01-01T00:00:00+00:00",
        )
        db = get_db()
        house_id = insert_house(
            db,
            source="airbnb",
            external_id="delete-forbidden",
            url="https://www.airbnb.com/rooms/delete-forbidden",
            title="Delete forbidden",
            submitted_by=member_id,
        )
        client.cookies.set("session", issue_token(member_id, "member"))

        response = client.delete(f"/houses/{house_id}")

    assert response.status_code == 403


def test_delete_house_admin_removes_house_and_votes(monkeypatch, tmp_path, caplog) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        admin_id = _make_user(
            name="Admin",
            username="admin-delete",
            role="admin",
            created_at="2026-01-01T00:00:00+00:00",
        )
        voter_id = _make_user(
            name="Voter",
            username="voter-delete",
            role="member",
            created_at="2026-01-02T00:00:00+00:00",
        )
        db = get_db()
        house_id = insert_manual_house(
            db,
            url="https://example.com/delete-success",
            title="Delete success",
            submitted_by=admin_id,
        )
        db["votes"].insert({"user_id": voter_id, "house_id": house_id, "voted_at": "2026-01-03T00:00:00+00:00"})
        db.conn.commit()
        assert count_votes_for_house(db, house_id) == 1
        _set_session(client, admin_id, "admin")
        before_delete = client.get("/")

        with caplog.at_level(logging.INFO):
            response = client.delete(f"/houses/{house_id}")
        after_delete = client.get("/")

    assert response.status_code == 204
    assert before_delete.status_code == 200
    assert "Delete success" in before_delete.text
    assert after_delete.status_code == 200
    assert "Delete success" not in after_delete.text
    assert get_db()["houses"].count == 0
    assert count_votes_for_house(get_db(), house_id) == 0
    assert "event=house_deleted" in caplog.text
    assert "https://example.com/delete-success" not in caplog.text


def test_delete_house_unknown_id_returns_404_with_utf8_charset(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        admin_id = _make_user(
            name="Admin",
            username="admin-delete-missing",
            role="admin",
            created_at="2026-01-01T00:00:00+00:00",
        )
        _set_session(client, admin_id, "admin")

        response = client.delete("/houses/999")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/plain; charset=utf-8")
    assert response.text == "Casa não encontrada."


def test_post_refresh_metadata_unauthenticated_redirects_to_login(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        response = client.post("/admin/refresh-metadata", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/login"


def test_post_refresh_metadata_member_forbidden(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _make_user(
            name="Member",
            username="member",
            role="member",
            created_at="2026-01-01T00:00:00+00:00",
        )
        _set_session(client, user_id, "member")

        response = client.post("/admin/refresh-metadata")

    assert response.status_code == 403


def test_post_refresh_metadata_scans_missing_rows_and_continues_after_failure(monkeypatch, tmp_path, caplog) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        admin_id = _make_user(
            name="Admin",
            username="admin-user",
            role="admin",
            created_at="2026-01-01T00:00:00+00:00",
        )
        db = get_db()
        init_schema(db)
        insert_house(
            db,
            source="airbnb",
            external_id="complete",
            url="https://www.airbnb.com/rooms/complete",
            title="Complete",
            image_url="https://example.com/complete.jpg",
            description="Complete description",
            price="$100",
            submitted_by=admin_id,
            submitted_at="2026-01-01T00:00:00+00:00",
        )
        insert_house(
            db,
            source="booking",
            external_id="missing-price",
            url="https://www.booking.com/hotel/br/missing-price.html",
            title="Missing price",
            image_url="https://example.com/price.jpg",
            description="Has description",
            price=None,
            submitted_by=admin_id,
            submitted_at="2026-01-02T00:00:00+00:00",
        )
        insert_house(
            db,
            source="booking",
            external_id="missing-image",
            url="https://www.booking.com/hotel/br/missing-image.html",
            title="Missing image",
            image_url="",
            description="Has description",
            price="$200",
            submitted_by=admin_id,
            submitted_at="2026-01-03T00:00:00+00:00",
        )
        insert_house(
            db,
            source="airbnb",
            external_id="missing-description",
            url="https://www.airbnb.com/rooms/missing-description",
            title="Missing description",
            image_url="https://example.com/desc.jpg",
            description=" ",
            price="$300",
            submitted_by=admin_id,
            submitted_at="2026-01-04T00:00:00+00:00",
        )
        _set_session(client, admin_id, "admin")

        fetch_calls: list[str] = []

        async def fake_fetch(url: str):
            fetch_calls.append(url)
            if "missing-price" in url:
                return None
            if "missing-image" in url:
                return OGData(title="Updated", image_url="https://example.com/new.jpg", description="Updated description", price="R$ 900")
            return OGData(title="Updated", image_url="https://example.com/desc-new.jpg", description="Updated description", price="$400")

        import app.routes as routes_module

        monkeypatch.setattr(routes_module.scraper, "fetch_og", fake_fetch)

        with caplog.at_level(logging.INFO):
            response = client.post("/admin/refresh-metadata")

    assert response.status_code == 200
    assert 'id="metadata-refresh-fragment"' in response.text
    assert "Atualizar" in response.text
    assert 'hx-post="/admin/refresh-metadata"' in response.text
    assert "Verificadas 3 casas. Atualizadas 2. Falhas: 1." in response.text
    assert len(fetch_calls) == 3
    assert "https://www.airbnb.com/rooms/complete" not in fetch_calls
    assert "event=metadata_refresh" in caplog.text
    assert "scanned=3" in caplog.text
    assert "updated=2" in caplog.text
    assert "failed=1" in caplog.text

    rows = list(db.query("SELECT external_id, image_url, description, price FROM houses ORDER BY submitted_at ASC"))
    rows_by_external_id = {row["external_id"]: row for row in rows}
    assert rows_by_external_id["complete"]["price"] == "$100"
    assert rows_by_external_id["missing-price"]["price"] is None
    assert rows_by_external_id["missing-image"]["image_url"] == "https://example.com/new.jpg"
    assert rows_by_external_id["missing-image"]["price"] == "$200"
    assert rows_by_external_id["missing-description"]["description"] == "Updated description"
    assert rows_by_external_id["missing-description"]["price"] == "$300"


def test_post_refresh_metadata_preserves_existing_fields_and_fills_only_missing_price(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        admin_id = _make_user(
            name="Admin",
            username="admin-user",
            role="admin",
            created_at="2026-01-01T00:00:00+00:00",
        )
        db = get_db()
        init_schema(db)
        insert_house(
            db,
            source="booking",
            external_id="keep-price",
            url="https://www.booking.com/hotel/br/keep-price.html",
            title="Original title",
            image_url="https://example.com/original.jpg",
            description="Original description",
            price=None,
            submitted_by=admin_id,
            submitted_at="2026-01-02T00:00:00+00:00",
        )
        _set_session(client, admin_id, "admin")

        async def fake_fetch(url: str):
            assert url == "https://www.booking.com/hotel/br/keep-price.html"
            return OGData(
                title="Replacement title",
                image_url="https://example.com/replacement.jpg",
                description="Replacement description",
                price="R$ 777",
            )

        import app.routes as routes_module

        monkeypatch.setattr(routes_module.scraper, "fetch_og", fake_fetch)

        response = client.post("/admin/refresh-metadata")

    assert response.status_code == 200
    assert "Atualizar" in response.text
    assert 'hx-post="/admin/refresh-metadata"' in response.text
    assert "Verificadas 1 casas. Atualizadas 1. Falhas: 0." in response.text
    row = list(
        db.query(
            "SELECT title, image_url, description, price FROM houses WHERE external_id = ?",
            ["keep-price"],
        )
    )[0]
    assert row["title"] == "Original title"
    assert row["image_url"] == "https://example.com/original.jpg"
    assert row["description"] == "Original description"
    assert row["price"] == "R$ 777"


def test_admin_panel_shows_username_column_not_email(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        admin_id = _make_user(
            name="Admin",
            username="admin-user",
            role="admin",
            created_at="2026-01-01T00:00:00+00:00",
        )
        _make_user(
            name="Alice",
            username="alice",
            role="member",
            created_at="2026-01-02T00:00:00+00:00",
        )
        set_invite_token(get_db(), "seed-token")
        _set_session(client, admin_id, "admin")

        response = client.get("/admin")

    assert response.status_code == 200
    assert "<th>Nome de usuário</th>" in response.text
    assert "<th>Email</th>" not in response.text
    assert "<td>alice</td>" in response.text
    assert "<td>admin-user</td>" in response.text
    assert "admin-controls" in response.text
    assert "admin-members" in response.text
