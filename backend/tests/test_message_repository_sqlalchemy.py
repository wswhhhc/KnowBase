from __future__ import annotations

import json

from sqlalchemy.orm import sessionmaker

from src.persistence.conversation_repository import create_conversation_with_session
from src.persistence.message_repository import (
    add_message_with_session,
    get_messages_with_session,
    list_assistant_debug_pairs_with_session,
    update_feedback_with_session,
)
from src.persistence.schema import conversations, metadata
from src.persistence.sqlalchemy_database import create_engine_for_url


def _session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def test_sqlalchemy_add_and_get_messages_parses_sources_and_debug_info():
    session_factory = _session_factory()
    conversation = create_conversation_with_session(session_factory, "消息")

    message_id = add_message_with_session(
        session_factory,
        conversation["id"],
        "assistant",
        "回答",
        sources=[{"source": "doc.md", "page": "", "score": ""}],
        quality_reason="ok",
        debug_info=json.dumps({"used_rerank": True}),
    )

    messages = get_messages_with_session(session_factory, conversation["id"])

    assert messages[0]["id"] == message_id
    assert messages[0]["sources"] == [{"source": "doc.md", "page": None, "score": None}]
    assert messages[0]["debug_info"] == {"used_rerank": True}


def test_sqlalchemy_add_message_updates_conversation_timestamp():
    session_factory = _session_factory()
    conversation = create_conversation_with_session(session_factory, "更新时间")
    before = conversation["updated_at"]

    add_message_with_session(session_factory, conversation["id"], "user", "hello")

    with session_factory() as session:
        after = session.execute(
            conversations.select().with_only_columns(conversations.c.updated_at)
        ).scalar_one()

    assert after >= before


def test_sqlalchemy_list_assistant_debug_pairs_matches_user_and_assistant_per_thread():
    session_factory = _session_factory()
    first = create_conversation_with_session(session_factory, "A", thread_id="thread-a")
    second = create_conversation_with_session(session_factory, "B", thread_id="thread-b")

    add_message_with_session(session_factory, first["id"], "user", "年假几天")
    add_message_with_session(
        session_factory,
        first["id"],
        "assistant",
        "5天",
        debug_info=json.dumps({"used_rerank": True}),
    )
    add_message_with_session(session_factory, second["id"], "assistant", "orphan")

    pairs = list_assistant_debug_pairs_with_session(session_factory)

    assert pairs == [
        {
            "thread_id": "thread-a",
            "question": "年假几天",
            "debug_info": {"used_rerank": True},
            "created_at": pairs[0]["created_at"],
        }
    ]


def test_sqlalchemy_update_feedback_can_be_scoped_to_conversation():
    session_factory = _session_factory()
    conversation = create_conversation_with_session(session_factory, "反馈")
    other = create_conversation_with_session(session_factory, "其他")
    msg_id = add_message_with_session(session_factory, conversation["id"], "assistant", "回答")

    assert update_feedback_with_session(session_factory, msg_id, "like", conv_id=other["id"]) is False
    assert update_feedback_with_session(
        session_factory,
        msg_id,
        "like",
        conv_id=conversation["id"],
        category="quality",
        detail="useful",
    ) is True

    message = get_messages_with_session(session_factory, conversation["id"])[0]
    assert message["feedback"] == "like"

