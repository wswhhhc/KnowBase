from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.persistence import conversation_store


POSTGRES_URL = "postgresql+psycopg://knowbase:pw@postgres/knowbase"


def test_conversation_store_uses_sqlalchemy_list_when_database_url_is_postgres():
    session_factory = MagicMock()
    expected = [{"id": "conv-1", "thread_id": "thread-1", "title": "团队", "workspace_id": "", "created_at": "t", "updated_at": "t"}]

    with patch("src.persistence.conversation_store.settings") as mock_settings:
        mock_settings.storage.database_url = POSTGRES_URL
        with patch("src.persistence.conversation_store.get_session_factory", return_value=session_factory) as mock_factory:
            with patch(
                "src.persistence.conversation_store.conversation_repository.list_conversations_with_session",
                return_value=expected,
            ) as mock_list:
                assert conversation_store.list_conversations(workspace_id="") == expected

    mock_factory.assert_called_once_with(POSTGRES_URL)
    mock_list.assert_called_once_with(session_factory, "")


def test_conversation_store_uses_sqlite_create_by_default():
    expected = {"id": "conv-1", "thread_id": "thread-1", "title": "SQLite", "workspace_id": "", "created_at": "t", "updated_at": "t"}

    with patch("src.persistence.conversation_store.settings") as mock_settings:
        mock_settings.storage.database_url = "sqlite:///runtime/local/conversations.db"
        with patch("src.persistence.conversation_store.get_connection") as mock_get_connection:
            with patch(
                "src.persistence.conversation_store.conversation_repository.create_conversation",
                return_value=expected,
            ) as mock_create:
                assert conversation_store.create_conversation("SQLite", workspace_id="") == expected

    mock_create.assert_called_once_with(mock_get_connection, "SQLite", None, "")

