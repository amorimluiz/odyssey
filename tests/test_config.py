from __future__ import annotations

import os

import pytest

from app.config import TursoConfigError, get_settings


def test_get_settings_returns_only_local_sqlite_fields(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", "/tmp/house.db")
    monkeypatch.setenv("BASE_URL", "https://example.com")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_env == "development"
    assert settings.is_production is False
    assert settings.db_path == "/tmp/house.db"
    assert settings.base_url == "https://example.com"
    assert settings.turso_database_url is None
    assert settings.turso_auth_token is None


def test_settings_defaults_to_development_without_app_env(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", "/tmp/default.db")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_env == "development"
    assert settings.db_path == "/tmp/default.db"
    assert settings.is_production is False


def test_settings_requires_turso_database_url_in_production(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "turso-token")
    get_settings.cache_clear()

    with pytest.raises(TursoConfigError, match="TURSO_DATABASE_URL"):
        get_settings()


def test_settings_requires_turso_auth_token_in_production(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://db.turso.io")
    get_settings.cache_clear()

    with pytest.raises(TursoConfigError, match="TURSO_AUTH_TOKEN"):
        get_settings()


def test_settings_returns_turso_values_in_production(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://db.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "turso-token")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_env == "production"
    assert settings.is_production is True
    assert settings.turso_database_url == "libsql://db.turso.io"
    assert settings.turso_auth_token == "turso-token"


def test_isolate_environment_clears_turso_variables() -> None:
    assert os.getenv("TURSO_DATABASE_URL") is None
    assert os.getenv("TURSO_AUTH_TOKEN") is None
