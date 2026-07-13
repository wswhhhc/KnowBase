from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from src.persistence.conversation_repository import (
    ConversationWorkspaceMismatchError,
    create_conversation_with_session,
    delete_conversation_with_session,
    delete_conversations_with_session,
    get_conversation_by_thread_with_session,
    get_conversation_with_session,
    list_conversations_with_session,
    persist_conversation_turn_with_session,
    update_title_with_session,
)
from src.persistence.schema import conversations, messages, metadata, pinned_sources
from src.persistence.sqlalchemy_database import create_engine_for_url


def _session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def test_sqlalchemy_conversation_crud_and_workspace_filtering():
    session_factory = _session_factory()

    default_conv = create_conversation_with_session(session_factory, "默认对话")
    ws_conv = create_conversation_with_session(session_factory, "团队对话", workspace_id="ws-1")
    update_ok = update_title_with_session(session_factory, ws_conv["id"], "团队对话 A")

    assert update_ok is True
    assert get_conversation_with_session(session_factory, ws_conv["id"])["title"] == "团队对话 A"
    assert get_conversation_by_thread_with_session(session_factory, ws_conv["thread_id"])["id"] == ws_conv["id"]

    default_list = list_conversations_with_session(session_factory, workspace_id="")
    ws_list = list_conversations_with_session(session_factory, workspace_id="ws-1")

    assert [conversation["id"] for conversation in default_list] == [default_conv["id"]]
    assert [conversation["id"] for conversation in ws_list] == [ws_conv["id"]]


def test_sqlalchemy_schema_rejects_duplicate_thread_ids_across_workspaces():
    session_factory = _session_factory()

    create_conversation_with_session(
        session_factory,
        "工作区 A",
        thread_id="shared-thread",
        workspace_id="ws-a",
    )

    with pytest.raises(sa.exc.IntegrityError):
        create_conversation_with_session(
            session_factory,
            "工作区 B",
            thread_id="shared-thread",
            workspace_id="ws-b",
        )


def test_sqlalchemy_persist_turn_rejects_workspace_mismatch_without_partial_writes():
    session_factory = _session_factory()
    create_conversation_with_session(
        session_factory,
        "工作区 A",
        thread_id="shared-thread",
        workspace_id="ws-a",
    )

    with pytest.raises(ConversationWorkspaceMismatchError):
        persist_conversation_turn_with_session(
            session_factory,
            title="不会使用",
            question="不能跨工作区写入",
            thread_id="shared-thread",
            workspace_id="ws-b",
            answer="拒绝写入",
            final_sources=[],
            final_quality="",
            debug_payload="{}",
            pinned_chunk_ids=["chunk-pin"],
            excluded_chunk_ids=["chunk-exclude"],
        )

    with session_factory() as session:
        assert session.execute(messages.select()).all() == []
        assert session.execute(pinned_sources.select()).all() == []


def test_sqlalchemy_persist_turn_commits_conversation_pin_state_and_messages():
    session_factory = _session_factory()

    conversation_id, assistant_message_id = persist_conversation_turn_with_session(
        session_factory,
        title="事务对话",
        question="用户问题",
        thread_id="thread-transaction",
        workspace_id="ws-a",
        answer="助手回答",
        final_sources=[{"source": "doc.md", "content": "证据"}],
        final_quality="通过",
        debug_payload='{"evidence_level":"strong"}',
        pinned_chunk_ids=["chunk-pin", "chunk-pin"],
        excluded_chunk_ids=["chunk-pin", "chunk-exclude"],
    )

    with session_factory() as session:
        conversation = session.execute(
            sa.select(conversations).where(conversations.c.id == conversation_id)
        ).mappings().one()
        stored_messages = session.execute(
            messages.select().order_by(messages.c.id)
        ).mappings().all()
        stored_pins = session.execute(
            pinned_sources.select().order_by(pinned_sources.c.id)
        ).mappings().all()

    assert conversation["workspace_id"] == "ws-a"
    assert [message["role"] for message in stored_messages] == ["user", "assistant"]
    assert stored_messages[1]["id"] == assistant_message_id
    assert stored_messages[1]["sources"] == '[{"source": "doc.md", "content": "证据"}]'
    assert [(pin["chunk_id"], pin["action"]) for pin in stored_pins] == [
        ("chunk-pin", "pin"),
        ("chunk-exclude", "exclude"),
    ]


def test_sqlalchemy_persist_turn_rolls_back_all_rows_when_assistant_insert_fails():
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.execute(
            sa.text(
                "CREATE TRIGGER fail_assistant_insert "
                "BEFORE INSERT ON messages "
                "WHEN NEW.role = 'assistant' "
                "BEGIN SELECT RAISE(ABORT, 'assistant insert failed'); END"
            )
        )

    with pytest.raises(sa.exc.IntegrityError, match="assistant insert failed"):
        persist_conversation_turn_with_session(
            session_factory,
            title="回滚测试",
            question="用户问题",
            thread_id="thread-rollback",
            workspace_id="ws-a",
            answer="助手回答",
            final_sources=[],
            final_quality="",
            debug_payload="{}",
            pinned_chunk_ids=["chunk-pin"],
            excluded_chunk_ids=["chunk-exclude"],
        )

    with session_factory() as session:
        assert session.execute(conversations.select()).all() == []
        assert session.execute(messages.select()).all() == []
        assert session.execute(pinned_sources.select()).all() == []


