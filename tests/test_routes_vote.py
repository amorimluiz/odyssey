from __future__ import annotations

import importlib
import sqlite3

import pytest
from starlette.testclient import TestClient

from app.auth import hash_password, issue_token
from app.components import vote_button
from app.db import count_votes_for_house, get_db, init_schema, insert_house, insert_user


def _build_client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    import main

    importlib.reload(main)
    return TestClient(main.create_app())


def _make_user(client: TestClient, username: str) -> int:
    db = get_db()
    init_schema(db)
    user_id = insert_user(
        db,
        name=username,
        username=username,
        password_hash=hash_password("verysecure"),
        role="member",
    )
    return user_id


def _set_session(client: TestClient, user_id: int) -> None:
    client.cookies.set("session", issue_token(user_id, "member"))


def _seed_house(submitted_by: int) -> int:
    db = get_db()
    return insert_house(
        db,
        source="airbnb",
        external_id="vote-house-1",
        url="https://www.airbnb.com/rooms/vote-house-1",
        title="Vote House",
        image_url=None,
        description="Desc",
        price=None,
        submitted_by=submitted_by,
    )


def test_vote_button_renders_voted_variant() -> None:
    html = repr(vote_button({"id": 10, "vote_count": 3}, is_voted=True))

    assert 'aria-pressed="true"' in html
    assert 'aria-label="Remover voto desta casa"' in html
    assert "house-card-vote-btn" in html
    assert "is-voted" in html
    assert "♥" in html
    assert "3" in html
    assert 'hx-post="/houses/10/vote"' in html
    assert 'hx-swap="outerHTML"' in html


def test_vote_button_renders_unvoted_variant() -> None:
    html = repr(vote_button({"id": 11, "vote_count": 0}, is_voted=False))

    assert 'aria-pressed="false"' in html
    assert 'aria-label="Votar nesta casa"' in html
    assert "house-card-vote-btn" in html
    assert "is-neutral" in html
    assert "♡" in html
    assert "0" in html


def test_vote_toggle_authenticated_vote_then_unvote(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _make_user(client, "member")
        _set_session(client, user_id)
        house_id = _seed_house(user_id)

        first = client.post(f"/houses/{house_id}/vote")
        second = client.post(f"/houses/{house_id}/vote")

    assert first.status_code == 200
    assert 'aria-pressed="true"' in first.text
    assert 'aria-label="Remover voto desta casa"' in first.text
    assert "♥" in first.text
    assert ">1<" in first.text

    assert second.status_code == 200
    assert 'aria-pressed="false"' in second.text
    assert 'aria-label="Votar nesta casa"' in second.text
    assert "♡" in second.text
    assert ">0<" in second.text

    assert count_votes_for_house(get_db(), house_id) == 0


def test_vote_toggle_unauthenticated_returns_401(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _make_user(client, "owner")
        house_id = _seed_house(user_id)

        response = client.post(f"/houses/{house_id}/vote")

    assert response.status_code == 401
    assert "Não autorizado." in response.text


def test_vote_toggle_unknown_house_returns_404(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _make_user(client, "member")
        _set_session(client, user_id)

        response = client.post("/houses/9999/vote")

    assert response.status_code == 404
    assert "Casa não encontrada." in response.text


def test_vote_toggle_cross_user_isolation_and_double_toggle(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_a = _make_user(client, "user-a")
        user_b = _make_user(client, "user-b")
        house_id = _seed_house(user_a)

        _set_session(client, user_a)
        r1 = client.post(f"/houses/{house_id}/vote")
        _set_session(client, user_b)
        r2 = client.post(f"/houses/{house_id}/vote")

        assert 'aria-label="Remover voto desta casa"' in r1.text
        assert 'aria-label="Remover voto desta casa"' in r2.text
        assert "♥" in r1.text
        assert "♥" in r2.text
        assert ">1<" in r1.text
        assert ">2<" in r2.text
        assert count_votes_for_house(get_db(), house_id) == 2

        r3 = client.post(f"/houses/{house_id}/vote")
        assert 'aria-pressed="false"' in r3.text
        assert 'aria-label="Votar nesta casa"' in r3.text
        assert "♡" in r3.text
        assert ">1<" in r3.text
        assert count_votes_for_house(get_db(), house_id) == 1

        _set_session(client, user_a)
        r4 = client.post(f"/houses/{house_id}/vote")
        assert 'aria-pressed="false"' in r4.text
        assert 'aria-label="Votar nesta casa"' in r4.text
        assert "♡" in r4.text
        assert ">0<" in r4.text
        assert count_votes_for_house(get_db(), house_id) == 0


def test_vote_toggle_ignores_user_id_payload_and_query(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        jwt_user = _make_user(client, "jwt-user")
        attacker = _make_user(client, "attacker")
        house_id = _seed_house(jwt_user)

        _set_session(client, jwt_user)
        response = client.post(
            f"/houses/{house_id}/vote?user_id={attacker}",
            data={"user_id": str(attacker)},
        )

    assert response.status_code == 200
    assert 'aria-pressed="true"' in response.text

    votes = list(get_db().query("SELECT user_id, house_id FROM votes ORDER BY user_id"))
    assert votes == [{"user_id": jwt_user, "house_id": house_id}]


def test_vote_uniqueness_enforced_at_db_level(monkeypatch, tmp_path) -> None:
    with _build_client(monkeypatch, tmp_path) as client:
        user_id = _make_user(client, "unique-user")
        house_id = _seed_house(user_id)
        db = get_db()

        db["votes"].insert({"user_id": user_id, "house_id": house_id, "voted_at": "2026-01-01T00:00:00+00:00"})
        with pytest.raises(sqlite3.IntegrityError):
            db["votes"].insert({"user_id": user_id, "house_id": house_id, "voted_at": "2026-01-01T00:00:01+00:00"})
