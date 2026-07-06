from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.persistence import workspace_store


POSTGRES_URL = "postgresql+psycopg://knowbase:pw@postgres/knowbase"


def test_workspace_store_uses_sqlalchemy_list_when_database_url_is_postgres():
    session_factory = MagicMock()
    expected = [{"id": "", "name": "默认工作区", "description": "", "created_at": "t", "updated_at": "t"}]

    with patch("src.persistence.workspace_store.settings") as mock_settings:
        mock_settings.storage.database_url = POSTGRES_URL
        with patch("src.persistence.workspace_store.get_session_factory", return_value=session_factory) as mock_factory:
            with patch("src.persistence.workspace_store.workspace_repository.list_workspaces_with_session", return_value=expected) as mock_list:
                assert workspace_store.list_workspaces() == expected

    mock_factory.assert_called_once_with(POSTGRES_URL)
    mock_list.assert_called_once_with(session_factory)


def test_workspace_store_uses_sqlite_create_by_default():
    expected = {"id": "ws-1", "name": "SQLite", "description": "", "created_at": "t", "updated_at": "t"}

    with patch("src.persistence.workspace_store.settings") as mock_settings:
        mock_settings.storage.database_url = "sqlite:///runtime/local/conversations.db"
        with patch("src.persistence.workspace_store.get_connection") as mock_get_connection:
            with patch("src.persistence.workspace_store.workspace_repository.create_workspace", return_value=expected) as mock_create:
                assert workspace_store.create_workspace("SQLite", "") == expected

    mock_create.assert_called_once_with(mock_get_connection, "SQLite", "")

