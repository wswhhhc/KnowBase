"""Bookmark persistence facade selecting SQLite or SQLAlchemy backends."""

from __future__ import annotations

from src.config.settings import settings
from src.persistence import bookmark_repository
from src.persistence.database import get_connection
from src.persistence.sqlalchemy_database import get_session_factory, is_postgres_url


def _session_factory():
    return get_session_factory(settings.storage.database_url)


def _use_sqlalchemy() -> bool:
    return is_postgres_url(settings.storage.database_url)


def create_bookmark(
    workspace_id: str = "",
    conversation_id: str = "",
    message_id: int = 0,
    chunk_id: str = "",
    note: str = "",
    content: str = "",
    source: str = "",
    tags: str = "",
) -> dict:
    if _use_sqlalchemy():
        return bookmark_repository.create_bookmark_with_session(
            _session_factory(),
            workspace_id,
            conversation_id,
            message_id,
            chunk_id,
            note,
            content,
            source,
            tags,
        )
    return bookmark_repository.create_bookmark(
        get_connection,
        workspace_id,
        conversation_id,
        message_id,
        chunk_id,
        note,
        content,
        source,
        tags,
    )


def list_bookmarks(workspace_id: str | None = None, search: str | None = None) -> list[dict]:
    if _use_sqlalchemy():
        return bookmark_repository.list_bookmarks_with_session(_session_factory(), workspace_id, search)
    return bookmark_repository.list_bookmarks(get_connection, workspace_id, search)


def get_bookmark(bm_id: int) -> dict | None:
    if _use_sqlalchemy():
        return bookmark_repository.get_bookmark_with_session(_session_factory(), bm_id)
    return bookmark_repository.get_bookmark(get_connection, bm_id)


def update_bookmark(bm_id: int, **kwargs) -> dict | None:
    if _use_sqlalchemy():
        return bookmark_repository.update_bookmark_with_session(_session_factory(), bm_id, **kwargs)
    return bookmark_repository.update_bookmark(get_connection, bm_id, **kwargs)


def delete_bookmark(bm_id: int) -> bool:
    if _use_sqlalchemy():
        return bookmark_repository.delete_bookmark_with_session(_session_factory(), bm_id)
    return bookmark_repository.delete_bookmark(get_connection, bm_id)
