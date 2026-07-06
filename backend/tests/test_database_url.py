from __future__ import annotations

from pathlib import Path

from src.config.settings import LOCAL_RUNTIME_DIR, ROOT_DIR, Settings


def test_database_url_defaults_to_runtime_sqlite_database():
    cfg = Settings(_env_file=None)

    assert cfg.storage.database_url == f"sqlite:///{LOCAL_RUNTIME_DIR / 'conversations.db'}"


def test_database_url_resolves_relative_sqlite_paths_from_repo_root():
    cfg = Settings(database_url="sqlite:///runtime/team/conversations.db", _env_file=None)

    assert cfg.storage.database_url == f"sqlite:///{ROOT_DIR / Path('runtime/team/conversations.db')}"