def test_sqlalchemy_persist_turn_treats_null_workspace_as_default():
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.execute(
            conversations.insert().values(
                id="conv-null",
                thread_id="thread-null",
                title="历史对话",
                workspace_id=None,
                created_at="now",
                updated_at="now",
            )
        )

    conversation_id, _assistant_message_id = persist_conversation_turn_with_session(
        session_factory,
        title="不会使用",
        question="默认工作区问题",
        thread_id="thread-null",
        workspace_id="",
        answer="默认工作区回答",
        final_sources=[],
        final_quality="",
        debug_payload="{}",
        pinned_chunk_ids=[],
        excluded_chunk_ids=[],
    )

    assert conversation_id == "conv-null"
    with session_factory() as session:
        assert [row.role for row in session.execute(messages.select()).all()] == [
            "user",
            "assistant",
        ]


def _mapping_result(row):
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    return result


def test_sqlalchemy_persist_turn_recovers_same_workspace_unique_insert_race():
    session_factory = MagicMock()
    session = MagicMock()
    session_factory.begin.return_value.__enter__.return_value = session
    session_factory.begin.return_value.__exit__.return_value = False
    session.get_bind.return_value.dialect.name = "postgresql"
    conflict_result = MagicMock()
    conflict_result.scalar_one_or_none.return_value = None
    assistant_result = MagicMock(inserted_primary_key=[42])
    update_result = MagicMock(rowcount=1)
    session.execute.side_effect = [
        _mapping_result(None),
        conflict_result,
        _mapping_result({"id": "conv-winner", "workspace_id": "ws-a"}),
        MagicMock(),
        MagicMock(),
        assistant_result,
        update_result,
    ]

    result = persist_conversation_turn_with_session(
        session_factory,
        title="竞态对话",
        question="用户问题",
        thread_id="shared-thread",
        workspace_id="ws-a",
        answer="助手回答",
        final_sources=[],
        final_quality="",
        debug_payload="{}",
        pinned_chunk_ids=[],
        excluded_chunk_ids=[],
    )

    assert result == ("conv-winner", 42)
    assert session.execute.call_count == 7


def test_sqlalchemy_persist_turn_rejects_cross_workspace_unique_insert_race():
    session_factory = MagicMock()
    session = MagicMock()
    session_factory.begin.return_value.__enter__.return_value = session
    session_factory.begin.return_value.__exit__.return_value = False
    session.get_bind.return_value.dialect.name = "postgresql"
    conflict_result = MagicMock()
    conflict_result.scalar_one_or_none.return_value = None
    session.execute.side_effect = [
        _mapping_result(None),
        conflict_result,
        _mapping_result({"id": "conv-winner", "workspace_id": "ws-b"}),
    ]

    with pytest.raises(ConversationWorkspaceMismatchError):
        persist_conversation_turn_with_session(
            session_factory,
            title="竞态对话",
            question="用户问题",
            thread_id="shared-thread",
            workspace_id="ws-a",
            answer="助手回答",
            final_sources=[],
            final_quality="",
            debug_payload="{}",
            pinned_chunk_ids=[],
            excluded_chunk_ids=[],
        )

    assert session.execute.call_count == 3


def test_sqlalchemy_list_conversations_includes_normalized_last_message_preview():
    session_factory = _session_factory()
    conversation = create_conversation_with_session(session_factory, "预览")

    with session_factory.begin() as session:
        session.execute(
            messages.insert(),
            [
                {
                    "conversation_id": conversation["id"],
                    "role": "user",
                    "content": "第一条",
                    "created_at": "2026-01-01T00:00:00+00:00",
                },
                {
                    "conversation_id": conversation["id"],
                    "role": "assistant",
                    "content": "第二条\n需要压平",
                    "created_at": "2026-01-01T00:00:01+00:00",
                },
            ],
        )

    listed = list_conversations_with_session(session_factory)

    assert listed[0]["last_message_preview"] == "第二条 需要压平"


def test_sqlalchemy_delete_conversation_cascades_messages_and_pin_state():
    session_factory = _session_factory()
    conversation = create_conversation_with_session(session_factory, "删除", thread_id="thread-delete")

    with session_factory.begin() as session:
        session.execute(
            messages.insert().values(
                conversation_id=conversation["id"],
                role="user",
                content="hello",
                created_at="2026-01-01T00:00:00+00:00",
            )
        )
        session.execute(
            pinned_sources.insert().values(
                thread_id="thread-delete",
                chunk_id="chunk-1",
                action="pin",
                created_at="2026-01-01T00:00:00+00:00",
            )
        )

    assert delete_conversation_with_session(session_factory, conversation["id"]) is True
    assert get_conversation_with_session(session_factory, conversation["id"]) is None

    with session_factory() as session:
        assert session.execute(messages.select()).all() == []
        assert session.execute(pinned_sources.select()).all() == []


def test_sqlalchemy_delete_conversations_batch_keeps_unlisted_threads():
    session_factory = _session_factory()
    first = create_conversation_with_session(session_factory, "A", thread_id="thread-a")
    second = create_conversation_with_session(session_factory, "B", thread_id="thread-b")
    kept = create_conversation_with_session(session_factory, "C", thread_id="thread-c")

    with session_factory.begin() as session:
        for thread_id in ("thread-a", "thread-b", "thread-c"):
            session.execute(
                pinned_sources.insert().values(
                    thread_id=thread_id,
                    chunk_id=f"{thread_id}:chunk",
                    action="pin",
                    created_at="2026-01-01T00:00:00+00:00",
                )
            )

    delete_conversations_with_session(session_factory, [first["id"], second["id"]])

    assert get_conversation_with_session(session_factory, first["id"]) is None
    assert get_conversation_with_session(session_factory, second["id"]) is None
    assert get_conversation_with_session(session_factory, kept["id"]) is not None

    with session_factory() as session:
        remaining_thread_ids = [
            row.thread_id for row in session.execute(pinned_sources.select()).all()
        ]

    assert remaining_thread_ids == ["thread-c"]

