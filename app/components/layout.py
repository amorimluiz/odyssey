"""Layout and navigation components."""

from __future__ import annotations

from fasthtml.common import A, Body, Button, Div, Form, H1, Head, Header, Html, Link, Meta, Nav, Script, Title
from starlette.requests import Request

from app.auth import current_user

HTMX_CDN = "https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js"
HTMX_INTEGRITY = "sha384-H5SrcfygHmAuTDZphMHqBJLc3FhssKjG7w/CeCpFReSfwBWDTKpkzPP8c+cLsK+V"
HTMX_RESPONSE_HANDLING = (
    '{"responseHandling":['
    '{"code":"204","swap":false},'
    '{"code":"[23]..","swap":true},'
    '{"code":"422|502","swap":true,"error":true},'
    '{"code":"[45]..","swap":false,"error":true},'
    '{"code":"...","swap":true}'
    "]}"
)


def nav_header(request: Request | None) -> Header:
    """Render top navigation links according to user auth state."""
    user = current_user(request) if request is not None else None
    links = [A("Início", href="/")]

    if user is None:
        links.append(A("Entrar", href="/login"))
    else:
        if user.get("role") == "admin":
            links.append(A("Administração", href="/admin"))
        links.append(
            Form(
                Button("Sair", type="submit", cls="nav-logout-button"),
                method="post",
                action="/logout",
                cls="nav-logout-form",
            )
        )

    return Header(
        Nav(*links, cls="nav-links"),
        cls="site-header",
    )


def base_layout(*content, request: Request | None = None, title: str | None = None) -> Html:
    """Render the base HTML shell with shared scripts and navigation."""
    page_title = title or "Votação de Casas do Grupo"
    return Html(
        Head(
            Title(page_title),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Meta(name="htmx-config", content=HTMX_RESPONSE_HANDLING),
            Link(rel="stylesheet", href="/static/style.css"),
            # Keep HTMX on CDN for now; task_10 can decide whether to vendor assets.
            Script(src=HTMX_CDN, integrity=HTMX_INTEGRITY, crossorigin="anonymous"),
        ),
        Body(
            nav_header(request),
            Div(
                H1(page_title, cls="page-title"),
                Div(*content, id="content"),
                cls="layout-shell",
            ),
            cls="app-body",
        ),
    )
