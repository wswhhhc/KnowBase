from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from src.persistence.pin_state_repository import (
    clear_pin_state_with_session,
    load_pin_state_summary_with_session,
    load_pin_state_with_session,
    replace_pin_state_with_session,
)
from src.persistence.schema import metadata
from src.persistence.sqlalchemy_database import create_engine_for_url


def _session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def test_sqlalchemy_replace_pin_state_dedupes_and_excludes_pinned_ids():
    session_factory = _session_factory()

    replace_pin_state_with_session(
        session_factory,
        "thread-1",
        pinned_chunk_ids=["doc:1", "doc:1"],
        excluded_chunk_ids=["doc:1", "doc:2", "doc:2"],
    )

    assert load_pin_state_with_session(session_factory, "thread-1") == [
        {"chunk_id": "doc:1", "action": "pin"},
        {"chunk_id": "doc:2", "action": "exclude"},
    ]
    assert load_pin_state_summary_with_session(session_factory, "thread-1") == {
        "thread_id": "thread-1",
        "pinned_chunk_ids": ["doc:1"],
        "excluded_chunk_ids": ["doc:2"],
    }


def test_sqlalchemy_replace_pin_state_clears_previous_entries():
    session_factory = _session_factory()

    replace_pin_state_with_session(session_factory, "thread-1", pinned_chunk_ids=["old"])
    replace_pin_state_with_session(session_factory, "thread-1", excluded_chunk_ids=["new"])

    assert load_pin_state_with_session(session_factory, "thread-1") == [
        {"chunk_id": "new", "action": "exclude"}
    ]


def test_sqlalchemy_clear_pin_state_removes_thread_entries():
    session_factory = _session_factory()

    replace_pin_state_with_session(session_factory, "thread-1", pinned_chunk_ids=["doc:1"])
    clear_pin_state_with_session(session_factory, "thread-1")

    assert load_pin_state_with_session(session_factory, "thread-1") == []
