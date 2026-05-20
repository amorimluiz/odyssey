"""House submission, listing, voting, and modal components."""

from __future__ import annotations

from typing import Any

from fasthtml.common import A, Button, Div, Form, H2, Img, Input, Label, NotStr, P, Span


SEARCH_ICON_SVG = NotStr(
    '<svg class="house-submit-icon" viewBox="0 0 24 24" width="20" height="20" '
    'fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true" focusable="false">'
    '<circle cx="11" cy="11" r="7"></circle>'
    '<path d="M20 20l-3.5-3.5"></path>'
    "</svg>"
)

PLUS_ICON_SVG = NotStr(
    '<svg class="house-submit-icon" viewBox="0 0 24 24" width="20" height="20" '
    'fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true" focusable="false">'
    '<path d="M12 5v14M5 12h14"></path>'
    "</svg>"
)


MODAL_FOCUS_RETURN_JS = "window.__houseModalTrigger?.focus?.(); window.__houseModalTrigger = null;"
MODAL_INITIAL_FOCUS_JS = "setTimeout(() => this.querySelector('#title')?.focus(), 10);"
MODAL_CLOSE_JS = (
    "const modal = this.closest('#house-modal'); "
    "if (modal) modal.outerHTML = '<div id=\"house-modal\" class=\"house-modal-host\"></div>'; "
    f"{MODAL_FOCUS_RETURN_JS}"
)
MODAL_BACKDROP_CLICK_JS = f"if (event.target !== this) return; {MODAL_CLOSE_JS}"
MODAL_PANEL_CLICK_JS = "event.stopPropagation();"
MODAL_KEYDOWN_JS = (
    "if (event.key === 'Escape') { "
    "event.preventDefault(); "
    f"{MODAL_CLOSE_JS} "
    "return; "
    "} "
    "if (event.key !== 'Tab') return; "
    "const focusables = Array.from(this.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex=\"-1\"])'))"
    ".filter((el) => !el.hasAttribute('disabled') && !el.hasAttribute('hidden')); "
    "if (focusables.length === 0) { "
    "event.preventDefault(); "
    "return; "
    "} "
    "const first = focusables[0]; "
    "const last = focusables[focusables.length - 1]; "
    "if (event.shiftKey && document.activeElement === first) { "
    "event.preventDefault(); "
    "last.focus(); "
    "} else if (!event.shiftKey && document.activeElement === last) { "
    "event.preventDefault(); "
    "first.focus(); "
    "} "
)


def _field_value(house: dict[str, Any], field: str) -> dict[str, str]:
    value = str(house.get(field, "") or "").strip()
    return {"value": value} if value else {}


def house_submit_form() -> Div:
    """Render the scraper form, manual entry trigger, and modal host."""
    return Div(
        Form(
            Div(
                Input(
                    id="house-url",
                    name="url",
                    type="url",
                    placeholder="https://www.airbnb.com/rooms/12345678",
                    required=True,
                    cls="text-input house-submit-input",
                ),
                Button(
                    SEARCH_ICON_SVG,
                    type="submit",
                    aria_label="Adicionar casa pela URL",
                    cls="btn house-submit-icon-btn",
                ),
                Button(
                    PLUS_ICON_SVG,
                    type="button",
                    aria_label="Cadastrar manualmente",
                    hx_get="/houses/manual/new",
                    hx_target="#house-modal",
                    hx_swap="outerHTML",
                    hx_on_click="window.__houseModalTrigger = this",
                    cls="btn house-submit-icon-btn",
                ),
                cls="house-submit-row",
            ),
            hx_post="/houses",
            hx_target="#house-list",
            hx_swap="afterbegin",
            cls="house-submit-form",
        ),
        Div(id="house-modal", cls="house-modal-host"),
        cls="house-submit-stack",
    )


def house_manual_form(
    *,
    action: str,
    method: str,
    target: str,
    swap: str,
    submit_label: str,
    house: dict[str, Any] | None = None,
) -> Form:
    """Render the shared manual house form for create and edit flows."""
    house = house or {}
    method = method.lower()
    form_attrs = {"hx_target": target, "hx_swap": swap, f"hx_{method}": action}

    return Form(
        Label("Título", fr="title", cls="form-label"),
        Input(id="title", name="title", type="text", required=True, autofocus=True, cls="text-input", **_field_value(house, "title")),
        Label("URL", fr="url", cls="form-label"),
        Input(id="url", name="url", type="url", required=True, cls="text-input", **_field_value(house, "url")),
        Label("URL da imagem", fr="image_url", cls="form-label"),
        Input(id="image_url", name="image_url", type="url", cls="text-input", **_field_value(house, "image_url")),
        Label("Descrição", fr="description", cls="form-label"),
        Input(id="description", name="description", type="text", cls="text-input", **_field_value(house, "description")),
        Label("Preço", fr="price", cls="form-label"),
        Input(id="price", name="price", type="text", cls="text-input", **_field_value(house, "price")),
        Button(submit_label, type="submit", cls="btn btn-primary"),
        cls="house-form",
        **form_attrs,
    )


