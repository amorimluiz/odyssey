"""Application factory and top-level FastHTML wiring."""

from __future__ import annotations

import importlib
import logging
import time

from fasthtml.common import Beforeware, FastHTML
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.staticfiles import StaticFiles

from app.auth import SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS, _cookie_secure_flag, current_user
from app.config import get_settings
from app import db as app_db

logger = logging.getLogger(__name__)


def _load_routes(app: FastHTML) -> None:
    routes_module = importlib.import_module("app.routes")
    register = getattr(routes_module, "register_routes", None)
    if callable(register):
        register(app)


def create_app() -> FastHTML:
    settings = get_settings()

    def log_request_start(request: Request) -> None:
        request.scope["_request_started"] = time.perf_counter()
        user = current_user(request)
        request.scope["_request_user_id"] = str(user.get("sub")) if user else "anon"

    def log_request_end(request: Request, resp: Response | None = None) -> None:
        if resp is None:
            return None
        started = request.scope.get("_request_started", time.perf_counter())
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        user_id = request.scope.get("_request_user_id", "anon")
        status_code = resp.status_code if hasattr(resp, "status_code") else 200
        logger.info(
            "request method=%s path=%s user_id=%s status=%s latency_ms=%s",
            request.method,
            request.url.path,
            user_id,
            status_code,
            elapsed_ms,
        )

    app = FastHTML(
        secret_key=settings.secret_key,
        session_cookie=SESSION_COOKIE_NAME,
        max_age=SESSION_MAX_AGE_SECONDS,
        same_site="lax",
        sess_path="/",
        sess_https_only=_cookie_secure_flag(),
        before=Beforeware(log_request_start),
        after=log_request_end,
    )

    @app.on_event("startup")
    async def startup() -> None:
        db = app_db.get_db()
        app_db.init_schema(db)

    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/healthz")
    async def healthz() -> PlainTextResponse:
        return PlainTextResponse("ok")

    _load_routes(app)
    return app


app = create_app()
