from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from src.persistence.conversation_repository import (
    create_conversation_with_session,
    delete_conversation_with_session,
    delete_conversations_with_session,
    get_conversation_by_thread_with_session,
    get_conversation_with_session,
    list_conversations_with_session,
    update_title_with_session,
)
from src.persistence.schema import messages, metadata, pinned_sources
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