def house_modal_shell(title: str, form: Form, *, description: str | None = None) -> Div:
    """Wrap a shared form in a modal shell with accessible labelling."""
    return Div(
        Div(
            H2(title, id="house-modal-title", cls="house-modal-title"),
            P(description, cls="house-modal-description") if description else None,
            form,
            cls="house-modal-panel",
            tabindex="-1",
            hx_on_click=MODAL_PANEL_CLICK_JS,
            hx_on_keydown=MODAL_KEYDOWN_JS,
        ),
        id="house-modal",
        role="dialog",
        aria_modal="true",
        aria_labelledby="house-modal-title",
        cls="house-modal",
        hx_on_click=MODAL_BACKDROP_CLICK_JS,
        hx_on__after_swap=MODAL_INITIAL_FOCUS_JS,
    )


def house_modal_clear() -> Div:
    """Render the out-of-band modal host used to clear the dialog and restore focus."""
    return Div(
        id="house-modal",
        cls="house-modal-host",
        hx_swap_oob="true",
        hx_on__after_swap=MODAL_FOCUS_RETURN_JS,
    )


def vote_button(house: dict, is_voted: bool) -> Div:
    """Render HTMX vote toggle cell: heart button + adjacent count outside the click target."""
    house_id = house.get("id")
    vote_count = int(house.get("vote_count", 0))
    btn_class = "house-card-vote-btn is-voted" if is_voted else "house-card-vote-btn is-neutral"
    icon = "♥" if is_voted else "♡"
    label = "Remover voto desta casa" if is_voted else "Votar nesta casa"
    cell_id = f"vote-cell-{house_id}"
    return Div(
        Button(
            Span(icon, aria_hidden="true", cls="house-card-vote-icon"),
            type="button",
            id=f"vote-button-{house_id}",
            aria_label=label,
            aria_pressed="true" if is_voted else "false",
            hx_post=f"/houses/{house_id}/vote",
            hx_target=f"#{cell_id}",
            hx_swap="outerHTML",
            cls=btn_class,
        ),
        Span(str(vote_count), cls="house-card-vote-count"),
        id=cell_id,
        cls="house-card-vote",
    )


def house_card(
    house: dict,
    *,
    is_voted: bool = False,
    can_edit: bool = True,
    can_delete: bool = False,
    highlight: bool = False,
    oob: bool = False,
) -> Div:
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
    if source == "manual":
        source_label = "Manual"
        source_class = "house-card-source badge-source-manual"

    actions: list[Any] = []
    house_id = house.get("id")
    if can_edit and house_id is not None:
        actions.append(
            Button(
                Span("✎", aria_hidden="true", cls="house-card-action-icon"),
                type="button",
                aria_label="Editar casa",
                hx_get=f"/houses/{house_id}/edit",
                hx_target="#house-modal",
                hx_swap="outerHTML",
                hx_on_click="window.__houseModalTrigger = this",
                cls="house-card-action house-card-icon-btn",
            )
        )
    if can_delete and house_id is not None:
        actions.append(
            Button(
                Span("🗑", aria_hidden="true", cls="house-card-action-icon"),
                type="button",
                aria_label="Excluir casa",
                hx_delete=f"/houses/{house_id}",
                hx_target=f"#house-{house_id}",
                hx_swap="delete",
                hx_confirm="Tem certeza que deseja excluir esta casa?",
                cls="house-card-action house-card-icon-btn house-card-action-danger",
            )
        )
    actions.append(vote_button(house, is_voted))

    card_classes = "house-card"
    if highlight:
        card_classes += " house-card-highlight"

    attrs = {}
    if oob:
        attrs["hx_swap_oob"] = "true"

    price_value = str(house.get("price") or "").strip()
    footer_children: list[Any] = []
    if price_value:
        footer_children.append(P(price_value, cls="house-card-price"))
    footer_children.append(Div(*actions, cls="house-card-actions"))

    return Div(
        Div(image, cls="house-card-media"),
        Div(
            A(
                Span(source_label, cls=source_class),
                H2(str(house.get("title", "Anúncio sem título")), cls="house-card-title"),
                P(short_description, cls="house-card-description") if short_description else None,
                href=str(house.get("url", "#")),
                rel="noopener noreferrer",
                target="_blank",
                cls="house-card-link",
            ),
            cls="house-card-content",
        ),
        Div(*footer_children, cls="house-card-action-zone"),
        id=f'house-{house.get("id")}',
        cls=card_classes,
        **attrs,
    )
