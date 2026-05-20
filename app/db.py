"""SQLite database helpers for Group House Voting."""

from __future__ import annotations

import logging
import re
import sqlite3
import unicodedata
from datetime import UTC, datetime
from typing import Any

try:
    import libsql  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised indirectly in tests via monkeypatching
    libsql = None  # type: ignore[assignment]

from sqlite_utils import Database

from app.config import get_settings
from app.errors import DuplicateHouseError

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _register_slugify(db: Database) -> None:
    create_function = getattr(db.conn, "create_function", None)
    if not callable(create_function):
        return
    try:
        create_function("slugify", 1, slugify)
    except Exception:  # pragma: no cover - only reached on backends that expose but reject UDFs
        return


def _configure_local_sqlite(db: Database) -> None:
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    _register_slugify(db)


def _configure_shared_sqlite(db: Database) -> None:
    db.execute("PRAGMA foreign_keys=ON")
    _register_slugify(db)


def slugify(text: str) -> str:
    """ASCII slug: lowercase, diacritics stripped, non-alnum replaced with hyphen."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s_-]+", "-", text).strip("-")


def get_db() -> Database:
    """Open the configured database backend and enable supported shared behavior."""
    settings = get_settings()
    if settings.is_production:
        if libsql is None:
            raise RuntimeError("libsql module is required when APP_ENV=production")
        conn = libsql.connect(settings.turso_database_url, auth_token=settings.turso_auth_token)
        db = Database(conn)
        _configure_shared_sqlite(db)
        backend = "libsql"
    else:
        db = Database(settings.db_path)
        _configure_local_sqlite(db)
        backend = "sqlite"
    logger.info("event=db_backend_selected backend=%s app_env=%s", backend, settings.app_env)
    return db


def init_schema(db: Database) -> None:
    """Create schema and indexes if missing."""
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS houses (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            image_url TEXT,
            description TEXT,
            price TEXT,
            submitted_by INTEGER NOT NULL REFERENCES users(id),
            submitted_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS votes (
            user_id INTEGER NOT NULL REFERENCES users(id),
            house_id INTEGER NOT NULL REFERENCES houses(id),
            voted_at TEXT NOT NULL,
            PRIMARY KEY(user_id, house_id)
        );
        """
    )

    db["users"].create_index(["username"], unique=True, if_not_exists=True, index_name="users_username")
    db["houses"].create_index(["source", "external_id"], unique=True, if_not_exists=True)


def insert_user(
    db: Database,
    *,
    name: str,
    username: str,
    password_hash: str,
    role: str = "member",
    created_at: str | None = None,
) -> int:
    """Insert a user and return the new user id."""
    row = db.conn.execute(
        """
        INSERT INTO users (name, username, password_hash, role, created_at)
        VALUES (?, ?, ?, ?, ?)
        RETURNING id
        """,
        [
            name,
            username.lower(),
            password_hash,
            role,
            created_at or _utc_now_iso(),
        ],
    )
    row_id = row.fetchone()[0]
    db.conn.commit()
    return int(row_id)


def get_user_by_username(db: Database, username: str) -> dict[str, Any] | None:
    """Return user row for username (case-insensitive), or None."""
    rows = list(db.query("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", [username]))
    return dict(rows[0]) if rows else None


def count_users(db: Database) -> int:
    """Return total number of users in the database."""
    row = list(db.query("SELECT COUNT(*) AS c FROM users"))[0]
    return int(row["c"])


