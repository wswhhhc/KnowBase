from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.persistence import message_store


POSTGRES_URL = "postgresql+psycopg://knowbase:pw@postgres/knowbase"


def test_message_store_uses_sqlalchemy_get_when_database_url_is_postgres():
    session_factory = MagicMock()
    expected = [{"id": 1, "role": "assistant", "content": "团队"}]

    with patch("src.persistence.message_store.settings") as mock_settings:
        mock_settings.storage.database_url = POSTGRES_URL
        with patch("src.persistence.message_store.get_session_factory", return_value=session_factory) as mock_factory:
            with patch(
                "src.persistence.message_store.message_repository.get_messages_with_session",
                return_value=expected,
            ) as mock_get:
                assert message_store.get_messages("conv-1") == expected

    mock_factory.assert_called_once_with(POSTGRES_URL)
    mock_get.assert_called_once_with(session_factory, "conv-1")


def test_message_store_uses_sqlite_add_by_default():
    with patch("src.persistence.message_store.settings") as mock_settings:
        mock_settings.storage.database_url = "sqlite:///runtime/local/conversations.db"
        with patch("src.persistence.message_store.get_connection") as mock_get_connection:
            with patch("src.persistence.message_store.message_repository.add_message", return_value=1) as mock_add:
                assert message_store.add_message("conv-1", "user", "hello") == 1

    mock_add.assert_called_once_with(
        mock_get_connection,
        "conv-1",
        "user",
        "hello",
        sources=None,
        quality_reason="",
        debug_info="{}",
    )
