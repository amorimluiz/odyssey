"""House submission, listing, voting, and modal components."""

from __future__ import annotations

from typing import Any

from fasthtml.common import A, Button, Div, Form, H2, Img, Input, Label, P, Span


MODAL_FOCUS_RETURN_JS = "window.__houseModalTrigger?.focus?.(); window.__houseModalTrigger = null;"
MODAL_INITIAL_FOCUS_JS = "setTimeout(() => this.querySelector('#title')?.focus(), 10);"
MODAL_KEYDOWN_JS = (
    "if (event.key === 'Escape') { "
    "event.preventDefault(); "
    "const modal = this.closest('#house-modal'); "
    "if (modal) modal.outerHTML = '<div id=\"house-modal\" class=\"house-modal-host\"></div>'; "
    f"{MODAL_FOCUS_RETURN_JS} "
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
        ),
        Div(
            Button(
                "Cadastrar manualmente",
                type="button",
                hx_get="/houses/manual/new",
                hx_target="#house-modal",
                hx_swap="outerHTML",
                hx_on_click="window.__houseModalTrigger = this",
                cls="btn btn-secondary",
            ),
            cls="house-submit-actions",
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
            hx_on_keydown=MODAL_KEYDOWN_JS,
        ),
        id="house-modal",
        role="dialog",
        aria_modal="true",
        aria_labelledby="house-modal-title",
        cls="house-modal",
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

    actions = []
    house_id = house.get("id")
    if can_edit and house_id is not None:
        actions.append(
            Button(
                "Editar",
                type="button",
                aria_label="Editar casa",
                hx_get=f"/houses/{house_id}/edit",
                hx_target="#house-modal",
                hx_swap="outerHTML",
                hx_on_click="window.__houseModalTrigger = this",
                cls="btn btn-secondary house-card-action",
            )
        )
    if can_delete and house_id is not None:
        actions.append(
            Button(
                "Excluir",
                type="button",
                aria_label="Excluir casa",
                hx_delete=f"/houses/{house_id}",
                hx_target=f"#house-{house_id}",
                hx_swap="delete",
                hx_confirm="Tem certeza que deseja excluir esta casa?",
                cls="btn btn-danger house-card-action house-card-action-danger",
            )
        )

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
            Div(*actions, cls="house-card-actions") if actions else None,
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