def insert_house(
    db: Database,
    *,
    source: str,
    external_id: str,
    url: str,
    title: str,
    submitted_by: int,
    image_url: str | None = None,
    description: str | None = None,
    price: str | None = None,
    submitted_at: str | None = None,
) -> int:
    """Insert house row and map unique collision to DuplicateHouseError."""
    try:
        row = db.conn.execute(
            """
            INSERT INTO houses (
                source,
                external_id,
                url,
                title,
                image_url,
                description,
                price,
                submitted_by,
                submitted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            [
                source,
                external_id,
                url,
                title,
                image_url,
                description,
                price,
                submitted_by,
                submitted_at or _utc_now_iso(),
            ],
        )
        row_id = row.fetchone()[0]
    except sqlite3.IntegrityError as exc:
        if "houses.source, houses.external_id" in str(exc) or "UNIQUE constraint failed: houses.source, houses.external_id" in str(exc):
            raise DuplicateHouseError("House already exists for source/external_id") from exc
        raise

    db.conn.commit()
    return int(row_id)


def get_house_by_external_id(db: Database, source: str, external_id: str) -> dict[str, Any] | None:
    """Return house by unique key, or None."""
    rows = list(
        db.query(
            "SELECT * FROM houses WHERE source = ? AND external_id = ? LIMIT 1",
            [source, external_id],
        )
    )
    return dict(rows[0]) if rows else None


def get_house_by_id(db: Database, house_id: int) -> dict[str, Any] | None:
    """Return house by id, or None."""
    rows = list(db.query("SELECT * FROM houses WHERE id = ? LIMIT 1", [house_id]))
    return dict(rows[0]) if rows else None


def houses_missing_metadata(db: Database) -> list[dict[str, Any]]:
    """Return houses missing price, image URL, or description metadata."""
    rows = db.query(
        """
        SELECT *
        FROM houses
        WHERE COALESCE(TRIM(price), '') = ''
           OR COALESCE(TRIM(image_url), '') = ''
           OR COALESCE(TRIM(description), '') = ''
        ORDER BY submitted_at ASC, id ASC
        """
    )
    return [dict(row) for row in rows]


def update_house_missing_metadata(db: Database, house_id: int, og_data) -> bool:
    """Fill only missing metadata fields on a house row."""
    row = get_house_by_id(db, house_id)
    if row is None:
        return False

    def _is_missing(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    def _clean(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    updates: dict[str, Any] = {}
    for field in ("image_url", "description", "price"):
        if not _is_missing(row.get(field)):
            continue
        new_value = _clean(getattr(og_data, field, None))
        if new_value is not None:
            updates[field] = new_value

    if not updates:
        return False

    assignments = ", ".join(f"{field} = ?" for field in updates)
    params = list(updates.values()) + [house_id]
    db.execute(f"UPDATE houses SET {assignments} WHERE id = ?", params)
    db.conn.commit()
    return True


def count_votes_for_house(db: Database, house_id: int) -> int:
    """Return current vote count for a house id."""
    row = list(
        db.query("SELECT COUNT(*) AS c FROM votes WHERE house_id = ?", [house_id])
    )[0]
    return int(row["c"])


def user_voted_house_ids(db: Database, user_id: int) -> set[int]:
    """Return house ids currently voted by user."""
    rows = db.query("SELECT house_id FROM votes WHERE user_id = ?", [user_id])
    return {int(row["house_id"]) for row in rows}


def houses_ranked(db: Database) -> list[dict[str, Any]]:
    """Return houses with vote_count sorted by rank rules."""
    rows = db.query(
        """
        SELECT
            h.id,
            h.source,
            h.external_id,
            h.url,
            h.title,
            h.image_url,
            h.description,
            h.price,
            h.submitted_by,
            h.submitted_at,
            COUNT(v.user_id) AS vote_count
        FROM houses h
        LEFT JOIN votes v ON v.house_id = h.id
        GROUP BY h.id
        ORDER BY vote_count DESC, h.submitted_at ASC
        """
    )
    return [dict(row) for row in rows]


def toggle_vote(db: Database, user_id: int, house_id: int, voted_at: str | None = None) -> bool:
    """Toggle a vote; return True if active after operation."""
    existing = list(
        db.query(
            "SELECT 1 FROM votes WHERE user_id = ? AND house_id = ? LIMIT 1",
            [user_id, house_id],
        )
    )
    if existing:
        db["votes"].delete_where("user_id = ? AND house_id = ?", [user_id, house_id])
        db.conn.commit()
        return False

    db["votes"].insert(
        {
            "user_id": user_id,
            "house_id": house_id,
            "voted_at": voted_at or _utc_now_iso(),
        }
    )
    db.conn.commit()
    return True


def get_invite_token(db: Database) -> str | None:
    """Return active invite token, if present."""
    rows = list(
        db.query("SELECT value FROM settings WHERE key = ? LIMIT 1", ["invite_token"])
    )
    return None if not rows else str(rows[0]["value"])


def set_invite_token(db: Database, token: str) -> None:
    """Upsert active invite token."""
    db.execute(
        """
        INSERT INTO settings(key, value)
        VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        ["invite_token", token],
    )
    db.conn.commit()


def list_users(db: Database) -> list[dict[str, Any]]:
    """Return users sorted by join date ascending."""
    rows = db.query(
        """
        SELECT id, name, username, role, created_at
        FROM users
        ORDER BY created_at ASC
        """
    )
    return [dict(row) for row in rows]
