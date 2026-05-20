from __future__ import annotations

from pathlib import Path


def test_readme_and_env_example_document_persistence_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    for snippet in [
        "The visible app UI and user-facing error copy are in Brazilian Portuguese.",
        "SQLite persistence is local-only and depends on the configured database file remaining available.",
        "Provide a persistent `DB_PATH` on platforms that do not keep the filesystem between deploys.",
        "Coverage is enforced at 80%.",
    ]:
        assert snippet in readme

    for snippet in [
        "DB_PATH=./app.db",
        "SECRET_KEY=replace-with-at-least-32-random-bytes",
        "ADMIN_EMAIL=admin@example.com",
    ]:
        assert snippet in env_example
