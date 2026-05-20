"""Admin-facing reusable fragments."""

from __future__ import annotations

from fasthtml.common import Button, Div, H2, Input, P, Script, Table, Tbody, Td, Th, Thead, Tr


def invite_link_fragment(invite_url: str) -> Div:
    """Render current invite URL plus copy and rotate controls."""
    return Div(
        P("Link de convite atual"),
        Input(
            id="invite-link-input",
            type="text",
            value=invite_url,
            readonly=True,
            cls="text-input",
        ),
        Div(
            Button(
                "Copiar link",
                type="button",
                onclick="copyInviteLink()",
                cls="btn btn-secondary",
            ),
            Button(
                "Rotacionar link de convite",
                type="button",
                hx_post="/admin/rotate-invite",
                hx_target="#invite-link-fragment",
                hx_swap="outerHTML",
                cls="btn btn-primary",
            ),
            cls="admin-actions",
        ),
        Script(
            """
function copyInviteLink() {
  const el = document.getElementById("invite-link-input");
  if (!el) return;
  el.select();
  navigator.clipboard.writeText(el.value);
}
""".strip()
        ),
        id="invite-link-fragment",
        cls="admin-invite",
    )


def metadata_refresh_fragment(*, scanned: int | None = None, updated: int | None = None, failed: int | None = None) -> Div:
    """Render admin metadata refresh controls and optional summary."""
    summary = None
    if scanned is not None and updated is not None and failed is not None:
        summary = P(
            f"Verificadas {scanned} casas. Atualizadas {updated}. Falhas: {failed}.",
            cls="admin-refresh-summary",
        )

    return Div(
        Button(
            "Atualizar metadados ausentes",
            type="button",
            hx_post="/admin/refresh-metadata",
            hx_target="#metadata-refresh-fragment",
            hx_swap="outerHTML",
            cls="btn btn-secondary",
        ),
        summary,
        id="metadata-refresh-fragment",
        cls="admin-actions admin-refresh",
    )


def admin_panel(*, invite_url: str, members: list[dict]) -> Div:
    """Render admin panel with invite controls and read-only member list."""
    rows = [
        Tr(
            Td(member.get("name", "")),
            Td(member.get("username", "")),
            Td(member.get("created_at", "")),
        )
        for member in members
    ]

    return Div(
        invite_link_fragment(invite_url),
        metadata_refresh_fragment(),
        H2("Membros", cls="section-title"),
        Table(
            Thead(Tr(Th("Nome"), Th("Nome de usuário"), Th("Data de entrada"))),
            Tbody(*rows),
            cls="members-table",
        ),
        cls="admin-panel",
    )
