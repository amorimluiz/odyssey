"""House submission, listing, and voting components."""

from __future__ import annotations

from fasthtml.common import A, Button, Div, Form, H2, Img, Input, P, Span


def house_submit_form() -> Form:
    """Form that submits listing URLs and prepends new cards with HTMX."""
    return Form(
        Input(
            id="house-url",
            name="url",
            type="url",
            placeholder="https://www.airbnb.com/rooms/12345678",
            required=True,
            cls="text-input",
        ),
        Button("Adicionar casa", type="submit", cls="btn btn-primary"),
        hx_post="/houses",
        hx_target="#house-list",
        hx_swap="afterbegin",
        cls="house-submit-form",
    )


def vote_button(house: dict, is_voted: bool) -> Button:
    """Render HTMX vote toggle button fragment."""
    vote_count = int(house.get("vote_count", 0))
    label = "Votado" if is_voted else "Votar"
    btn_class = "btn house-card-vote-btn is-voted" if is_voted else "btn house-card-vote-btn"
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
        Img(src=image_url, alt=str(house.get("title", "Anúncio de casa")), cls="house-card-image")
        if image_url
        else Div("Imagem indisponível", cls="house-card-image house-card-image-placeholder")
    )
    description = str(house.get("description") or "").strip()
    short_description = description[:157] + "..." if len(description) > 160 else description

    source = str(house.get("source", "")).lower()
    source_label = "Airbnb" if source == "airbnb" else "Booking"
    source_class = "house-card-source badge-source-airbnb" if source == "airbnb" else "house-card-source badge-source-booking"

    card_classes = "house-card"
    if highlight:
        card_classes += " house-card-highlight"

    attrs = {}
    if oob:
        attrs["hx_swap_oob"] = "true"

    return Div(
        Div(image, cls="house-card-media"),
        Div(
            Span(source_label, cls=source_class),
            H2(str(house.get("title", "Anúncio sem título")), cls="house-card-title"),
            P(short_description, cls="house-card-description") if short_description else None,
            P(str(house["price"]), cls="house-card-price") if house.get("price") else None,
            Div(
                vote_button(house, is_voted),
                cls="house-card-vote-row",
            ),
            A(
                "Abrir anúncio",
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
