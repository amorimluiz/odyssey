"""Reusable feedback fragments."""

from __future__ import annotations

from fasthtml.common import Div, Span


def error_fragment(message: str, retryable: bool = False) -> Div:
    """Render inline error feedback for HTMX form fragments."""
    retry_hint = Div("Tente novamente em alguns segundos.", cls="error-retry") if retryable else None
    children = [Span(message, cls="error-message")]
    if retry_hint is not None:
        children.append(retry_hint)
    fragment_class = "error-fragment retryable" if retryable else "error-fragment"
    return Div(*children, role="alert", cls=fragment_class)
