from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.persistence import pin_state_store


POSTGRES_URL = "postgresql+psycopg://knowbase:pw@postgres/knowbase"


def test_pin_state_store_uses_sqlalchemy_summary_when_database_url_is_postgres():
    session_factory = MagicMock()
    expected = {"thread_id": "thread-1", "pinned_chunk_ids": [], "excluded_chunk_ids": []}

    with patch("src.persistence.pin_state_store.settings") as mock_settings:
        mock_settings.storage.database_url = POSTGRES_URL
        with patch("src.persistence.pin_state_store.get_session_factory", return_value=session_factory) as mock_factory:
            with patch(
                "src.persistence.pin_state_store.pin_state_repository.load_pin_state_summary_with_session",
                return_value=expected,
            ) as mock_summary:
                assert pin_state_store.load_pin_state_summary("thread-1") == expected

    mock_factory.assert_called_once_with(POSTGRES_URL)
    mock_summary.assert_called_once_with(session_factory, "thread-1")


def test_pin_state_store_uses_sqlite_replace_by_default():
    with patch("src.persistence.pin_state_store.settings") as mock_settings:
        mock_settings.storage.database_url = "sqlite:///runtime/local/conversations.db"
        with patch("src.persistence.pin_state_store.get_connection") as mock_get_connection:
            with patch("src.persistence.pin_state_store.pin_state_repository.replace_pin_state") as mock_replace:
                pin_state_store.replace_pin_state("thread-1", ["pin"], ["exclude"])

    mock_replace.assert_called_once_with(mock_get_connection, "thread-1", ["pin"], ["exclude"])
