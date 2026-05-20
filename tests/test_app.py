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
    assert html.count('name="viewport"') == 1
    assert 'content="width=device-width, initial-scale=1"' in html
    assert 'name="htmx-config"' in html
    assert "422|502" in html
    assert "htmx.min.js" in html


def test_nav_header_logged_out_variant() -> None:
    scope = {"type": "http", "headers": [], "method": "GET", "path": "/"}
    request = Request(scope)

    html = _render(nav_header(request))

    assert "Entrar" in html
    assert "Início" in html
    assert "Logout" not in html
    assert "Admin" not in html


def test_nav_header_admin_variant(monkeypatch) -> None:
    scope = {"type": "http", "headers": [], "method": "GET", "path": "/"}
    request = Request(scope)

    monkeypatch.setattr(components, "current_user", lambda _request: {"sub": 1, "role": "admin"})
    html = _render(nav_header(request))

    assert "Administração" in html
    assert "Sair" in html
    assert "Entrar" not in html
    assert 'href="/logout"' not in html
    assert 'method="post"' in html
    assert 'action="/logout"' in html
    assert '<form' in html


def test_error_fragment_retryable_variant() -> None:
    html = _render(error_fragment("nope", retryable=True))

    assert "nope" in html
    assert "Tente novamente em alguns segundos." in html


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
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/login"


def test_login_page_renders_html_shell(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))

    import main

    importlib.reload(main)
    with TestClient(main.create_app()) as client:
        response = client.get("/login")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<form" in response.text


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


def test_startup_restores_before_schema_initialization(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("HF_TOKEN", "hf_token")
    monkeypatch.setenv("HF_REPO_ID", "owner/repo")

    import main

    order: list[str] = []

    def fake_restore(_settings) -> None:
        order.append("restore")

    def fake_init_schema(_db) -> None:
        order.append("schema")

    monkeypatch.setattr(main.app_persistence, "restore_sqlite_files", fake_restore)
    monkeypatch.setattr(main.app_db, "init_schema", fake_init_schema)

    with TestClient(main.create_app()):
        pass

    assert order == ["restore", "schema"]



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
