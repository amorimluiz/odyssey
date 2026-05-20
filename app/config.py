"""Environment-backed application settings."""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    db_path: str
    secret_key: str
    base_url: str | None
    hf_token: str | None = None
    hf_repo_id: str | None = None
    hf_repo_type: str = "dataset"
    hf_db_path_in_repo: str = "app.db"
    hf_sync_enabled: bool = True

    @property
    def remote_persistence_enabled(self) -> bool:
        return self.hf_sync_enabled and bool(self.hf_token) and bool(self.hf_repo_id)


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and validate settings from environment variables."""
    load_dotenv()

    db_path = os.getenv("DB_PATH", "./app.db")
    secret_key = os.getenv("SECRET_KEY")
    base_url = os.getenv("BASE_URL") or None
    hf_token = os.getenv("HF_TOKEN") or None
    hf_repo_id = os.getenv("HF_REPO_ID") or None
    hf_repo_type = os.getenv("HF_REPO_TYPE") or "dataset"
    db_name = Path(db_path).name if not db_path.startswith(":") else "app.db"
    hf_db_path_in_repo = os.getenv("HF_DB_PATH_IN_REPO") or db_name
    hf_sync_enabled = _env_flag("HF_SYNC_ENABLED", default=True)

    if not secret_key:
        raise ValueError("SECRET_KEY environment variable is required")

    return Settings(
        db_path=db_path,
        secret_key=secret_key,
        base_url=base_url,
        hf_token=hf_token,
        hf_repo_id=hf_repo_id,
        hf_repo_type=hf_repo_type,
        hf_db_path_in_repo=hf_db_path_in_repo,
        hf_sync_enabled=hf_sync_enabled,
    )
