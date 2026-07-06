from __future__ import annotations

from sqlalchemy import select

from src.persistence.schema import bookmarks, conversations, messages, metadata, pinned_sources, workspaces
from src.persistence.sqlite_import import import_sqlite_business_data
from src.persistence.sqlalchemy_database import create_engine_for_url


def _sqlite_url(path) -> str:
    return f"sqlite:///{path}"


def test_import_sqlite_business_data_copies_phase1_tables(tmp_path):
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    source_engine = create_engine_for_url(_sqlite_url(source_path))
    target_engine = create_engine_for_url(_sqlite_url(target_path))
    metadata.create_all(source_engine)
    metadata.create_all(target_engine)

    with source_engine.begin() as conn:
        conn.execute(
            workspaces.insert().values(
                id="ws-a",
                name="团队",
                description="",
                created_at="2026-07-06T00:00:00+00:00",
                updated_at="2026-07-06T00:00:00+00:00",
            )
        )
        conn.execute(
            conversations.insert().values(
                id="conv-a",
                thread_id="thread-a",
                title="迁移",
                workspace_id="ws-a",
                created_at="2026-07-06T00:00:00+00:00",
                updated_at="2026-07-06T00:01:00+00:00",
            )
        )
        conn.execute(
            messages.insert().values(
                id=7,
                conversation_id="conv-a",
                role="assistant",
                content="回答",
                sources="[]",
                quality_reason="ok",
                debug_info="{}",
                created_at="2026-07-06T00:02:00+00:00",
            )
        )
        conn.execute(
            bookmarks.insert().values(
                id=3,
                workspace_id="ws-a",
                conversation_id="conv-a",
                message_id=7,
                chunk_id="doc:1",
                note="note",
                content="片段",
                source="doc.md",
                tags="tag",
                created_at="2026-07-06T00:03:00+00:00",
            )
        )
        conn.execute(
            pinned_sources.insert().values(
                id=5,
                thread_id="thread-a",
                chunk_id="doc:1",
                action="pin",
                created_at="2026-07-06T00:04:00+00:00",
            )
        )

    counts = import_sqlite_business_data(source_path, _sqlite_url(target_path))

    assert counts == {
        "workspaces": 1,
        "conversations": 1,
        "messages": 1,
        "bookmarks": 1,
        "pinned_sources": 1,
    }
    with target_engine.connect() as conn:
        assert conn.execute(select(workspaces.c.id)).scalar_one() == "ws-a"
        assert conn.execute(select(messages.c.id)).scalar_one() == 7
        assert conn.execute(select(bookmarks.c.id)).scalar_one() == 3
        assert conn.execute(select(pinned_sources.c.id)).scalar_one() == 5


def test_import_sqlite_business_data_truncates_target_before_copy(tmp_path):
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    source_engine = create_engine_for_url(_sqlite_url(source_path))
    target_engine = create_engine_for_url(_sqlite_url(target_path))
    metadata.create_all(source_engine)
    metadata.create_all(target_engine)

    with source_engine.begin() as conn:
        conn.execute(
            workspaces.insert().values(
                id="source",
                name="source",
                description="",
                created_at="t",
                updated_at="t",
            )
        )
    with target_engine.begin() as conn:
        conn.execute(
            workspaces.insert().values(
                id="stale",
                name="stale",
                description="",
                created_at="t",
                updated_at="t",
            )
        )

    import_sqlite_business_data(source_path, _sqlite_url(target_path), truncate=True)

    with target_engine.connect() as conn:
        assert conn.execute(select(workspaces.c.id)).scalars().all() == ["source"]


def test_import_sqlite_business_data_dry_run_does_not_write(tmp_path):
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    source_engine = create_engine_for_url(_sqlite_url(source_path))
    target_engine = create_engine_for_url(_sqlite_url(target_path))
    metadata.create_all(source_engine)
    metadata.create_all(target_engine)

    with source_engine.begin() as conn:
        conn.execute(
            workspaces.insert().values(
                id="source",
                name="source",
                description="",
                created_at="t",
                updated_at="t",
            )
        )

    counts = import_sqlite_business_data(source_path, _sqlite_url(target_path), dry_run=True)

    assert counts["workspaces"] == 1
    with target_engine.connect() as conn:
        assert conn.execute(select(workspaces.c.id)).all() == []
