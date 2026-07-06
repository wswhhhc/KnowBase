from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.persistence import bookmark_store


POSTGRES_URL = "postgresql+psycopg://knowbase:pw@postgres/knowbase"


def test_bookmark_store_uses_sqlalchemy_list_when_database_url_is_postgres():
    session_factory = MagicMock()
    expected = [{"id": 1, "workspace_id": "ws-a"}]

    with patch("src.persistence.bookmark_store.settings") as mock_settings:
        mock_settings.storage.database_url = POSTGRES_URL
        with patch("src.persistence.bookmark_store.get_session_factory", return_value=session_factory) as mock_factory:
            with patch(
                "src.persistence.bookmark_store.bookmark_repository.list_bookmarks_with_session",
                return_value=expected,
            ) as mock_list:
                assert bookmark_store.list_bookmarks(workspace_id="ws-a", search="Alpha") == expected

    mock_factory.assert_called_once_with(POSTGRES_URL)
    mock_list.assert_called_once_with(session_factory, "ws-a", "Alpha")


def test_bookmark_store_uses_sqlite_create_by_default():
    expected = {"id": 1, "workspace_id": ""}

    with patch("src.persistence.bookmark_store.settings") as mock_settings:
        mock_settings.storage.database_url = "sqlite:///runtime/local/conversations.db"
        with patch("src.persistence.bookmark_store.get_connection") as mock_get_connection:
            with patch("src.persistence.bookmark_store.bookmark_repository.create_bookmark", return_value=expected) as mock_create:
                assert bookmark_store.create_bookmark(content="片段") == expected

    mock_create.assert_called_once_with(
        mock_get_connection,
        "",
        "",
        0,
        "",
        "",
        "片段",
        "",
        "",
    )
