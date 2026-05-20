"""Compatibility facade for shared FastHTML components."""

from __future__ import annotations

from . import admin as admin
from . import feedback as feedback
from . import houses as houses
from . import layout as layout
from .admin import admin_panel, invite_link_fragment, metadata_refresh_fragment
from .feedback import error_fragment
from .houses import house_card, house_submit_form, vote_button
from .layout import HTMX_CDN, HTMX_INTEGRITY, HTMX_RESPONSE_HANDLING, base_layout, nav_header

__all__ = [
    "HTMX_CDN",
    "HTMX_INTEGRITY",
    "HTMX_RESPONSE_HANDLING",
    "admin_panel",
    "base_layout",
    "error_fragment",
    "house_card",
    "house_submit_form",
    "invite_link_fragment",
    "metadata_refresh_fragment",
    "nav_header",
    "vote_button",
]
