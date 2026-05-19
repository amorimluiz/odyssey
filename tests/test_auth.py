from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.auth import (
    clear_session_cookie,
    current_user,
    decode_token,
    hash_password,
    issue_token,
    require_admin,
    require_user,
    set_session_cookie,
    verify_password,
)
from app.config import get_settings


class DummyRequest:
    def __init__(self, cookies: dict[str, str] | None = None) -> None:
        self.cookies = cookies or {}


def test_hash_and_verify_password_round_trip() -> None:
    hashed = hash_password("plain-secret")
    assert verify_password("plain-secret", hashed) is True


def test_verify_password_rejects_different_plaintext() -> None:
    hashed = hash_password("plain-secret")
    assert verify_password("different-secret", hashed) is False


def test_issue_and_decode_token_round_trip(settings) -> None:
    token = issue_token(42, "member")
    raw_payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    payload = decode_token(token)

    assert raw_payload["sub"] == "42"
    assert payload is not None
    assert payload["sub"] == "42"
    assert int(payload["sub"]) == 42
    assert payload["role"] == "member"
    assert isinstance(payload["exp"], int)


def test_issue_token_emits_string_subject_claim(settings) -> None:
    token = issue_token(7, "admin")
    raw_payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])

    assert isinstance(raw_payload["sub"], str)
    assert raw_payload["sub"] == "7"


def test_decode_token_rejects_different_signing_key(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    get_settings.cache_clear()
    token = issue_token(1, "member")

    monkeypatch.setenv("SECRET_KEY", "b" * 32)
    get_settings.cache_clear()
    assert decode_token(token) is None


def test_decode_token_rejects_expired_token(settings) -> None:
    expired_payload = {
        "sub": 1,
        "role": "member",
        "exp": datetime.now(tz=timezone.utc) - timedelta(seconds=1),
    }
    token = jwt.encode(expired_payload, settings.secret_key, algorithm="HS256")
    assert decode_token(token) is None


def test_decode_token_rejects_malformed_input(settings) -> None:
    assert decode_token("not.a.jwt") is None


def test_current_user_absent_cookie_returns_none() -> None:
    request = DummyRequest(cookies={})
    assert current_user(request) is None


def test_current_user_valid_cookie_returns_payload(settings) -> None:
    token = issue_token(7, "admin")
    request = DummyRequest(cookies={"session": token})

    payload = current_user(request)
    assert payload is not None
    assert payload["sub"] == "7"
    assert payload["role"] == "admin"


def _build_auth_app() -> Starlette:
    async def member_page(request: Request) -> Response:
        gate = require_user(request)
        if isinstance(gate, Response):
            return gate
        return JSONResponse({"sub": gate["sub"], "role": gate["role"]})

    async def admin_page(request: Request) -> Response:
        gate = require_admin(request)
        if isinstance(gate, Response):
            return gate
        return JSONResponse({"sub": gate["sub"], "role": gate["role"]})

    async def set_cookie_page(request: Request) -> Response:
        response = Response("ok", status_code=200)
        set_session_cookie(response, issue_token(101, "member"))
        return response

    return Starlette(
        routes=[
            Route("/member", member_page),
            Route("/admin", admin_page),
            Route("/set-cookie", set_cookie_page),
        ]
    )


def test_require_user_redirects_to_login_without_cookie(settings) -> None:
    client = TestClient(_build_auth_app())

    response = client.get("/member", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/login"


def test_require_admin_returns_403_for_member(settings) -> None:
    client = TestClient(_build_auth_app())
    token = issue_token(5, "member")

    response = client.get("/admin", cookies={"session": token}, follow_redirects=False)

    assert response.status_code == 403


def test_set_session_cookie_attributes(settings, monkeypatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)

    client = TestClient(_build_auth_app())
    response = client.get("/set-cookie")

    cookie_header = response.headers["set-cookie"].lower()
    assert "session=" in cookie_header
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header
    assert "max-age=2592000" in cookie_header


def test_set_session_cookie_secure_in_production(settings, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    client = TestClient(_build_auth_app())

    response = client.get("/set-cookie")
    cookie_header = response.headers["set-cookie"].lower()
    assert "secure" in cookie_header


def test_clear_session_cookie_expires_cookie() -> None:
    response = Response("ok")
    clear_session_cookie(response)

    cookie_header = response.headers["set-cookie"].lower()
    assert "session=" in cookie_header
    assert "max-age=0" in cookie_header
