"""Environment-backed application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


class TursoConfigError(ValueError):
    """Raised when production Turso settings are incomplete."""


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    db_path: str = "./app.db"
    secret_key: str = ""
    base_url: str | None = None
    turso_database_url: str | None = None
    turso_auth_token: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and validate settings from environment variables."""
    load_dotenv()

    app_env = (os.getenv("APP_ENV") or "development").strip().lower()
    db_path = os.getenv("DB_PATH", "./app.db")
    secret_key = os.getenv("SECRET_KEY")
    base_url = os.getenv("BASE_URL") or None
    turso_database_url = os.getenv("TURSO_DATABASE_URL") or None
    turso_auth_token = os.getenv("TURSO_AUTH_TOKEN") or None

    if not secret_key:
        raise ValueError("SECRET_KEY environment variable is required")

    if app_env == "production":
        if not turso_database_url:
            raise TursoConfigError("APP_ENV=production requires TURSO_DATABASE_URL")
        if not turso_auth_token:
            raise TursoConfigError("APP_ENV=production requires TURSO_AUTH_TOKEN")

    return Settings(
        app_env=app_env,
        db_path=db_path,
        secret_key=secret_key,
        base_url=base_url,
        turso_database_url=turso_database_url,
        turso_auth_token=turso_auth_token,
    )
