"""Optional Hugging Face Hub persistence for the SQLite file set."""

from __future__ import annotations

import logging
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HubPersistenceSettings:
    token: str | None
    repo_id: str | None
    repo_type: str
    db_path_in_repo: str


def _build_hub_settings(settings: Settings) -> HubPersistenceSettings | None:
    if not settings.remote_persistence_enabled:
        return None
    return HubPersistenceSettings(
        token=settings.hf_token,
        repo_id=settings.hf_repo_id,
        repo_type=settings.hf_repo_type,
        db_path_in_repo=settings.hf_db_path_in_repo,
    )


def _sqlite_file_paths(db_path: Path) -> list[Path]:
    return [
        db_path,
        db_path.with_name(f"{db_path.name}-wal"),
        db_path.with_name(f"{db_path.name}-shm"),
    ]


def _is_file_backed_db(db_path: str) -> bool:
    return db_path not in {":memory:", ""} and not db_path.startswith("file::memory:")


def restore_sqlite_files(settings: Settings) -> None:
    """Restore the remote SQLite file set when Hub sync is configured."""

    hub_settings = _build_hub_settings(settings)
    db_path = Path(settings.db_path)
    db_name = db_path.name
    if hub_settings is None:
        logger.info("event=sqlite_restore_skip reason=not_configured db_path=%s", db_name)
        return
    if not _is_file_backed_db(settings.db_path):
        logger.info("event=sqlite_restore_skip reason=memory_db repo_id=%s db_path=%s", hub_settings.repo_id, db_name)
        return
    if db_path.exists():
        logger.info("event=sqlite_restore_skip reason=local_exists repo_id=%s db_path=%s", hub_settings.repo_id, db_name)
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("event=sqlite_restore_start repo_id=%s db_path=%s", hub_settings.repo_id, db_name)

    restored_files = 0
    remote_files = _sqlite_file_paths(Path(hub_settings.db_path_in_repo))
    local_files = _sqlite_file_paths(db_path)

    for index, (remote_file, local_file) in enumerate(zip(remote_files, local_files, strict=True)):
        try:
            downloaded = hf_hub_download(
                repo_id=hub_settings.repo_id,
                filename=remote_file.as_posix(),
                repo_type=hub_settings.repo_type,
                token=hub_settings.token,
            )
        except Exception as exc:  # pragma: no cover - exercised through tests with mocked client errors
            if index == 0:
                logger.info(
                    "event=sqlite_restore_skip reason=remote_missing repo_id=%s db_path=%s error_type=%s",
                    hub_settings.repo_id,
                    db_name,
                    type(exc).__name__,
                )
                return
            logger.info(
                "event=sqlite_restore_missing_companion repo_id=%s file=%s error_type=%s",
                hub_settings.repo_id,
                remote_file.as_posix(),
                type(exc).__name__,
            )
            continue

        local_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(downloaded, local_file)
        restored_files += 1

    logger.info(
        "event=sqlite_restore_complete repo_id=%s db_path=%s files=%s",
        hub_settings.repo_id,
        db_name,
        restored_files,
    )


def sync_sqlite_files(settings: Settings) -> None:
    """Checkpoint the WAL and upload the SQLite file set when Hub sync is configured."""

    hub_settings = _build_hub_settings(settings)
    db_path = Path(settings.db_path)
    db_name = db_path.name
    if hub_settings is None:
        logger.info("event=sqlite_sync_skip reason=not_configured db_path=%s", db_name)
        return
    if not _is_file_backed_db(settings.db_path):
        logger.info("event=sqlite_sync_skip reason=memory_db repo_id=%s db_path=%s", hub_settings.repo_id, db_name)
        return
    if not db_path.exists():
        logger.info("event=sqlite_sync_skip reason=local_missing repo_id=%s db_path=%s", hub_settings.repo_id, db_name)
        return

    logger.info("event=sqlite_sync_start repo_id=%s db_path=%s", hub_settings.repo_id, db_name)

    try:
        with sqlite3.connect(db_path) as checkpoint_conn:
            checkpoint_conn.execute("PRAGMA wal_checkpoint(FULL)")
    except Exception as exc:
        logger.exception(
            "event=sqlite_sync_error stage=checkpoint repo_id=%s db_path=%s error_type=%s",
            hub_settings.repo_id,
            db_name,
            type(exc).__name__,
        )
        return

    api = HfApi(token=hub_settings.token)
    local_files = [path for path in _sqlite_file_paths(db_path) if path.exists()]

    uploaded = 0
    for local_file in local_files:
        remote_file = Path(hub_settings.db_path_in_repo).with_name(local_file.name)
        try:
            api.upload_file(
                path_or_fileobj=str(local_file),
                path_in_repo=remote_file.as_posix(),
                repo_id=hub_settings.repo_id,
                repo_type=hub_settings.repo_type,
                commit_message="Sync SQLite database",
            )
        except Exception as exc:
            logger.exception(
                "event=sqlite_sync_error stage=upload repo_id=%s db_path=%s file=%s error_type=%s",
                hub_settings.repo_id,
                db_name,
                local_file.name,
                type(exc).__name__,
            )
            return
        uploaded += 1

    logger.info(
        "event=sqlite_sync_complete repo_id=%s db_path=%s files=%s",
        hub_settings.repo_id,
        db_name,
        uploaded,
    )
