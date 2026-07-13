from __future__ import annotations

import os
import threading
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from src.persistence import conversation_repository
from src.persistence.conversation_repository import (
    ConversationWorkspaceMismatchError,
    create_conversation_with_session,
    delete_conversation_with_session,
    persist_conversation_turn_with_session,
)
from src.persistence.pin_state_repository import normalize_pin_inputs
from src.persistence.schema import conversations, messages, pinned_sources
from src.persistence.sqlalchemy_database import create_engine_for_url


POSTGRES_TEST_URL = os.getenv("KNOWBASE_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="KNOWBASE_TEST_POSTGRES_URL is not configured",
)


def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture(scope="module")
def postgres_session_factory():
    database_name = make_url(POSTGRES_TEST_URL).database or ""
    if database_name.lower() != "knowbase_test":
        pytest.fail("Postgres integration tests require the dedicated 'knowbase_test' database")

    config = _alembic_config(POSTGRES_TEST_URL)
    command.upgrade(config, "005")
    engine = create_engine_for_url(POSTGRES_TEST_URL)

    @sa.event.listens_for(engine, "connect")
    def set_test_timeouts(dbapi_connection, _connection_record):
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '5s'")
            cursor.execute("SET statement_timeout = '8s'")

    factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )

    try:
        yield factory
    finally:
        with factory.begin() as session:
            session.execute(
                sa.text(
                    "TRUNCATE TABLE messages, pinned_sources, conversations "
                    "RESTART IDENTITY"
                )
            )
        engine.dispose()


@pytest.fixture(autouse=True)
def clean_chat_tables(postgres_session_factory):
    with postgres_session_factory.begin() as session:
        session.execute(
            sa.text(
                "TRUNCATE TABLE messages, pinned_sources, conversations "
                "RESTART IDENTITY"
            )
        )


def _turn_kwargs(workspace_id: str, *, pin: str = "") -> dict:
    return {
        "title": "Postgres 并发对话",
        "question": f"{workspace_id} 的问题",
        "thread_id": "shared-thread",
        "workspace_id": workspace_id,
        "answer": f"{workspace_id} 的回答",
        "final_sources": [],
        "final_quality": "",
        "debug_payload": "{}",
        "pinned_chunk_ids": [pin] if pin else [],
        "excluded_chunk_ids": [],
    }


def _join_threads(threads: list[threading.Thread]) -> None:
    for thread in threads:
        if thread.ident is not None:
            thread.join(timeout=10)
    assert all(thread.ident is None or not thread.is_alive() for thread in threads)


def _racing_uuid_factory():
    barrier = threading.Barrier(2)
    candidate_ids = iter([uuid4(), uuid4()])
    candidate_lock = threading.Lock()

    def racing_uuid():
        barrier.wait(timeout=5)
        with candidate_lock:
            return next(candidate_ids)

    return racing_uuid


def test_postgres_same_workspace_new_thread_race_commits_both_turns(
    postgres_session_factory,
):
    results: list[tuple[str, int]] = []
    errors: list[BaseException] = []

    def persist_turn():
        try:
            results.append(
                persist_conversation_turn_with_session(
                    postgres_session_factory,
                    **_turn_kwargs("ws-a"),
                )
            )
        except BaseException as exc:  # pragma: no cover - surfaced by assertion
            errors.append(exc)

    threads = [threading.Thread(target=persist_turn) for _ in range(2)]
    with patch(
        "src.persistence.conversation_repository.uuid4",
        side_effect=_racing_uuid_factory(),
    ):
        for thread in threads:
            thread.start()
        _join_threads(threads)

    assert errors == []
    assert len(results) == 2
    assert len({conversation_id for conversation_id, _message_id in results}) == 1

    with postgres_session_factory() as session:
        assert len(session.execute(conversations.select()).all()) == 1
        assert [row.role for row in session.execute(messages.select().order_by(messages.c.id)).all()] == [
            "user",
            "assistant",
            "user",
            "assistant",
        ]


def test_postgres_cross_workspace_new_thread_race_rejects_loser_without_partial_rows(
    postgres_session_factory,
):
    results: list[tuple[str, tuple[str, int]]] = []
    errors: list[tuple[str, BaseException]] = []

    def persist_turn(workspace_id: str):
        try:
            results.append(
                (
                    workspace_id,
                    persist_conversation_turn_with_session(
                        postgres_session_factory,
                        **_turn_kwargs(workspace_id, pin=f"chunk-{workspace_id}"),
                    ),
                )
            )
        except BaseException as exc:  # pragma: no cover - surfaced by assertion
            errors.append((workspace_id, exc))

    threads = [
        threading.Thread(target=persist_turn, args=(workspace_id,))
        for workspace_id in ("ws-a", "ws-b")
    ]
    with patch(
        "src.persistence.conversation_repository.uuid4",
        side_effect=_racing_uuid_factory(),
    ):
        for thread in threads:
            thread.start()
        _join_threads(threads)

    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0][1], ConversationWorkspaceMismatchError)

    winner_workspace = results[0][0]
    with postgres_session_factory() as session:
        conversation = session.execute(conversations.select()).mappings().one()
        stored_messages = session.execute(messages.select().order_by(messages.c.id)).all()
        stored_pins = session.execute(pinned_sources.select()).mappings().all()

    assert conversation["workspace_id"] == winner_workspace
    assert [row.role for row in stored_messages] == ["user", "assistant"]
    assert [(row["chunk_id"], row["action"]) for row in stored_pins] == [
        (f"chunk-{winner_workspace}", "pin"),
    ]


