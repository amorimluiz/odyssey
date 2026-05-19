"""Application route registrations."""

from __future__ import annotations

from hmac import compare_digest
import logging
import uuid
from typing import Protocol

from fasthtml.common import A, Button, Div, FastHTML, Form, Input, Label, P, to_xml
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from app.auth import clear_session_cookie, current_user, hash_password, issue_token, require_admin, require_user, set_session_cookie, verify_password
from app.components import admin_panel, base_layout, error_fragment, house_card, house_submit_form, invite_link_fragment, vote_button
from app.config import get_settings
from app.db import count_users, count_votes_for_house, get_db, get_house_by_external_id, get_house_by_id, get_invite_token, get_user_by_username, houses_ranked, insert_house, insert_user, list_users, set_invite_token, slugify, toggle_vote, user_voted_house_ids
from app import scraper

logger = logging.getLogger(__name__)


class RoutesRegistrar(Protocol):
    """Callable contract used by the app factory to register routes."""

    def __call__(self, app: FastHTML) -> None: ...


def register_routes(app: FastHTML) -> None:
    """Register task-specific business routes on the provided app instance."""

    def _html_response(body, request: Request, *, title: str, status_code: int = 200) -> HTMLResponse:
        return HTMLResponse(content=str(base_layout(body, request=request, title=title)), status_code=status_code)

    def _register_form(
        token: str | None,
        *,
        disabled: bool,
        error_message: str | None = None,
        name: str = "",
        username: str = "",
        password: str = "",
    ) -> Div:
        error_node = error_fragment(error_message) if error_message else None
        form_children = [
            Label("Name", fr="name", cls="form-label"),
            Input(
                id="name", name="name", type="text", required=True, disabled=disabled, cls="text-input",
                hx_get="/username-preview",
                hx_trigger="input changed delay:300ms",
                hx_target="#username",
                hx_swap="outerHTML",
                value=name,
            ),
            Label("Username", fr="username", cls="form-label"),
            Input(id="username", name="username", type="text", required=True, disabled=disabled, cls="text-input", value=username),
            Label("Password", fr="password", cls="form-label"),
            Input(id="password", name="password", type="password", required=True, disabled=disabled, cls="text-input", value=password),
        ]
        if token is not None:
            form_children.append(Input(name="token", type="hidden", value=token))
        form_children.append(Button("Create account", type="submit", disabled=disabled, cls="btn btn-primary"))
        return Div(
            error_node,
            Form(*form_children, method="post", action="/register", cls="auth-form"),
            cls="auth-panel",
        )

    def _login_form(*, error_message: str | None = None, setup_link: bool = False) -> Div:
        error_node = error_fragment(error_message) if error_message else None
        helper = P(
            "First time here? Create the initial admin at ",
            A("/setup", href="/setup"),
            ".",
            cls="auth-hint",
        ) if setup_link else None
        return Div(
            error_node,
            helper,
            Form(
                Label("Username", fr="username", cls="form-label"),
                Input(id="username", name="username", type="text", required=True, cls="text-input"),
                Label("Password", fr="password", cls="form-label"),
                Input(id="password", name="password", type="password", required=True, cls="text-input"),
                Button("Login", type="submit", cls="btn btn-primary"),
                method="post",
                action="/login",
                cls="auth-form",
            ),
            cls="auth-panel",
        )

    @app.get("/username-preview")
    async def username_preview(request: Request):
        name = str(request.query_params.get("name", ""))
        slug = slugify(name)
        return HTMLResponse(content=to_xml(Input(id="username", name="username", type="text", value=slug, cls="text-input", required=True)))

    @app.get("/invite/{token}")
    async def invite_page(request: Request, token: str):
        db = get_db()
        stored_token = get_invite_token(db) or ""
        token_ok = bool(stored_token) and compare_digest(stored_token, token)
        body = _register_form(
            token,
            disabled=not token_ok,
            error_message=(
                "This invite link is invalid or has been rotated. Ask your organizer for a new one."
                if not token_ok
                else None
            ),
        )
        status_code = 200 if token_ok else 403
        return _html_response(body, request, title="Register", status_code=status_code)

    @app.get("/setup")
    async def setup_page(request: Request):
        db = get_db()
        if count_users(db) > 0:
            user = current_user(request)
            if user is None:
                return RedirectResponse(url="/login", status_code=303)
            if user.get("role") == "admin":
                return RedirectResponse(url="/admin", status_code=303)
            return RedirectResponse(url="/", status_code=303)

        body = Div(
            P("Create the first admin account.", cls="auth-hint"),
            _register_form(None, disabled=False),
            cls="setup-panel",
        )
        return _html_response(body, request, title="Setup")

    @app.post("/register")
    async def register(request: Request):
        form = await request.form()
        token = str(form.get("token", ""))
        name = str(form.get("name", "")).strip()
        username = slugify(str(form.get("username", "")).strip())
        password = str(form.get("password", ""))

        db = get_db()
        user_count = count_users(db)
        stored_token = get_invite_token(db) or ""
        token_ok = user_count == 0 or (bool(stored_token) and compare_digest(stored_token, token))
        if not token_ok:
            body = _register_form(token, disabled=True)
            return _html_response(body, request, title="Register", status_code=403)

        if len(password) < 8:
            body = _register_form(
                token,
                disabled=False,
                error_message="Password must be at least 8 characters.",
                name=name,
                username=username,
                password=password,
            )
            return _html_response(body, request, title="Register", status_code=422)

        if get_user_by_username(db, username) is not None:
            body = _register_form(
                token,
                disabled=False,
                error_message="This username is already taken — please choose a different one.",
                name=name,
                username=username,
                password=password,
            )
            return _html_response(body, request, title="Register", status_code=409)

        role = "admin" if user_count == 0 else "member"

        user_id = insert_user(
            db,
            name=name,
            username=username,
            password_hash=hash_password(password),
            role=role,
        )
        if role == "admin" and not stored_token:
            set_invite_token(db, uuid.uuid4().hex)
        response = RedirectResponse(url="/", status_code=303)
        set_session_cookie(response, issue_token(user_id, role))
        return response

    @app.get("/login")
    async def login_page(request: Request):
        db = get_db()
        return _html_response(_login_form(setup_link=count_users(db) == 0), request, title="Login")

    @app.post("/login")
    async def login(request: Request):
        form = await request.form()
        username = str(form.get("username", "")).strip()
        password = str(form.get("password", ""))
        user = get_user_by_username(get_db(), username)

        generic_error = "Invalid username or password."
        if user is None or not verify_password(password, str(user.get("password_hash", ""))):
            return _html_response(_login_form(error_message=generic_error), request, title="Login", status_code=401)

        response = RedirectResponse(url="/", status_code=303)
        set_session_cookie(response, issue_token(int(user["id"]), str(user["role"])))
        return response

    @app.post("/logout")
    async def logout() -> RedirectResponse:
        response = RedirectResponse(url="/login", status_code=303)
        clear_session_cookie(response)
        return response

    @app.get("/")
    async def home(request: Request):
        user_or_response = require_user(request)
        if isinstance(user_or_response, Response):
            return user_or_response

        db = get_db()
        houses = houses_ranked(db)
        voted_ids = user_voted_house_ids(db, int(user_or_response["sub"]))
        if houses:
            list_content = [house_card(house, is_voted=int(house["id"]) in voted_ids) for house in houses]
        else:
            list_content = [P("Paste an Airbnb or Booking URL above to get started", cls="house-list-empty")]

        return base_layout(
            house_submit_form(),
            Div(*list_content, id="house-list", cls="house-list"),
            request=request,
            title="Group House Voting",
        )

    @app.post("/houses")
    async def submit_house(request: Request):
        user_or_response = require_user(request)
        if isinstance(user_or_response, Response):
            return user_or_response

        form = await request.form()
        raw_url = str(form.get("url", "")).strip()
        parsed = scraper.parse_url(raw_url)
        if parsed is None:
            logger.info("scraper outcome=parse_fail url=%s", raw_url)
            return HTMLResponse(
                content=str(error_fragment("Only Airbnb and Booking URLs are supported.")),
                status_code=422,
            )

        db = get_db()
        existing = get_house_by_external_id(db, parsed.source, parsed.external_id)
        if existing is not None:
            existing_with_votes = dict(existing)
            existing_with_votes["vote_count"] = 0
            return (Div(), house_card(existing_with_votes, highlight=True, oob=True))

        og_data = await scraper.fetch_og(parsed.normalized)
        fetch_meta = scraper.last_fetch_meta()
        if og_data is None:
            logger.error(
                "scraper outcome=og_fail url=%s status=%s elapsed_ms=%s",
                parsed.normalized,
                fetch_meta.get("status", "unknown"),
                fetch_meta.get("elapsed_ms", 0),
            )
            return HTMLResponse(
                content=str(error_fragment("Could not fetch listing metadata.", retryable=True)),
                status_code=502,
            )

        logger.info(
            "scraper outcome=success url=%s status=%s elapsed_ms=%s",
            parsed.normalized,
            fetch_meta.get("status", "unknown"),
            fetch_meta.get("elapsed_ms", 0),
        )
        house_id = insert_house(
            db,
            source=parsed.source,
            external_id=parsed.external_id,
            url=parsed.normalized,
            title=og_data.title,
            image_url=og_data.image_url,
            description=og_data.description,
            price=og_data.price,
            submitted_by=int(user_or_response["sub"]),
        )
        return house_card(
            {
                "id": house_id,
                "source": parsed.source,
                "external_id": parsed.external_id,
                "url": parsed.normalized,
                "title": og_data.title,
                "image_url": og_data.image_url,
                "description": og_data.description,
                "price": og_data.price,
                "vote_count": 0,
            },
            is_voted=False,
        )

    @app.post("/houses/{house_id}/vote")
    async def toggle_house_vote(request: Request, house_id: int):
        user = current_user(request)
        if user is None:
            return Response(content="Unauthorized", status_code=401)

        db = get_db()
        house = get_house_by_id(db, house_id)
        if house is None:
            return Response(content="House not found", status_code=404)

        is_voted = toggle_vote(db, int(user["sub"]), house_id)
        house["vote_count"] = count_votes_for_house(db, house_id)
        return vote_button(house, is_voted)

    @app.get("/admin")
    async def admin_page(request: Request):
        admin_or_response = require_admin(request)
        if isinstance(admin_or_response, Response):
            return admin_or_response

        db = get_db()
        token = get_invite_token(db) or ""
        members = list_users(db)
        return base_layout(
            admin_panel(invite_url=_invite_url(request, token), members=members),
            request=request,
            title="Admin",
        )

    @app.post("/admin/rotate-invite")
    async def rotate_invite(request: Request):
        admin_or_response = require_admin(request)
        if isinstance(admin_or_response, Response):
            return admin_or_response

        db = get_db()
        new_token = uuid.uuid4().hex
        set_invite_token(db, new_token)
        logger.info(
            "event=invite_rotated admin_user_id=%s",
            admin_or_response.get("sub"),
        )
        return invite_link_fragment(_invite_url(request, new_token))
    def _invite_base_url(request: Request) -> str:
        settings = get_settings()
        if settings.base_url:
            return settings.base_url.rstrip("/")
        host = request.headers.get("host", "localhost")
        scheme = request.url.scheme or "http"
        return f"{scheme}://{host}"

    def _invite_url(request: Request, token: str) -> str:
        return f"{_invite_base_url(request)}/invite/{token}"
