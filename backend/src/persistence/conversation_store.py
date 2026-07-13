"""Conversation persistence facade selecting SQLite or SQLAlchemy backends."""

from __future__ import annotations

from src.config.settings import settings
from src.persistence import conversation_repository
from src.persistence.database import get_connection
from src.persistence.sqlalchemy_database import get_session_factory, is_postgres_url


def _session_factory():
    return get_session_factory(settings.storage.database_url)


def _use_sqlalchemy() -> bool:
    return is_postgres_url(settings.storage.database_url)


def create_conversation(
    title: str = "新对话",
    thread_id: str | None = None,
    workspace_id: str = "",
) -> dict:
    if _use_sqlalchemy():
        return conversation_repository.create_conversation_with_session(
            _session_factory(),
            title,
            thread_id,
            workspace_id,
        )
    return conversation_repository.create_conversation(get_connection, title, thread_id, workspace_id)


def persist_conversation_turn(
    *,
    title: str,
    question: str,
    thread_id: str,
    workspace_id: str,
    answer: str,
    final_sources: list,
    final_quality: str,
    debug_payload: str,
    pinned_chunk_ids: list[str],
    excluded_chunk_ids: list[str],
) -> tuple[str, int]:
    if _use_sqlalchemy():
        return conversation_repository.persist_conversation_turn_with_session(
            _session_factory(),
            title=title,
            question=question,
            thread_id=thread_id,
            workspace_id=workspace_id,
            answer=answer,
            final_sources=final_sources,
            final_quality=final_quality,
            debug_payload=debug_payload,
            pinned_chunk_ids=pinned_chunk_ids,
            excluded_chunk_ids=excluded_chunk_ids,
        )
    return conversation_repository.persist_conversation_turn(
        get_connection,
        title=title,
        question=question,
        thread_id=thread_id,
        workspace_id=workspace_id,
        answer=answer,
        final_sources=final_sources,
        final_quality=final_quality,
        debug_payload=debug_payload,
        pinned_chunk_ids=pinned_chunk_ids,
        excluded_chunk_ids=excluded_chunk_ids,
    )


def get_conversation_by_thread(thread_id: str) -> dict | None:
    if _use_sqlalchemy():
        return conversation_repository.get_conversation_by_thread_with_session(_session_factory(), thread_id)
    return conversation_repository.get_conversation_by_thread(get_connection, thread_id)


def list_conversations(workspace_id: str | None = None) -> list[dict]:
    if _use_sqlalchemy():
        return conversation_repository.list_conversations_with_session(_session_factory(), workspace_id)
    return conversation_repository.list_conversations(get_connection, workspace_id)


def get_conversation(conv_id: str) -> dict | None:
    if _use_sqlalchemy():
        return conversation_repository.get_conversation_with_session(_session_factory(), conv_id)
    return conversation_repository.get_conversation(get_connection, conv_id)


def update_title(conv_id: str, title: str) -> bool:
    if _use_sqlalchemy():
        return conversation_repository.update_title_with_session(_session_factory(), conv_id, title)
    return conversation_repository.update_title(get_connection, conv_id, title)


def delete_conversations(conv_ids: list[str]) -> None:
    if _use_sqlalchemy():
        conversation_repository.delete_conversations_with_session(_session_factory(), conv_ids)
        return
    conversation_repository.delete_conversations(get_connection, conv_ids)


def delete_conversation(conv_id: str) -> bool:
    if _use_sqlalchemy():
        return conversation_repository.delete_conversation_with_session(_session_factory(), conv_id)
    return conversation_repository.delete_conversation(get_connection, conv_id)

