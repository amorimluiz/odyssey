"""Layout and navigation components."""

from __future__ import annotations

from fasthtml.common import A, Body, Button, Div, Form, Head, Header, Html, Link, Meta, Nav, NotStr, Script, Title
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

_ICON_BASE = (
    'viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true" focusable="false"'
)

HOME_ICON_SVG = NotStr(
    f'<svg class="nav-icon" {_ICON_BASE}>'
    '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-7h-6v7H4a1 1 0 0 1-1-1z"></path>'
    "</svg>"
)

GEAR_ICON_SVG = NotStr(
    f'<svg class="nav-icon" {_ICON_BASE}>'
    '<circle cx="12" cy="12" r="3"></circle>'
    '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06'
    "a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51"
    " 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82"
    " 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82"
    "l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3"
    "a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83"
    "l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
    '"></path>'
    "</svg>"
)

LOGOUT_ICON_SVG = NotStr(
    f'<svg class="nav-icon" {_ICON_BASE}>'
    '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>'
    '<path d="M16 17l5-5-5-5"></path>'
    '<path d="M21 12H9"></path>'
    "</svg>"
)


def nav_header(request: Request | None) -> Header:
    """Render top navigation links according to user auth state."""
    user = current_user(request) if request is not None else None
    links = [A(HOME_ICON_SVG, href="/", aria_label="Início", title="Início", cls="nav-link")]

    if user is None:
        links.append(A("Entrar", href="/login", cls="nav-link nav-link-text"))
    else:
        if user.get("role") == "admin":
            links.append(
                A(
                    GEAR_ICON_SVG,
                    href="/admin",
                    aria_label="Administração",
                    title="Administração",
                    cls="nav-link",
                )
            )
        links.append(
            Form(
                Button(
                    LOGOUT_ICON_SVG,
                    type="submit",
                    aria_label="Sair",
                    title="Sair",
                    cls="nav-link nav-logout-button",
                ),
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
                Div(*content, id="content"),
                cls="layout-shell",
            ),
            cls="app-body",
        ),
    )
