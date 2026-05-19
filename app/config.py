"""Environment-backed application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    db_path: str
    secret_key: str
    base_url: str | None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and validate settings from environment variables."""
    load_dotenv()

    db_path = os.getenv("DB_PATH", "./app.db")
    secret_key = os.getenv("SECRET_KEY")
    base_url = os.getenv("BASE_URL") or None

    if not secret_key:
        raise ValueError("SECRET_KEY environment variable is required")

    return Settings(db_path=db_path, secret_key=secret_key, base_url=base_url)
