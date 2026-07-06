"""Message persistence facade selecting SQLite or SQLAlchemy backends."""

from __future__ import annotations

from src.config.settings import settings
from src.persistence import message_repository
from src.persistence.database import get_connection
from src.persistence.sqlalchemy_database import get_session_factory, is_postgres_url


def _session_factory():
    return get_session_factory(settings.storage.database_url)


def _use_sqlalchemy() -> bool:
    return is_postgres_url(settings.storage.database_url)


def add_message(
    conv_id: str,
    role: str,
    content: str,
    *,
    sources: list | None = None,
    quality_reason: str = "",
    debug_info: str = "{}",
) -> int:
    if _use_sqlalchemy():
        return message_repository.add_message_with_session(
            _session_factory(),
            conv_id,
            role,
            content,
            sources=sources,
            quality_reason=quality_reason,
            debug_info=debug_info,
        )
    return message_repository.add_message(
        get_connection,
        conv_id,
        role,
        content,
        sources=sources,
        quality_reason=quality_reason,
        debug_info=debug_info,
    )


def get_messages(conv_id: str) -> list[dict]:
    if _use_sqlalchemy():
        return message_repository.get_messages_with_session(_session_factory(), conv_id)
    return message_repository.get_messages(get_connection, conv_id)


def list_assistant_debug_pairs() -> list[dict]:
    if _use_sqlalchemy():
        return message_repository.list_assistant_debug_pairs_with_session(_session_factory())
    return message_repository.list_assistant_debug_pairs(get_connection)


def update_feedback(
    msg_row_id: int,
    feedback: str,
    *,
    conv_id: str | None = None,
    category: str | None = None,
    detail: str | None = None,
) -> bool:
    if _use_sqlalchemy():
        return message_repository.update_feedback_with_session(
            _session_factory(),
            msg_row_id,
            feedback,
            conv_id=conv_id,
            category=category,
            detail=detail,
        )
    return message_repository.update_feedback(
        get_connection,
        msg_row_id,
        feedback,
        conv_id=conv_id,
        category=category,
        detail=detail,
    )
