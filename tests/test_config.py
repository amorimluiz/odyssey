from __future__ import annotations

from dataclasses import asdict

from app.config import get_settings


def test_get_settings_returns_only_local_sqlite_fields(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", "/tmp/house.db")
    monkeypatch.setenv("BASE_URL", "https://example.com")
    get_settings.cache_clear()

    settings = get_settings()

    assert asdict(settings) == {
        "db_path": "/tmp/house.db",
        "secret_key": "s" * 32,
        "base_url": "https://example.com",
    }
    assert tuple(asdict(settings).keys()) == ("db_path", "secret_key", "base_url")
