from __future__ import annotations

import importlib

from bs4 import BeautifulSoup
from starlette.testclient import TestClient

from app.auth import hash_password
from app.db import get_db, get_invite_token, init_schema, insert_user, set_invite_token


def _build_client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    import main

    importlib.reload(main)
    return TestClient(main.create_app())


def _seed_invite(token: str) -> None:
    db = get_db()
    init_schema(db)
    set_invite_token(db, token)


def _assert_html_response(response) -> None:
    assert response.headers["content-type"].startswith("text/html")


# --- /invite route tests ---

def test_get_invite_valid_returns_form(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")

        response = client.get("/invite/invite-ok")

    assert response.status_code == 200
    _assert_html_response(response)
    assert "Create account" in response.text
    soup = BeautifulSoup(response.text, "html.parser")
    assert len(soup.find_all("form")) == 1
    assert soup.find("input", {"name": "token", "value": "invite-ok"}) is not None


def test_get_invite_invalid_returns_403_same_shell(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")

        bad = client.get("/invite/bad-token")
        other_bad = client.get("/invite/another-bad")

    assert bad.status_code == 403
    assert other_bad.status_code == 403
    _assert_html_response(bad)
    _assert_html_response(other_bad)
    assert "Create account" in bad.text
    assert "disabled" in bad.text
    assert "disabled" in other_bad.text
    assert "Create account" in other_bad.text
    soup = BeautifulSoup(bad.text, "html.parser")
    alert = soup.find(attrs={"role": "alert"})
    assert alert is not None
    assert "This invite link is invalid or has been rotated. Ask your organizer for a new one." in alert.get_text(" ", strip=True)


def test_get_invite_valid_does_not_render_alert(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")

        response = client.get("/invite/invite-ok")

    assert response.status_code == 200
    _assert_html_response(response)
    soup = BeautifulSoup(response.text, "html.parser")
    assert soup.find(attrs={"role": "alert"}) is None


# --- /username-preview route tests ---

def test_username_preview_plain_ascii(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        response = client.get("/username-preview", params={"name": "Alice"})

    assert response.status_code == 200
    assert 'id="username"' in response.text
    assert 'value="alice"' in response.text


def test_username_preview_accented_name(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        response = client.get("/username-preview", params={"name": "João Silva"})

    assert response.status_code == 200
    assert 'id="username"' in response.text
    assert 'value="joao-silva"' in response.text


def test_username_preview_special_characters(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        response = client.get("/username-preview", params={"name": "Ça va?"})

    assert response.status_code == 200
    assert 'id="username"' in response.text
    assert 'value="ca-va"' in response.text


def test_username_preview_empty_name(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        response = client.get("/username-preview", params={"name": ""})

    assert response.status_code == 200
    assert 'id="username"' in response.text
    assert 'value=""' in response.text


# --- /register route tests ---

def test_register_persists_slugified_username_and_redirects(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")

        response = client.post(
            "/register",
            data={"name": "Alice", "username": "alice", "password": "supersecure", "token": "invite-ok"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "session=" in response.headers["set-cookie"].lower()
    db = get_db()
    row = list(db.query("SELECT username FROM users LIMIT 1"))[0]
    assert row["username"] == "alice"


def test_register_edited_username_overrides_slug(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")

        response = client.post(
            "/register",
            data={"name": "Alice", "username": "custom-name", "password": "supersecure", "token": "invite-ok"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    db = get_db()
    row = list(db.query("SELECT username FROM users LIMIT 1"))[0]
    assert row["username"] == "custom-name"


def test_register_cookie_round_trip_reaches_home(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")

        register_response = client.post(
            "/register",
            data={"name": "Alice", "username": "alice", "password": "supersecure", "token": "invite-ok"},
            follow_redirects=False,
        )
        session_cookie = register_response.cookies.get("session")
        assert session_cookie is not None

        home_response = client.get("/", cookies={"session": session_cookie}, follow_redirects=False)

    assert register_response.status_code == 303
    assert home_response.status_code == 200
    _assert_html_response(home_response)
    assert "Paste an Airbnb or Booking URL above to get started" in home_response.text
    assert "/login" not in home_response.headers.get("location", "")


def test_register_short_password_rejected_without_insert(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")

        response = client.post(
            "/register",
            data={"name": "Bob", "username": "bob", "password": "short", "token": "invite-ok"},
        )

    assert response.status_code == 422
    _assert_html_response(response)
    assert "Password must be at least 8 characters." in response.text
    db = get_db()
    assert db["users"].count == 0


def test_register_duplicate_username_shows_error(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")
        client.post(
            "/register",
            data={"name": "One", "username": "dup-user", "password": "verysecure", "token": "invite-ok"},
            follow_redirects=False,
        )

        response = client.post(
            "/register",
            data={"name": "Two", "username": "dup-user", "password": "anothervalue", "token": "invite-ok"},
        )

    assert response.status_code == 409
    _assert_html_response(response)
    assert "This username is already taken — please choose a different one." in response.text
    assert get_db()["users"].count == 1


def test_register_first_user_is_admin(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")
        client.post(
            "/register",
            data={"name": "First", "username": "first-user", "password": "verysecure", "token": "invite-ok"},
            follow_redirects=False,
        )

    db = get_db()
    user = list(db.query("SELECT role FROM users LIMIT 1"))[0]
    assert user["role"] == "admin"


def test_register_second_user_is_member(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")
        db = get_db()
        insert_user(db, name="Existing", username="existing", password_hash=hash_password("existingpass"), role="admin")

        client.post(
            "/register",
            data={"name": "Second", "username": "second-user", "password": "verysecure", "token": "invite-ok"},
            follow_redirects=False,
        )

    db = get_db()
    second = list(db.query("SELECT role FROM users WHERE username = ?", ["second-user"]))[0]
    assert second["role"] == "member"


def test_register_role_assignment_independent_of_admin_email(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ADMIN_EMAIL", "ignored@example.com")
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("invite-ok")
        client.post(
            "/register",
            data={"name": "First", "username": "first-user", "password": "verysecure", "token": "invite-ok"},
            follow_redirects=False,
        )

    db = get_db()
    user = list(db.query("SELECT role FROM users LIMIT 1"))[0]
    assert user["role"] == "admin"


def test_register_rotated_token_rejected(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        _seed_invite("old-token")
        db = get_db()
        set_invite_token(db, "new-token")

        response = client.post(
            "/register",
            data={"name": "Alice", "username": "alice", "password": "verysecure", "token": "old-token"},
        )

    assert response.status_code == 403
    _assert_html_response(response)
    assert get_invite_token(get_db()) == "new-token"


# --- /login route tests ---

def test_login_success_sets_cookie(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        db = get_db()
        init_schema(db)
        insert_user(db, name="User", username="user", password_hash=hash_password("verysecure"), role="member")

        response = client.post(
            "/login",
            data={"username": "user", "password": "verysecure"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "session=" in response.headers["set-cookie"].lower()


def test_login_cookie_round_trip_reaches_home(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        db = get_db()
        init_schema(db)
        insert_user(db, name="User", username="user", password_hash=hash_password("verysecure"), role="member")

        login_response = client.post(
            "/login",
            data={"username": "user", "password": "verysecure"},
            follow_redirects=False,
        )
        session_cookie = login_response.cookies.get("session")
        assert session_cookie is not None

        home_response = client.get("/", cookies={"session": session_cookie}, follow_redirects=False)

    assert login_response.status_code == 303
    assert home_response.status_code == 200
    _assert_html_response(home_response)
    assert "Paste an Airbnb or Booking URL above to get started" in home_response.text


def test_login_unknown_username_returns_error(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        db = get_db()
        init_schema(db)
        insert_user(db, name="User", username="user", password_hash=hash_password("verysecure"), role="member")

        response = client.post("/login", data={"username": "ghost", "password": "badpass"})

    assert response.status_code == 401
    _assert_html_response(response)
    assert "Invalid username or password." in response.text
    assert "set-cookie" not in response.headers


def test_login_wrong_password_returns_same_error(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        db = get_db()
        init_schema(db)
        insert_user(db, name="User", username="user", password_hash=hash_password("verysecure"), role="member")

        response = client.post("/login", data={"username": "user", "password": "wrongpass"})

    assert response.status_code == 401
    _assert_html_response(response)
    assert "Invalid username or password." in response.text
    assert "set-cookie" not in response.headers


def test_login_case_insensitive_username(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        db = get_db()
        init_schema(db)
        insert_user(db, name="User", username="alice", password_hash=hash_password("verysecure"), role="member")

        response = client.post(
            "/login",
            data={"username": "ALICE", "password": "verysecure"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_logout_clears_cookie_and_redirects(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        response = client.post("/logout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert "max-age=0" in response.headers["set-cookie"].lower()
