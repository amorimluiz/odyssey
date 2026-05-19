from __future__ import annotations

import importlib

from starlette.testclient import TestClient

from app.auth import hash_password
from app.db import get_db, get_invite_token, init_schema, insert_user, set_invite_token


def _build_client(monkeypatch, tmp_path, *, admin_email: str | None = None) -> TestClient:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    if admin_email is None:
        monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    else:
        monkeypatch.setenv("ADMIN_EMAIL", admin_email)
    import main

    importlib.reload(main)
    return TestClient(main.create_app())


def _seed_invite(token: str) -> None:
    db = get_db()
    init_schema(db)
    set_invite_token(db, token)


def test_get_invite_valid_returns_form(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")

        response = client.get("/invite/invite-ok")

    assert response.status_code == 200
    assert "Create account" in response.text


def test_get_invite_invalid_returns_403_same_shell(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")

        bad = client.get("/invite/bad-token")
        other_bad = client.get("/invite/another-bad")

    assert bad.status_code == 403
    assert other_bad.status_code == 403
    assert "Create account" in bad.text
    assert "disabled" in bad.text
    assert "disabled" in other_bad.text
    assert "Create account" in other_bad.text


def test_register_lowercases_email_and_sets_session_cookie(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")

        response = client.post(
            "/register",
            data={
                "name": "Alice",
                "email": "ALICE@EXAMPLE.COM",
                "password": "supersecure",
                "token": "invite-ok",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "session=" in response.headers["set-cookie"].lower()

    db = get_db()
    row = list(db.query("SELECT email FROM users LIMIT 1"))[0]
    assert row["email"] == "alice@example.com"


def test_register_short_password_rejected_without_insert(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")

        response = client.post(
            "/register",
            data={"name": "Bob", "email": "bob@example.com", "password": "short", "token": "invite-ok"},
        )

    assert response.status_code == 422
    assert "Password must be at least 8 characters." in response.text
    db = get_db()
    assert db["users"].count == 0


def test_register_admin_email_gets_admin_role(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path, admin_email="alice@x.com") as client:
        _seed_invite("invite-ok")
        client.post(
            "/register",
            data={"name": "Alice", "email": "Alice@X.com", "password": "verysecure", "token": "invite-ok"},
            follow_redirects=False,
        )

    db = get_db()
    user = list(db.query("SELECT role FROM users LIMIT 1"))[0]
    assert user["role"] == "admin"


def test_register_first_user_admin_when_admin_email_unset(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")
        client.post(
            "/register",
            data={"name": "First", "email": "first@x.com", "password": "verysecure", "token": "invite-ok"},
            follow_redirects=False,
        )

    db = get_db()
    user = list(db.query("SELECT role FROM users LIMIT 1"))[0]
    assert user["role"] == "admin"


def test_register_next_user_member_when_users_exist(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")
        db = get_db()
        insert_user(db, name="Existing", email="existing@x.com", password_hash=hash_password("existingpass"), role="admin")

        client.post(
            "/register",
            data={"name": "Second", "email": "second@x.com", "password": "verysecure", "token": "invite-ok"},
            follow_redirects=False,
        )

    db = get_db()
    second = list(db.query("SELECT role FROM users WHERE email = ?", ["second@x.com"]))[0]
    assert second["role"] == "member"


def test_register_rotated_token_rejected(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("old-token")
        db = get_db()
        set_invite_token(db, "new-token")

        response = client.post(
            "/register",
            data={"name": "Alice", "email": "alice@x.com", "password": "verysecure", "token": "old-token"},
        )

    assert response.status_code == 403
    assert get_invite_token(get_db()) == "new-token"


def test_register_duplicate_email_rejected(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")
        client.post(
            "/register",
            data={"name": "One", "email": "dup@x.com", "password": "verysecure", "token": "invite-ok"},
            follow_redirects=False,
        )

        response = client.post(
            "/register",
            data={"name": "Two", "email": "DUP@x.com", "password": "anothervalue", "token": "invite-ok"},
        )

    assert response.status_code == 409
    assert "Email is already registered." in response.text
    assert get_db()["users"].count == 1


def test_login_valid_credentials_sets_cookie(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        db = get_db()
        init_schema(db)
        insert_user(db, name="User", email="user@x.com", password_hash=hash_password("verysecure"), role="member")

        response = client.post(
            "/login",
            data={"email": "USER@x.com", "password": "verysecure"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "session=" in response.headers["set-cookie"].lower()


def test_login_wrong_password_and_missing_email_share_error(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        db = get_db()
        init_schema(db)
        insert_user(db, name="User", email="user@x.com", password_hash=hash_password("verysecure"), role="member")

        wrong_password = client.post("/login", data={"email": "user@x.com", "password": "badpass"})
        wrong_email = client.post("/login", data={"email": "ghost@x.com", "password": "badpass"})

    assert wrong_password.status_code == 401
    assert wrong_email.status_code == 401
    assert "Invalid email or password." in wrong_password.text
    assert wrong_password.text == wrong_email.text
    assert "set-cookie" not in wrong_password.headers
    assert "set-cookie" not in wrong_email.headers


def test_logout_clears_cookie_and_redirects(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        response = client.post("/logout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert "max-age=0" in response.headers["set-cookie"].lower()
