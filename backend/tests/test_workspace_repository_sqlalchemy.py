from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from src.persistence.schema import bookmarks, conversations, metadata
from src.persistence.sqlalchemy_database import create_engine_for_url
from src.persistence.workspace_repository import (
    create_workspace_with_session,
    delete_workspace_with_session,
    ensure_default_workspace_with_session,
    get_workspace_with_session,
    list_workspaces_with_session,
    update_workspace_with_session,
)


def _session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def test_sqlalchemy_workspace_crud_preserves_default_first_order():
    session_factory = _session_factory()

    ensure_default_workspace_with_session(session_factory)
    created = create_workspace_with_session(session_factory, "团队空间", "内部资料")
    update_ok = update_workspace_with_session(session_factory, created["id"], name="团队空间 A")

    assert update_ok is True
    assert get_workspace_with_session(session_factory, created["id"])["name"] == "团队空间 A"

    workspaces = list_workspaces_with_session(session_factory)
    assert workspaces[0]["id"] == ""
    assert [workspace["name"] for workspace in workspaces] == ["默认工作区", "团队空间 A"]


def test_sqlalchemy_delete_workspace_reassigns_conversations_and_bookmarks_to_default():
    session_factory = _session_factory()
    ensure_default_workspace_with_session(session_factory)
    workspace = create_workspace_with_session(session_factory, "待删除", "")

    with session_factory.begin() as session:
        session.execute(
            conversations.insert().values(
                id="conv-1",
                thread_id="thread-1",
                title="迁移对话",
                workspace_id=workspace["id"],
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
            )
        )
        session.execute(
            bookmarks.insert().values(
                workspace_id=workspace["id"],
                conversation_id="conv-1",
                message_id=1,
                chunk_id="chunk-1",
                note="note",
                content="content",
                source="source",
                tags="tag",
                created_at="2026-01-01T00:00:00+00:00",
            )
        )

    assert delete_workspace_with_session(session_factory, workspace["id"]) is True

    with session_factory() as session:
        conv_workspace = session.execute(
            conversations.select().with_only_columns(conversations.c.workspace_id)
        ).scalar_one()
        bookmark_workspace = session.execute(
            bookmarks.select().with_only_columns(bookmarks.c.workspace_id)
        ).scalar_one()

    assert conv_workspace == ""
    assert bookmark_workspace == ""

