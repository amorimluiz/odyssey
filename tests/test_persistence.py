from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.persistence import restore_sqlite_files, sync_sqlite_files


def _settings(db_path: str, *, hf_db_path_in_repo: str | None = None) -> Settings:
    return Settings(
        db_path=db_path,
        secret_key="s" * 32,
        base_url=None,
        hf_token="hf_token",
        hf_repo_id="owner/repo",
        hf_repo_type="dataset",
        hf_db_path_in_repo=hf_db_path_in_repo or Path(db_path).name,
        hf_sync_enabled=True,
    )


def test_restore_sqlite_files_restores_main_and_skips_missing_companions(monkeypatch, tmp_path) -> None:
    settings = _settings(str(tmp_path / "remote.db"), hf_db_path_in_repo="nested/remote.db")
    remote_dir = tmp_path / "remote"
    remote_dir.mkdir()
    remote_main = remote_dir / "remote.db"
    remote_main.write_text("main", encoding="utf-8")

    downloaded = {
        "nested/remote.db": str(remote_main),
    }
    calls: list[str] = []

    def fake_download(*, repo_id, filename, repo_type, token):
        calls.append(filename)
        if filename in downloaded:
            return downloaded[filename]
        raise FileNotFoundError(filename)

    monkeypatch.setattr("app.persistence.hf_hub_download", fake_download)

    restore_sqlite_files(settings)

    assert calls == [
        "nested/remote.db",
        "nested/remote.db-wal",
        "nested/remote.db-shm",
    ]
    assert (tmp_path / "remote.db").read_text(encoding="utf-8") == "main"
    assert not (tmp_path / "remote.db-wal").exists()
    assert not (tmp_path / "remote.db-shm").exists()


def test_sync_sqlite_files_checkpoints_and_uploads_only_existing_members(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "app.db"
    db_path.write_text("db", encoding="utf-8")
    (tmp_path / "app.db-wal").write_text("wal", encoding="utf-8")
    settings = _settings(str(db_path), hf_db_path_in_repo="nested/app.db")

    checkpoint_calls: list[str] = []

    class DummyCheckpointConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql):
            checkpoint_calls.append(sql)
            return self

    uploads: list[tuple[str, str, str]] = []

    class FakeApi:
        def __init__(self, token):
            self.token = token

        def upload_file(self, *, path_or_fileobj, path_in_repo, repo_id, repo_type, commit_message):
            uploads.append((Path(path_or_fileobj).name, path_in_repo, repo_id))
            return object()

    monkeypatch.setattr("app.persistence.sqlite3.connect", lambda _path: DummyCheckpointConn())
    monkeypatch.setattr("app.persistence.HfApi", FakeApi)

    sync_sqlite_files(settings)

    assert checkpoint_calls == ["PRAGMA wal_checkpoint(FULL)"]
    assert uploads == [
        ("app.db", "nested/app.db", "owner/repo"),
        ("app.db-wal", "nested/app.db-wal", "owner/repo"),
    ]


def test_sync_sqlite_files_swallows_upload_failure(monkeypatch, tmp_path, caplog) -> None:
    db_path = tmp_path / "app.db"
    db_path.write_text("db", encoding="utf-8")
    settings = _settings(str(db_path))

    class DummyCheckpointConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql):
            return self

    class FailingApi:
        def __init__(self, token):
            self.token = token

        def upload_file(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("app.persistence.sqlite3.connect", lambda _path: DummyCheckpointConn())
    monkeypatch.setattr("app.persistence.HfApi", FailingApi)

    with caplog.at_level("INFO"):
        sync_sqlite_files(settings)

    assert "event=sqlite_sync_error" in caplog.text
