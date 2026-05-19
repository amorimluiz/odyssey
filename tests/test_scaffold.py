"""Smoke and configuration tests for task 01 scaffold."""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

from app.config import Settings, get_settings


@pytest.mark.parametrize(
    "module_name",
    ["app", "app.db", "app.auth", "app.scraper", "app.routes", "app.config"],
)
def test_modules_import(module_name: str) -> None:
    importlib.import_module(module_name)


def test_get_settings_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PATH", "./tmp.db")
    monkeypatch.setenv("SECRET_KEY", "s" * 32)

    result = get_settings()

    assert isinstance(result, Settings)
    assert result.db_path == "./tmp.db"
    assert result.secret_key == "s" * 32


def test_get_settings_requires_secret_key() -> None:
    with pytest.raises(ValueError, match="SECRET_KEY"):
        get_settings()


def test_settings_has_no_admin_email_attribute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "k" * 32)

    result = get_settings()

    assert not hasattr(result, "admin_email")


def test_python_import_app_subprocess() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import app"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
