from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.persistence import database
from src.persistence.sqlalchemy_database import create_engine_for_url, is_postgres_url


def test_create_engine_for_url_keeps_sqlite_memory_url():
    engine = create_engine_for_url("sqlite:///:memory:")

    assert str(engine.url) == "sqlite:///:memory:"


def test_is_postgres_url_accepts_common_sqlalchemy_postgres_drivers():
    assert is_postgres_url("postgresql://user:pass@db/knowbase")
    assert is_postgres_url("postgresql+psycopg://user:pass@db/knowbase")
    assert not is_postgres_url("sqlite:///runtime/local/conversations.db")


def test_init_db_uses_sqlalchemy_workspace_bootstrap_for_postgres_url():
    session_factory = MagicMock()
    with patch("src.persistence.database.settings") as mock_settings:
        mock_settings.storage.database_url = "postgresql+psycopg://knowbase:pw@postgres/knowbase"
        with patch("src.persistence.database.run_migrations") as mock_run_migrations:
            with patch("src.persistence.database.get_session_factory", return_value=session_factory) as mock_get_factory:
                with patch(
                    "src.persistence.database.workspace_repository.ensure_default_workspace_with_session"
                ) as mock_ensure_default:
                    database.init_db()

    mock_run_migrations.assert_called_once()
    mock_get_factory.assert_called_once_with("postgresql+psycopg://knowbase:pw@postgres/knowbase")
    mock_ensure_default.assert_called_once_with(session_factory)
