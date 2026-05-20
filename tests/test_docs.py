from __future__ import annotations

from pathlib import Path


def test_readme_and_env_example_document_persistence_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    for snippet in [
        "The visible app UI and user-facing error copy are in Brazilian Portuguese.",
        "| `HF_TOKEN` | No | — | Hugging Face token used to restore and sync the SQLite file set. Leave empty for local-only mode. |",
        "| `HF_REPO_ID` | No | — | Hugging Face repository id such as `owner/repo`. Leave empty for local-only mode. |",
        "| `HF_REPO_TYPE` | No | `dataset` | Hugging Face repo type for the remote SQLite file set. |",
        "The app keeps working in local SQLite mode when `HF_TOKEN` or `HF_REPO_ID` are missing.",
        "The test suite mocks Hugging Face Hub calls, so it does not require a real token.",
    ]:
        assert snippet in readme

    for snippet in [
        "HF_TOKEN=",
        "HF_REPO_ID=",
        "HF_REPO_TYPE=dataset",
        "HF_DB_PATH_IN_REPO=app.db",
        "HF_SYNC_ENABLED=true",
        "Leave HF_TOKEN and HF_REPO_ID empty to keep the app in local SQLite mode.",
        "Set to false to disable remote sync even when Hub settings are present.",
    ]:
        assert snippet in env_example
