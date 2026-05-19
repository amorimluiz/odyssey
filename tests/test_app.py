from __future__ import annotations

import importlib
import logging

from starlette.requests import Request
from starlette.testclient import TestClient

from app import components
from app.components import base_layout, error_fragment, nav_header


def _render(node) -> str:
    return str(node)


def test_base_layout_includes_title_and_htmx_script() -> None:
    html = _render(base_layout("hello", title="Houses"))

    assert "<title>Houses</title>" in html
    assert "htmx.min.js" in html


def test_nav_header_logged_out_variant() -> None:
    scope = {"type": "http", "headers": [], "method": "GET", "path": "/"}
    request = Request(scope)

    html = _render(nav_header(request))

    assert "Login" in html
    assert "Logout" not in html
    assert "Admin" not in html


def test_nav_header_admin_variant(monkeypatch) -> None:
    scope = {"type": "http", "headers": [], "method": "GET", "path": "/"}
    request = Request(scope)

    monkeypatch.setattr(components, "current_user", lambda _request: {"sub": 1, "role": "admin"})
    html = _render(nav_header(request))

    assert "Admin" in html
    assert "Logout" in html
    assert "Login" not in html


def test_error_fragment_retryable_variant() -> None:
    html = _render(error_fragment("nope", retryable=True))

    assert "nope" in html
    assert "Please retry in a few seconds." in html


def test_healthz_returns_ok(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))

    import main

    importlib.reload(main)
    with TestClient(main.create_app()) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.text == "ok"


def test_home_renders_layout_and_nav(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))

    import main

    importlib.reload(main)
    with TestClient(main.create_app()) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Group House Voting" in response.text
    assert "Login" in response.text


def test_startup_calls_init_schema_once(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))

    import main

    calls = {"count": 0}

    def fake_init_schema(db) -> None:
        calls["count"] += 1

    monkeypatch.setattr(main.app_db, "init_schema", fake_init_schema)
    with TestClient(main.create_app()):
        pass

    assert calls["count"] == 1


def test_invalid_admin_email_emits_warning(monkeypatch, caplog, tmp_path) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("ADMIN_EMAIL", "not-an-email")

    import main

    importlib.reload(main)
    caplog.set_level(logging.WARNING)
    with TestClient(main.create_app()):
        pass

    assert "ADMIN_EMAIL appears invalid" in caplog.text


def test_startup_is_idempotent_for_same_db_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    db_path = str(tmp_path / "shared.db")
    monkeypatch.setenv("DB_PATH", db_path)

    import main

    importlib.reload(main)
    with TestClient(main.create_app()):
        pass
    with TestClient(main.create_app()):
        pass


def test_request_logging_contains_required_fields(monkeypatch, caplog, tmp_path) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))

    import main

    importlib.reload(main)
    caplog.set_level(logging.INFO)
    with TestClient(main.create_app()) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    line = next(msg for msg in caplog.messages if msg.startswith("request method="))
    assert "method=GET" in line
    assert "path=/healthz" in line
    assert "status=200" in line
    assert "latency_ms=" in line
