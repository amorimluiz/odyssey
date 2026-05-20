from __future__ import annotations

from app.config import get_settings


def test_settings_without_hub_env_remains_local_only(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", "/tmp/house.db")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.hf_token is None
    assert settings.hf_repo_id is None
    assert settings.hf_repo_type == "dataset"
    assert settings.hf_db_path_in_repo == "house.db"
    assert settings.hf_sync_enabled is True
    assert settings.remote_persistence_enabled is False


def test_settings_with_hub_env_enables_remote_persistence(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", "/tmp/group/app.db")
    monkeypatch.setenv("HF_TOKEN", "hf_test_token")
    monkeypatch.setenv("HF_REPO_ID", "owner/repo")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.hf_token == "hf_test_token"
    assert settings.hf_repo_id == "owner/repo"
    assert settings.hf_repo_type == "dataset"
    assert settings.hf_db_path_in_repo == "app.db"
    assert settings.remote_persistence_enabled is True
