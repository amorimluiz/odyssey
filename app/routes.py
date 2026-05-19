"""Route registration contract for application route modules.

Tasks 06-09 will implement ``register_routes(app)`` in this module. The app
factory calls this contract to attach business routes while keeping handlers out
of ``main.py``.
"""

from __future__ import annotations

from typing import Protocol

from fasthtml.common import FastHTML


class RoutesRegistrar(Protocol):
    """Callable contract used by the app factory to register routes."""

    def __call__(self, app: FastHTML) -> None: ...


def register_routes(app: FastHTML) -> None:
    """Register business routes on the provided app instance.

    Placeholder implementation for task 05. Subsequent route tasks will replace
    this with concrete route registrations.
    """
    _ = app
