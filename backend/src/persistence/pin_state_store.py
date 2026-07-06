"""Pinned source state facade selecting SQLite or SQLAlchemy backends."""

from __future__ import annotations

from src.config.settings import settings
from src.persistence import pin_state_repository
from src.persistence.database import get_connection
from src.persistence.sqlalchemy_database import get_session_factory, is_postgres_url


def _session_factory():
    return get_session_factory(settings.storage.database_url)


def _use_sqlalchemy() -> bool:
    return is_postgres_url(settings.storage.database_url)


def clear_pin_state(thread_id: str) -> None:
    if _use_sqlalchemy():
        pin_state_repository.clear_pin_state_with_session(_session_factory(), thread_id)
        return
    pin_state_repository.clear_pin_state(get_connection, thread_id)


def replace_pin_state(
    thread_id: str,
    pinned_chunk_ids: list[str] | None = None,
    excluded_chunk_ids: list[str] | None = None,
) -> None:
    if _use_sqlalchemy():
        pin_state_repository.replace_pin_state_with_session(
            _session_factory(),
            thread_id,
            pinned_chunk_ids,
            excluded_chunk_ids,
        )
        return
    pin_state_repository.replace_pin_state(
        get_connection,
        thread_id,
        pinned_chunk_ids,
        excluded_chunk_ids,
    )


def load_pin_state(thread_id: str) -> list[dict]:
    if _use_sqlalchemy():
        return pin_state_repository.load_pin_state_with_session(_session_factory(), thread_id)
    return pin_state_repository.load_pin_state(get_connection, thread_id)


def load_pin_state_summary(thread_id: str) -> dict:
    if _use_sqlalchemy():
        return pin_state_repository.load_pin_state_summary_with_session(_session_factory(), thread_id)
    return pin_state_repository.load_pin_state_summary(get_connection, thread_id)
