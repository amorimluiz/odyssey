"""Shared FastHTML components used across route modules."""

from __future__ import annotations

from fasthtml.common import A, Body, Button, Div, Form, H1, H2, Head, Header, Html, Img, Input, Nav, P, Script, Span, Title
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


def house_submit_form() -> Form:
    """Form that submits listing URLs and prepends new cards with HTMX."""
    return Form(
        Input(
            id="house-url",
            name="url",
            type="url",
            placeholder="https://www.airbnb.com/rooms/12345678",
            required=True,
        ),
        Button("Add house", type="submit"),
        hx_post="/houses",
        hx_target="#house-list",
        hx_swap="afterbegin",
        cls="house-submit-form",
    )


def vote_button(house: dict, is_voted: bool) -> Button:
    """Render HTMX vote toggle button fragment."""
    vote_count = int(house.get("vote_count", 0))
    label = "Voted" if is_voted else "Vote"
    btn_class = "house-card-vote-btn is-voted" if is_voted else "house-card-vote-btn"
    return Button(
        f"{label} ({vote_count})",
        type="button",
        id=f'vote-button-{house.get("id")}',
        aria_pressed="true" if is_voted else "false",
        hx_post=f'/houses/{house.get("id")}/vote',
        hx_target="this",
        hx_swap="outerHTML",
        cls=btn_class,
    )


def house_card(house: dict, *, is_voted: bool = False, highlight: bool = False, oob: bool = False) -> Div:
    """Render a reusable house card fragment for list and HTMX responses."""
    image_url = house.get("image_url")
    image = (
        Img(src=image_url, alt=str(house.get("title", "House listing")), cls="house-card-image")
        if image_url
        else Div("No image available", cls="house-card-image house-card-image-placeholder")
    )
    description = str(house.get("description") or "").strip()
    short_description = description[:157] + "..." if len(description) > 160 else description

    source = str(house.get("source", "")).lower()
    source_label = "Airbnb" if source == "airbnb" else "Booking"

    card_classes = "house-card"
    if highlight:
        card_classes += " house-card-highlight"

    attrs = {}
    if oob:
        attrs["hx_swap_oob"] = "true"

    return Div(
        Div(image, cls="house-card-media"),
        Div(
            Span(source_label, cls="house-card-source"),
            H2(str(house.get("title", "Untitled listing")), cls="house-card-title"),
            P(short_description, cls="house-card-description") if short_description else None,
            P(str(house["price"]), cls="house-card-price") if house.get("price") else None,
            Div(
                vote_button(house, is_voted),
                cls="house-card-vote-row",
            ),
            A(
                "Open listing",
                href=str(house.get("url", "#")),
                rel="noopener noreferrer",
                target="_blank",
                cls="house-card-link",
            ),
            cls="house-card-content",
        ),
        id=f'house-{house.get("id")}',
        cls=card_classes,
        **attrs,
    )


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
