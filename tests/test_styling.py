from __future__ import annotations

import importlib
import re

from starlette.requests import Request
from starlette.testclient import TestClient

from app import components
from app.auth import hash_password, issue_token
from app.components import base_layout, error_fragment, house_card, nav_header, vote_button
from app.db import get_db, init_schema, insert_user, set_invite_token

HEX_RE = re.compile(r"#[0-9a-fA-F]{6}")


def _build_client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    import main

    importlib.reload(main)
    return TestClient(main.create_app())


def _assert_viewport_meta_once(html: str) -> None:
    assert html.count('name="viewport"') == 1
    assert 'content="width=device-width, initial-scale=1"' in html


def test_house_card_has_documented_classes() -> None:
    html = repr(
        house_card(
            {
                "id": 1,
                "source": "airbnb",
                "url": "https://www.airbnb.com/rooms/1",
                "title": "Casa",
                "image_url": None,
                "description": "Desc",
                "price": "$123",
                "vote_count": 3,
            }
        )
    )

    assert 'class="house-card"' in html
    assert "house-card-title" in html
    assert "house-card-source" in html
    assert "house-card-image-placeholder" in html
    assert "Abrir anúncio" in html


def test_vote_button_toggled_class_and_aria_pressed() -> None:
    html = repr(vote_button({"id": 7, "vote_count": 4}, is_voted=True))

    assert "house-card-vote-btn" in html
    assert "is-voted" in html
    assert 'aria-pressed="true"' in html
    assert "Votado (4)" in html


def test_nav_header_admin_has_styled_admin_link(monkeypatch) -> None:
    scope = {"type": "http", "headers": [], "method": "GET", "path": "/"}
    request = Request(scope)

    monkeypatch.setattr(components, "current_user", lambda _request: {"sub": 1, "role": "admin"})
    html = repr(nav_header(request))

    assert 'href="/admin"' in html
    assert "nav-links" in html


def test_error_fragment_retryable_variant_class() -> None:
    html = repr(error_fragment("Could not fetch", retryable=True))

    assert "error-fragment retryable" in html


def test_base_layout_includes_stylesheet_and_htmx_script() -> None:
    html = str(base_layout("hello", title="Votação de Casas do Grupo"))

    assert '<link rel="stylesheet" href="/static/style.css">' in html
    assert "htmx.min.js" in html


def test_base_layout_includes_single_viewport_meta_tag() -> None:
    html = str(base_layout("hello", title="Votação de Casas do Grupo"))

    _assert_viewport_meta_once(html)


def test_get_root_includes_single_stylesheet_link(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        db = get_db()
        init_schema(db)
        user_id = insert_user(
            db,
            name="Member",
            username="member",
            password_hash=hash_password("verysecure"),
            role="member",
        )
        client.cookies.set("session", issue_token(user_id, "member"))

        response = client.get("/")

    assert response.status_code == 200
    assert response.text.count('<link rel="stylesheet" href="/static/style.css">') == 1


def test_primary_routes_render_viewport_meta_once(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        db = get_db()
        init_schema(db)
        set_invite_token(db, "seedtoken")
        member_id = insert_user(
            db,
            name="Member",
            username="member",
            password_hash=hash_password("verysecure"),
            role="member",
        )
        admin_id = insert_user(
            db,
            name="Admin",
            username="admin-user",
            password_hash=hash_password("verysecure"),
            role="admin",
        )

        login = client.get("/login")
        invite = client.get("/invite/seedtoken")
        client.cookies.set("session", issue_token(member_id, "member"))
        home = client.get("/")
        client.cookies.set("session", issue_token(admin_id, "admin"))
        admin = client.get("/admin")

    for response in (login, invite, home, admin):
        assert response.status_code == 200
        _assert_viewport_meta_once(response.text)


def test_rendered_pages_do_not_contain_hex_literals(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        db = get_db()
        init_schema(db)
        set_invite_token(db, "seedtoken")
        admin_id = insert_user(
            db,
            name="Admin",
            username="admin-user",
            password_hash=hash_password("verysecure"),
            role="admin",
        )

        login = client.get("/login")
        invite = client.get("/invite/seedtoken")
        client.cookies.set("session", issue_token(admin_id, "admin"))
        home = client.get("/")
        admin = client.get("/admin")

    for response in (login, invite, home, admin):
        assert response.status_code == 200
        assert HEX_RE.search(response.text) is None


def test_static_css_served_with_text_css_content_type(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        response = client.get("/static/style.css")

    assert response.status_code == 200
    assert "text/css" in response.headers.get("content-type", "")


def test_css_defines_required_design_tokens() -> None:
    css = open("static/style.css", "r", encoding="utf-8").read()

    for token in [
        "--color-primary",
        "--color-primary-deep",
        "--color-on-primary",
        "--color-ink-button",
        "--color-on-ink-button",
        "--color-canvas",
        "--color-hairline",
    ]:
        assert token in css


def test_css_has_no_hex_literals_outside_root_block() -> None:
    css = open("static/style.css", "r", encoding="utf-8").read()
    root_match = re.search(r":root\s*\{(?P<body>.*?)\}\s*", css, re.S)
    assert root_match is not None

    root_body = root_match.group("body")
    css_without_root = css.replace(root_match.group(0), "")
    assert HEX_RE.search(root_body) is not None
    assert HEX_RE.search(css_without_root) is None
