from __future__ import annotations

import sqlite3

import pytest
from sqlite_utils import Database

from app.db import (
    get_house_by_external_id,
    get_invite_token,
    houses_ranked,
    init_schema,
    insert_house,
    insert_user,
    set_invite_token,
    toggle_vote,
)
from app.errors import DuplicateHouseError


def test_init_schema_creates_tables_and_is_idempotent() -> None:
    db = Database(memory=True)
    init_schema(db)
    init_schema(db)

    assert db["settings"].exists()
    assert db["users"].exists()
    assert db["houses"].exists()
    assert db["votes"].exists()


def _seed_user_house(db: Database) -> tuple[int, int]:
    user_id = insert_user(db, name="A", email="a@example.com", password_hash="hash")
    house_id = insert_house(
        db,
        source="airbnb",
        external_id="abc1",
        url="https://airbnb.com/rooms/abc1",
        title="House A",
        submitted_by=user_id,
        submitted_at="2026-01-01T00:00:00+00:00",
    )
    return user_id, house_id


def test_duplicate_house_raises_typed_error() -> None:
    db = Database(memory=True)
    init_schema(db)
    user_id, _ = _seed_user_house(db)

    with pytest.raises(DuplicateHouseError):
        insert_house(
            db,
            source="airbnb",
            external_id="abc1",
            url="https://airbnb.com/rooms/abc1?x=1",
            title="Duplicate",
            submitted_by=user_id,
        )


def test_votes_composite_primary_key_enforced() -> None:
    db = Database(memory=True)
    init_schema(db)
    user_id, house_id = _seed_user_house(db)

    db["votes"].insert({"user_id": user_id, "house_id": house_id, "voted_at": "2026-01-01T00:00:00+00:00"})
    with pytest.raises(sqlite3.IntegrityError):
        db["votes"].insert({"user_id": user_id, "house_id": house_id, "voted_at": "2026-01-01T00:00:01+00:00"})


def test_user_email_uniqueness_case_insensitive_storage() -> None:
    db = Database(memory=True)
    init_schema(db)

    insert_user(db, name="User", email="Foo@x.com", password_hash="hash")
    with pytest.raises(sqlite3.IntegrityError):
        insert_user(db, name="User 2", email="foo@x.com", password_hash="hash")


def test_toggle_vote_insert_then_delete() -> None:
    db = Database(memory=True)
    init_schema(db)
    user_id, house_id = _seed_user_house(db)

    assert toggle_vote(db, user_id, house_id) is True
    assert toggle_vote(db, user_id, house_id) is False


def test_houses_ranked_sort_and_zero_votes() -> None:
    db = Database(memory=True)
    init_schema(db)

    user1 = insert_user(db, name="U1", email="u1@example.com", password_hash="hash")
    user2 = insert_user(db, name="U2", email="u2@example.com", password_hash="hash")

    h1 = insert_house(
        db,
        source="airbnb",
        external_id="h1",
        url="https://airbnb.com/rooms/h1",
        title="House 1",
        submitted_by=user1,
        submitted_at="2026-01-01T00:00:00+00:00",
    )
    h2 = insert_house(
        db,
        source="booking",
        external_id="h2",
        url="https://booking.com/hotel/h2",
        title="House 2",
        submitted_by=user1,
        submitted_at="2026-01-01T00:00:01+00:00",
    )
    h3 = insert_house(
        db,
        source="booking",
        external_id="h3",
        url="https://booking.com/hotel/h3",
        title="House 3",
        submitted_by=user2,
        submitted_at="2026-01-01T00:00:02+00:00",
    )

    assert toggle_vote(db, user1, h1) is True
    assert toggle_vote(db, user2, h1) is True
    assert toggle_vote(db, user1, h2) is True

    ranked = houses_ranked(db)
    assert [row["id"] for row in ranked] == [h1, h2, h3]
    assert ranked[0]["vote_count"] == 2
    assert ranked[1]["vote_count"] == 1
    assert ranked[2]["vote_count"] == 0


def test_get_house_by_external_id_and_invite_token_helpers() -> None:
    db = Database(memory=True)
    init_schema(db)
    user_id, _ = _seed_user_house(db)

    house = get_house_by_external_id(db, "airbnb", "abc1")
    assert house is not None
    assert house["submitted_by"] == user_id

    assert get_invite_token(db) is None
    set_invite_token(db, "token-123")
    assert get_invite_token(db) == "token-123"


def test_file_backed_persistence_and_constraints(tmp_path) -> None:
    db_path = tmp_path / "app.db"

    db1 = Database(str(db_path))
    init_schema(db1)
    uid = insert_user(db1, name="Persist", email="persist@example.com", password_hash="hash")
    hid = insert_house(
        db1,
        source="airbnb",
        external_id="persist1",
        url="https://airbnb.com/rooms/persist1",
        title="Persisted House",
        submitted_by=uid,
    )
    assert toggle_vote(db1, uid, hid) is True

    db2 = Database(str(db_path))
    init_schema(db2)

    rows = houses_ranked(db2)
    assert len(rows) == 1
    assert rows[0]["external_id"] == "persist1"
    assert rows[0]["vote_count"] == 1

    with pytest.raises(DuplicateHouseError):
        insert_house(
            db2,
            source="airbnb",
            external_id="persist1",
            url="https://airbnb.com/rooms/persist1?dup=1",
            title="Dup",
            submitted_by=uid,
        )

def test_get_db_enables_wal_and_foreign_keys(monkeypatch) -> None:
    from app.config import get_settings
    from app.db import get_db

    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DB_PATH", ":memory:")
    get_settings.cache_clear()

    db = get_db()
    mode = list(db.query("PRAGMA journal_mode"))[0]["journal_mode"]
    fk = list(db.query("PRAGMA foreign_keys"))[0]["foreign_keys"]

    assert str(mode).lower() in {"memory", "wal"}
    assert fk == 1

def test_get_db_file_backed_reports_wal(monkeypatch, tmp_path) -> None:
    from app.config import get_settings
    from app.db import get_db

    db_path = tmp_path / "wal.db"
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DB_PATH", str(db_path))
    get_settings.cache_clear()

    db = get_db()
    mode = list(db.query("PRAGMA journal_mode"))[0]["journal_mode"]
    assert str(mode).lower() == "wal"
