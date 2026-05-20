from __future__ import annotations

from pathlib import Path


def test_readme_and_env_example_document_persistence_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    for snippet in [
        "The visible app UI and user-facing error copy are in Brazilian Portuguese.",
        "| `APP_ENV` | No | `development` | Environment selector. Use `production` to require Turso/libSQL settings and direct remote persistence. |",
        "| `TURSO_DATABASE_URL` | No, but required when `APP_ENV=production` | — | Turso/libSQL database URL used for direct production connections. |",
        "| `TURSO_AUTH_TOKEN` | No, but required when `APP_ENV=production` | — | Turso auth token used with the production database URL. |",
        "Production must set `APP_ENV=production` and provide both Turso settings. The app fails fast during startup if either value is missing.",
        "Production connects directly to Turso/libSQL and commits writes remotely. It does not rely on a local SQLite file.",
        "Coverage is enforced at 80%. The test suite mocks libSQL connections, so it does not require a live Turso database or real Turso credentials.",
    ]:
        assert snippet in readme

    for snippet in [
        "APP_ENV=development",
        "DB_PATH=./app.db",
        "BASE_URL=",
        "TURSO_DATABASE_URL=libsql://<your-database>.turso.io",
        "TURSO_AUTH_TOKEN=<your-turso-auth-token>",
        "# Required when APP_ENV=production",
    ]:
        assert snippet in env_example
