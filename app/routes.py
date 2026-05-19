"""Application route registrations."""

from __future__ import annotations

from hmac import compare_digest
from typing import Protocol

from fasthtml.common import Button, Div, FastHTML, Form, Input, Label, P
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from app.auth import clear_session_cookie, hash_password, issue_token, set_session_cookie, verify_password
from app.components import base_layout, error_fragment
from app.config import get_settings
from app.db import get_db, get_invite_token, get_user_by_email, insert_user


class RoutesRegistrar(Protocol):
    """Callable contract used by the app factory to register routes."""

    def __call__(self, app: FastHTML) -> None: ...


def register_routes(app: FastHTML) -> None:
    """Register task-specific business routes on the provided app instance."""

    def _register_form(token: str, *, disabled: bool, error_message: str | None = None) -> Div:
        error_node = error_fragment(error_message) if error_message else None
        return Div(
            error_node,
            Form(
                Label("Name", fr="name"),
                Input(id="name", name="name", type="text", required=True, disabled=disabled),
                Label("Email", fr="email"),
                Input(id="email", name="email", type="email", required=True, disabled=disabled),
                Label("Password", fr="password"),
                Input(id="password", name="password", type="password", required=True, disabled=disabled),
                Input(name="token", type="hidden", value=token),
                Button("Create account", type="submit", disabled=disabled),
                method="post",
                action="/register",
            ),
        )

    def _login_form(*, error_message: str | None = None) -> Div:
        error_node = error_fragment(error_message) if error_message else None
        return Div(
            error_node,
            Form(
                Label("Email", fr="email"),
                Input(id="email", name="email", type="email", required=True),
                Label("Password", fr="password"),
                Input(id="password", name="password", type="password", required=True),
                Button("Login", type="submit"),
                method="post",
                action="/login",
            ),
        )

    @app.get("/invite/{token}")
    async def invite_page(request: Request, token: str):
        db = get_db()
        stored_token = get_invite_token(db) or ""
        token_ok = bool(stored_token) and compare_digest(stored_token, token)
        body = _register_form(token, disabled=not token_ok)
        status_code = 200 if token_ok else 403
        return Response(content=str(base_layout(body, request=request, title="Register")), status_code=status_code)

    @app.post("/register")
    async def register(request: Request):
        form = await request.form()
        token = str(form.get("token", ""))
        name = str(form.get("name", "")).strip()
        email = str(form.get("email", "")).strip().lower()
        password = str(form.get("password", ""))

        db = get_db()
        stored_token = get_invite_token(db) or ""
        token_ok = bool(stored_token) and compare_digest(stored_token, token)
        if not token_ok:
            body = _register_form(token, disabled=True)
            return Response(content=str(base_layout(body, request=request, title="Register")), status_code=403)

        if len(password) < 8:
            body = _register_form(token, disabled=False, error_message="Password must be at least 8 characters.")
            return Response(content=str(base_layout(body, request=request, title="Register")), status_code=422)

        if get_user_by_email(db, email) is not None:
            body = _register_form(token, disabled=False, error_message="Email is already registered.")
            return Response(content=str(base_layout(body, request=request, title="Register")), status_code=409)

        settings = get_settings()
        if settings.admin_email and settings.admin_email.strip().lower() == email:
            role = "admin"
        elif db["users"].count == 0:
            role = "admin"
        else:
            role = "member"

        user_id = insert_user(
            db,
            name=name,
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        response = RedirectResponse(url="/", status_code=303)
        set_session_cookie(response, issue_token(user_id, role))
        return response

    @app.get("/login")
    async def login_page(request: Request):
        return base_layout(_login_form(), request=request, title="Login")

    @app.post("/login")
    async def login(request: Request):
        form = await request.form()
        email = str(form.get("email", "")).strip().lower()
        password = str(form.get("password", ""))
        user = get_user_by_email(get_db(), email)

        generic_error = "Invalid email or password."
        if user is None or not verify_password(password, str(user.get("password_hash", ""))):
            return Response(
                content=str(base_layout(_login_form(error_message=generic_error), request=request, title="Login")),
                status_code=401,
            )

        response = RedirectResponse(url="/", status_code=303)
        set_session_cookie(response, issue_token(int(user["id"]), str(user["role"])))
        return response

    @app.post("/logout")
    async def logout() -> RedirectResponse:
        response = RedirectResponse(url="/login", status_code=303)
        clear_session_cookie(response)
        return response
