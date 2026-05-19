"""Shared FastHTML components used across route modules."""

from __future__ import annotations

from fasthtml.common import A, Body, Div, H1, Head, Header, Html, Nav, Script, Span, Title
from starlette.requests import Request

from app.auth import current_user

HTMX_CDN = "https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js"
HTMX_INTEGRITY = "sha384-H5SrcfygHmAuTDZphMHqBJLc3FhssKjG7w/CeCpFReSfwBWDTKpkzPP8c+cLsK+V"


def nav_header(request: Request | None) -> Header:
    """Render top navigation links according to user auth state."""
    user = current_user(request) if request is not None else None
    links = [A("Home", href="/")]

    if user is None:
        links.append(A("Login", href="/login"))
    else:
        if user.get("role") == "admin":
            links.append(A("Admin", href="/admin"))
        links.append(A("Logout", href="/logout"))

    return Header(
        Nav(*links, cls="nav-links"),
        cls="site-header",
    )


def error_fragment(message: str, retryable: bool = False) -> Div:
    """Render inline error feedback for HTMX form fragments."""
    retry_hint = Div("Please retry in a few seconds.", cls="error-retry") if retryable else None
    children = [Span(message, cls="error-message")]
    if retry_hint is not None:
        children.append(retry_hint)
    return Div(*children, role="alert", cls="error-fragment")


def base_layout(*content, request: Request | None = None, title: str | None = None) -> Html:
    """Render the base HTML shell with shared scripts and navigation."""
    page_title = title or "Group House Voting"
    return Html(
        Head(
            Title(page_title),
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
        ),
    )
