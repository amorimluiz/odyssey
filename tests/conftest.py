"""Shared pytest fixtures for project tests."""

from __future__ import annotations

import pytest

import app.config
from app.config import get_settings


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch: pytest.MonkeyPatch):
    """Reset env-dependent state between tests."""
    monkeypatch.setattr(app.config, "load_dotenv", lambda: None)
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch):
    """Provide baseline settings for tests that need config values."""
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    return get_settings()


@pytest.fixture
def in_memory_db_path(monkeypatch: pytest.MonkeyPatch) -> str:
    """Placeholder fixture for upcoming DB tasks."""
    path = ":memory:"
    monkeypatch.setenv("DB_PATH", path)
    return path
