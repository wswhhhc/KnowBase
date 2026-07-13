from __future__ import annotations

import sqlite3
import threading

import pytest

from src.persistence import (
    conversation_repository,
    database,
    message_repository,
    pin_state_repository,
)
from src.persistence.pin_state_repository import normalize_pin_inputs


def _turn_kwargs(**overrides):
    values = {
        "title": "事务对话",
        "question": "用户问题",
        "thread_id": "thread-transaction",
        "workspace_id": "ws-a",
        "answer": "助手回答",
        "final_sources": [{"source": "doc.md", "content": "证据"}],
        "final_quality": "通过",
        "debug_payload": "{}",
        "pinned_chunk_ids": ["chunk-pin"],
        "excluded_chunk_ids": ["chunk-exclude"],
    }
    values.update(overrides)
    return values


def _connection_factory(database_path):
    def connect():
        connection = sqlite3.connect(str(database_path), check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    return connect


def _init_isolated_database(database_path) -> None:
    database.set_db_path_override(database_path)
    try:
        database.init_db()
    finally:
        database.clear_db_path_override()


def test_sqlite_persist_turn_holds_workspace_binding_until_all_writes_commit(
    monkeypatch,
    tmp_path,
):
    database_path = tmp_path / "chat-turn.db"
    _init_isolated_database(database_path)
    get_connection = _connection_factory(database_path)
    conversation = conversation_repository.create_conversation(
        get_connection,
        "已有对话",
        thread_id="thread-transaction",
        workspace_id="ws-a",
    )

    binding_checked = threading.Event()
    allow_persist = threading.Event()
    move_attempted = threading.Event()
    move_completed = threading.Event()
    errors: list[BaseException] = []
    persisted_results: list[tuple[str, int]] = []

    def blocking_normalize(pinned_chunk_ids=None, excluded_chunk_ids=None):
        binding_checked.set()
        if not allow_persist.wait(timeout=5):
            raise TimeoutError("persist test was not released")
        return normalize_pin_inputs(pinned_chunk_ids, excluded_chunk_ids)

    monkeypatch.setattr(
        conversation_repository,
        "normalize_pin_inputs",
        blocking_normalize,
    )

    def persist_turn():
        try:
            persisted_results.append(
                conversation_repository.persist_conversation_turn(
                    get_connection,
                    **_turn_kwargs(),
                )
            )
        except BaseException as exc:  # pragma: no cover - surfaced by assertion
            errors.append(exc)

    def move_workspace():
        if not binding_checked.wait(timeout=5):
            errors.append(TimeoutError("workspace binding was not checked"))
            return
        move_attempted.set()
        connection = get_connection()
        try:
            connection.execute(
                "UPDATE conversations SET workspace_id = '' WHERE id = ?",
                (conversation["id"],),
            )
            connection.commit()
        except BaseException as exc:  # pragma: no cover - surfaced by assertion
            errors.append(exc)
        finally:
            connection.close()
            move_completed.set()

    persist_thread = threading.Thread(target=persist_turn)
    move_thread = threading.Thread(target=move_workspace)
    persist_started = False
    move_started = False

    try:
        persist_thread.start()
        persist_started = True
        assert binding_checked.wait(timeout=5)
        move_thread.start()
        move_started = True
        assert move_attempted.wait(timeout=5)
        assert not move_completed.wait(timeout=0.2)

        allow_persist.set()
        persist_thread.join(timeout=5)
        move_thread.join(timeout=5)

        assert not persist_thread.is_alive()
        assert not move_thread.is_alive()
        assert errors == []
        assert move_completed.is_set()
        assert persisted_results[0][0] == conversation["id"]

        messages = message_repository.get_messages(
            get_connection,
            conversation["id"],
        )
        assert [message["role"] for message in messages] == ["user", "assistant"]
        assert messages[1]["id"] == persisted_results[0][1]
        assert pin_state_repository.load_pin_state(
            get_connection,
            "thread-transaction",
        ) == [
            {"chunk_id": "chunk-pin", "action": "pin"},
            {"chunk_id": "chunk-exclude", "action": "exclude"},
        ]
    finally:
        allow_persist.set()
        if persist_started:
            persist_thread.join(timeout=1)
        if move_started:
            move_thread.join(timeout=1)


def test_sqlite_persist_turn_rolls_back_all_rows_when_assistant_insert_fails(tmp_path):
    database_path = tmp_path / "chat-turn-rollback.db"
    _init_isolated_database(database_path)
    get_connection = _connection_factory(database_path)

    connection = get_connection()
    try:
        connection.execute(
            "CREATE TRIGGER fail_assistant_insert "
            "BEFORE INSERT ON messages "
            "WHEN NEW.role = 'assistant' "
            "BEGIN SELECT RAISE(ABORT, 'assistant insert failed'); END"
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(sqlite3.IntegrityError, match="assistant insert failed"):
        conversation_repository.persist_conversation_turn(
            get_connection,
            **_turn_kwargs(thread_id="thread-rollback"),
        )

    connection = get_connection()
    try:
        assert connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM pinned_sources").fetchone()[0] == 0
    finally:
        connection.close()


def test_sqlite_persist_turn_treats_null_workspace_as_default(tmp_path):
    database_path = tmp_path / "chat-turn-null-workspace.db"
    _init_isolated_database(database_path)
    get_connection = _connection_factory(database_path)

    connection = get_connection()
    try:
        connection.execute(
            "INSERT INTO conversations "
            "(id, thread_id, title, workspace_id, created_at, updated_at) "
            "VALUES ('conv-null', 'thread-null', '历史对话', NULL, 'now', 'now')"
        )
        connection.commit()
    finally:
        connection.close()

    conversation_id, _assistant_message_id = conversation_repository.persist_conversation_turn(
        get_connection,
        **_turn_kwargs(thread_id="thread-null", workspace_id=""),
    )

    assert conversation_id == "conv-null"
    assert [
        message["role"]
        for message in message_repository.get_messages(get_connection, conversation_id)
    ] == ["user", "assistant"]
