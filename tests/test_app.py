from __future__ import annotations

import importlib
import logging
import sqlite3

from starlette.requests import Request
from starlette.testclient import TestClient

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

    monkeypatch.setattr("app.components.layout.current_user", lambda _request: {"sub": 1, "role": "admin"})
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
    assert response.text.startswith("<!doctype html>")
    assert not response.text.startswith("(")
    assert "<form" in response.text


def test_startup_calls_init_schema_once(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))

    import main

    calls = {"count": 0}
    original_init_schema = main.app_db.init_schema

    def fake_init_schema(db) -> None:
        calls["count"] += 1
        original_init_schema(db)

    monkeypatch.setattr(main.app_db, "init_schema", fake_init_schema)
    with TestClient(main.create_app()):
        pass

    assert calls["count"] == 1

    db = main.app_db.get_db()
    assert db["users"].exists()
    assert db["houses"].exists()
    assert db["votes"].exists()


def test_startup_uses_libsql_in_production(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "production.db"))
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://db.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "turso-token")

    import main
    importlib.reload(main)

    schema_calls: list[str] = []
    fake_conn = sqlite3.connect(":memory:", check_same_thread=False)

    def fake_connect(url: str, auth_token: str | None = None):
        assert url == "libsql://db.turso.io"
        assert auth_token == "turso-token"
        return fake_conn

    def fake_init_schema(_db) -> None:
        schema_calls.append("schema")

    monkeypatch.setattr(main.app_db, "init_schema", fake_init_schema)
    monkeypatch.setattr(
        main.app_db,
        "libsql",
        type("FakeLibSQL", (), {"connect": staticmethod(fake_connect)})(),
    )

    with TestClient(main.create_app()):
        pass

    assert schema_calls == ["schema"]


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


def test_startup_uses_local_sqlite_backend(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    db_path = tmp_path / "local.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import main

    observed: dict[str, object] = {}

    def fake_init_schema(db) -> None:
        observed["location"] = list(db.query("PRAGMA database_list"))[0]["file"]
        observed["mode"] = list(db.query("PRAGMA journal_mode"))[0]["journal_mode"]

    monkeypatch.setattr(main.app_db, "init_schema", fake_init_schema)
    importlib.reload(main)
    with TestClient(main.create_app()):
        pass

    assert observed["location"] == str(db_path)
    assert str(observed["mode"]).lower() == "wal"


def test_startup_uses_production_libsql_backend(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "production.db"))
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://db.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "turso-token")

    import main

    calls: list[tuple[str, str | None]] = []

    def fake_connect(url: str, auth_token: str | None = None):
        calls.append((url, auth_token))
        return sqlite3.connect(":memory:", check_same_thread=False)

    monkeypatch.setattr(main.app_db, "libsql", type("FakeLibSQL", (), {"connect": staticmethod(fake_connect)})())

    observed: dict[str, object] = {}

    def fake_init_schema(db) -> None:
        observed["fk"] = list(db.query("PRAGMA foreign_keys"))[0]["foreign_keys"]
        observed["mode"] = list(db.query("PRAGMA journal_mode"))[0]["journal_mode"]

    monkeypatch.setattr(main.app_db, "init_schema", fake_init_schema)
    importlib.reload(main)
    with TestClient(main.create_app()):
        pass

    assert calls == [("libsql://db.turso.io", "turso-token")]
    assert observed["fk"] == 1
    assert observed["mode"] != "wal"


def test_libsql_connection_adapter_makes_cursor_iterable() -> None:
    from app.db import _LibsqlConnectionAdapter

    class FakeCursor:
        def __init__(self, rows):
            self._rows = list(rows)
            self.description = [("a",), ("b",)]
            self.lastrowid = 42
            self.rowcount = len(self._rows)
            self.fetchall_calls = 0

        def fetchall(self):
            self.fetchall_calls += 1
            rows = self._rows
            self._rows = []
            return rows

    class FakeConn:
        def __init__(self):
            self.commits = 0
            self.scripts: list[str] = []
            self.last_cursor: FakeCursor | None = None

        def execute(self, sql, parameters=None):
            assert sql == "SELECT a, b FROM t"
            self.last_cursor = FakeCursor([(1, 2), (3, 4)])
            return self.last_cursor

        def commit(self):
            self.commits += 1

        def executescript(self, script):
            self.scripts.append(script)

    raw = FakeConn()
    adapter = _LibsqlConnectionAdapter(raw)

    cursor = adapter.execute("SELECT a, b FROM t")
    # Drain happens eagerly inside the wrapper so commit() can run on libsql.
    assert raw.last_cursor is not None and raw.last_cursor.fetchall_calls == 1
    # Proxied attributes survive the drain.
    assert cursor.description == [("a",), ("b",)]
    assert cursor.lastrowid == 42
    assert cursor.rowcount == 2
    # Buffered iteration semantics match DB-API: first read returns rows, second is empty.
    assert list(cursor) == [(1, 2), (3, 4)]
    assert cursor.fetchone() is None

    adapter.commit()
    adapter.executescript("CREATE TABLE t (a, b);")
    assert raw.commits == 1
    assert raw.scripts == ["CREATE TABLE t (a, b);"]


def test_libsql_connection_adapter_supports_context_manager_protocol() -> None:
    from app.db import _LibsqlConnectionAdapter

    events: list[str] = []

    class FakeConn:
        def __enter__(self):
            events.append("enter")
            return self

        def __exit__(self, exc_type, exc, tb):
            events.append(f"exit:{'err' if exc_type else 'ok'}")
            return False

        def execute(self, sql, parameters=None):
            class _C:
                description = ()
                lastrowid = 0
                rowcount = 0
                def fetchall(self):
                    return []
            return _C()

    adapter = _LibsqlConnectionAdapter(FakeConn())
    with adapter:
        adapter.execute("INSERT INTO t VALUES (1)")
    assert events == ["enter", "exit:ok"]

    import pytest
    with pytest.raises(RuntimeError):
        with adapter:
            raise RuntimeError("boom")
    assert events[-2:] == ["enter", "exit:err"]


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
