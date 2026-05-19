from __future__ import annotations

import importlib
import logging

from starlette.testclient import TestClient

from app.auth import hash_password, issue_token
from app.db import get_db, get_invite_token, init_schema, insert_user, set_invite_token


def _build_client(monkeypatch, tmp_path, *, base_url: str | None = None) -> TestClient:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    if base_url is None:
        monkeypatch.delenv("BASE_URL", raising=False)
    else:
        monkeypatch.setenv("BASE_URL", base_url)
    import main

    importlib.reload(main)
    return TestClient(main.create_app())


def _make_user(*, name: str, email: str, role: str, created_at: str) -> int:
    db = get_db()
    init_schema(db)
    return insert_user(
        db,
        name=name,
        email=email,
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
            email="member@example.com",
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
            email="admin@example.com",
            role="admin",
            created_at="2026-01-02T00:00:00+00:00",
        )
        _make_user(
            name="Alice",
            email="alice@example.com",
            role="member",
            created_at="2026-01-01T00:00:00+00:00",
        )
        _make_user(
            name="Bob",
            email="bob@example.com",
            role="member",
            created_at="2026-01-03T00:00:00+00:00",
        )
        set_invite_token(get_db(), "seed-token")
        _set_session(client, admin_id, "admin")

        response = client.get("/admin")

    assert response.status_code == 200
    assert "https://trip.example.com/invite/seed-token" in response.text
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
            email="admin@example.com",
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
            email="admin@example.com",
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
    assert new_token is not None
    assert new_token != "oldtoken"
    assert f"https://trip.example.com/invite/{new_token}" in response.text
    assert old_invite.status_code == 403
    assert new_invite.status_code == 200
    assert "Create account" in new_invite.text


def test_post_rotate_invite_logs_admin_id_without_token(monkeypatch, tmp_path, caplog) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        admin_id = _make_user(
            name="Admin",
            email="admin@example.com",
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
            email="member@example.com",
            role="member",
            created_at="2026-01-01T00:00:00+00:00",
        )
        _set_session(client, user_id, "member")

        response = client.post("/admin/rotate-invite")

    assert response.status_code == 403
