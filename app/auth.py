"""Authentication helpers for password hashing, JWT cookies, and route guards."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from app.config import get_settings

SESSION_COOKIE_NAME = "session"
SESSION_MAX_AGE_SECONDS = 30 * 86400

_password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash plaintext password using bcrypt."""
    return _password_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plaintext password against a bcrypt hash."""
    return _password_context.verify(plain, hashed)


def issue_token(user_id: int, role: str) -> str:
    """Issue an HS256 JWT with 30-day expiration."""
    settings = get_settings()
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=30)
    payload = {"sub": user_id, "role": role, "exp": expires_at}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode a JWT token and return payload if valid, otherwise None."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except (ExpiredSignatureError, InvalidTokenError, TypeError, ValueError):
        return None

    if not isinstance(payload, dict):
        return None
    return payload


def current_user(request: Request) -> dict[str, Any] | None:
    """Return decoded JWT payload from session cookie or None."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return decode_token(token)


def require_user(request: Request) -> dict[str, Any] | Response:
    """Return authenticated user payload or a 401 redirect response."""
    payload = current_user(request)
    if payload is None:
        return RedirectResponse(url="/login", status_code=307)
    return payload


def require_admin(request: Request) -> dict[str, Any] | Response:
    """Return admin payload or a forbidden/auth response."""
    user_or_response = require_user(request)
    if isinstance(user_or_response, Response):
        return user_or_response
    if user_or_response.get("role") != "admin":
        return Response(content="Forbidden", status_code=403)
    return user_or_response


def _cookie_secure_flag() -> bool:
    env = (os.getenv("APP_ENV") or os.getenv("ENV") or "").strip().lower()
    return env in {"prod", "production"}


def set_session_cookie(response: Response, token: str) -> None:
    """Set the JWT session cookie with shared security attributes."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure_flag(),
        max_age=SESSION_MAX_AGE_SECONDS,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Clear the JWT session cookie using the same path scope."""
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
