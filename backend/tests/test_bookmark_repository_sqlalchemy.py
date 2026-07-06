from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from src.persistence.bookmark_repository import (
    create_bookmark_with_session,
    delete_bookmark_with_session,
    list_bookmarks_with_session,
    update_bookmark_with_session,
)
from src.persistence.schema import metadata
from src.persistence.sqlalchemy_database import create_engine_for_url


def _session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def test_sqlalchemy_create_bookmark_deduplicates_workspace_chunk_pair():
    session_factory = _session_factory()

    first = create_bookmark_with_session(
        session_factory,
        workspace_id="ws-a",
        chunk_id="doc:1",
        content="first",
    )
    second = create_bookmark_with_session(
        session_factory,
        workspace_id="ws-a",
        chunk_id="doc:1",
        content="second",
    )

    assert second["id"] == first["id"]
    assert list_bookmarks_with_session(session_factory, workspace_id="ws-a") == [first]


def test_sqlalchemy_list_bookmarks_filters_by_workspace_and_search():
    session_factory = _session_factory()

    create_bookmark_with_session(session_factory, workspace_id="ws-a", content="Alpha 片段", tags="policy")
    create_bookmark_with_session(session_factory, workspace_id="ws-b", content="Alpha 片段", tags="policy")
    create_bookmark_with_session(session_factory, workspace_id="ws-a", content="Beta 片段", tags="other")

    results = list_bookmarks_with_session(session_factory, workspace_id="ws-a", search="Alpha")

    assert len(results) == 1
    assert results[0]["workspace_id"] == "ws-a"
    assert results[0]["content"] == "Alpha 片段"


def test_sqlalchemy_update_and_delete_bookmark():
    session_factory = _session_factory()
    bookmark = create_bookmark_with_session(session_factory, note="old", tags="a")

    updated = update_bookmark_with_session(session_factory, bookmark["id"], note="new", tags="b", content="ignored")

    assert updated is not None
    assert updated["note"] == "new"
    assert updated["tags"] == "b"
    assert updated["content"] == ""
    assert delete_bookmark_with_session(session_factory, bookmark["id"]) is True
    assert list_bookmarks_with_session(session_factory) == []