def test_postgres_workspace_move_waits_for_persist_transaction(
    postgres_session_factory,
):
    conversation = create_conversation_with_session(
        postgres_session_factory,
        "已有对话",
        thread_id="shared-thread",
        workspace_id="ws-a",
    )
    binding_locked = threading.Event()
    allow_persist = threading.Event()
    move_attempted = threading.Event()
    move_completed = threading.Event()
    errors: list[BaseException] = []

    def blocking_normalize(pinned_chunk_ids=None, excluded_chunk_ids=None):
        binding_locked.set()
        if not allow_persist.wait(timeout=5):
            raise TimeoutError("persist test was not released")
        return normalize_pin_inputs(pinned_chunk_ids, excluded_chunk_ids)

    def persist_turn():
        try:
            persist_conversation_turn_with_session(
                postgres_session_factory,
                **_turn_kwargs("ws-a"),
            )
        except BaseException as exc:  # pragma: no cover - surfaced by assertion
            errors.append(exc)

    def move_workspace():
        if not binding_locked.wait(timeout=5):
            errors.append(TimeoutError("conversation row was not locked"))
            return
        move_attempted.set()
        try:
            with postgres_session_factory.begin() as session:
                session.execute(
                    sa.update(conversations)
                    .where(conversations.c.id == conversation["id"])
                    .values(workspace_id="")
                )
        except BaseException as exc:  # pragma: no cover - surfaced by assertion
            errors.append(exc)
        finally:
            move_completed.set()

    threads = [threading.Thread(target=persist_turn), threading.Thread(target=move_workspace)]
    try:
        with patch(
            "src.persistence.conversation_repository.normalize_pin_inputs",
            side_effect=blocking_normalize,
        ):
            threads[0].start()
            assert binding_locked.wait(timeout=5)
            threads[1].start()
            assert move_attempted.wait(timeout=5)
            assert not move_completed.wait(timeout=0.2)
            allow_persist.set()
            _join_threads(threads)
    finally:
        allow_persist.set()
        _join_threads(threads)

    assert errors == []
    with postgres_session_factory() as session:
        stored_conversation = session.execute(
            conversations.select().where(conversations.c.id == conversation["id"])
        ).mappings().one()
        assert stored_conversation["workspace_id"] == ""
        assert len(session.execute(messages.select()).all()) == 2


def test_postgres_delete_waits_for_persist_and_leaves_no_orphans(
    postgres_session_factory,
):
    conversation = create_conversation_with_session(
        postgres_session_factory,
        "已有对话",
        thread_id="shared-thread",
        workspace_id="ws-a",
    )
    binding_locked = threading.Event()
    allow_persist = threading.Event()
    delete_attempted = threading.Event()
    delete_completed = threading.Event()
    errors: list[BaseException] = []

    def blocking_normalize(pinned_chunk_ids=None, excluded_chunk_ids=None):
        binding_locked.set()
        if not allow_persist.wait(timeout=5):
            raise TimeoutError("persist test was not released")
        return normalize_pin_inputs(pinned_chunk_ids, excluded_chunk_ids)

    def persist_turn():
        try:
            persist_conversation_turn_with_session(
                postgres_session_factory,
                **_turn_kwargs("ws-a", pin="chunk-delete"),
            )
        except BaseException as exc:  # pragma: no cover - surfaced by assertion
            errors.append(exc)

    def delete_conversation():
        if not binding_locked.wait(timeout=5):
            errors.append(TimeoutError("conversation row was not locked"))
            return
        delete_attempted.set()
        try:
            delete_conversation_with_session(
                postgres_session_factory,
                conversation["id"],
            )
        except BaseException as exc:  # pragma: no cover - surfaced by assertion
            errors.append(exc)
        finally:
            delete_completed.set()

    threads = [
        threading.Thread(target=persist_turn),
        threading.Thread(target=delete_conversation),
    ]
    try:
        with patch(
            "src.persistence.conversation_repository.normalize_pin_inputs",
            side_effect=blocking_normalize,
        ):
            threads[0].start()
            assert binding_locked.wait(timeout=5)
            threads[1].start()
            assert delete_attempted.wait(timeout=5)
            assert not delete_completed.wait(timeout=0.2)
            allow_persist.set()
            _join_threads(threads)
    finally:
        allow_persist.set()
        _join_threads(threads)

    assert errors == []
    with postgres_session_factory() as session:
        assert session.execute(conversations.select()).all() == []
        assert session.execute(messages.select()).all() == []
        assert session.execute(pinned_sources.select()).all() == []
