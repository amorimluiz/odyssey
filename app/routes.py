"""Application route registrations."""

from __future__ import annotations

from hmac import compare_digest
import logging
from typing import Protocol

from fasthtml.common import Button, Div, FastHTML, Form, Input, Label, P
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from app.auth import clear_session_cookie, current_user, hash_password, issue_token, require_user, set_session_cookie, verify_password
from app.components import base_layout, error_fragment, house_card, house_submit_form, vote_button
from app.config import get_settings
from app.db import count_votes_for_house, get_db, get_house_by_external_id, get_house_by_id, get_invite_token, get_user_by_email, houses_ranked, insert_house, insert_user, toggle_vote, user_voted_house_ids
from app import scraper

logger = logging.getLogger(__name__)


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
            list_content = [P("Paste an Airbnb or Booking URL above to get started")]

        return base_layout(
            house_submit_form(),
            Div(*list_content, id="house-list"),
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
            return Response(
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
            return Response(
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
