from __future__ import annotations

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from src.persistence import database


def _alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _insert_conversation(
    engine: sa.Engine,
    *,
    conversation_id: str,
    thread_id: str,
    workspace_id: str,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO conversations "
                "(id, thread_id, title, workspace_id, created_at, updated_at) "
                "VALUES (:id, :thread_id, :title, :workspace_id, :created_at, :updated_at)"
            ),
            {
                "id": conversation_id,
                "thread_id": thread_id,
                "title": conversation_id,
                "workspace_id": workspace_id,
                "created_at": "now",
                "updated_at": "now",
            },
        )


def test_workspace_member_role_migration_removes_admin_role(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    config = _alembic_config(database_url)
    engine = sa.create_engine(database_url, future=True)

    command.upgrade(config, "003")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO users (id, username, password_hash, role, is_active, created_at, updated_at) "
                "VALUES ('user-1', 'editor', 'hash', 'editor', 1, 'now', 'now')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO workspace_members (workspace_id, user_id, role, created_at) "
                "VALUES ('ws-a', 'user-1', 'admin', 'now')"
            )
        )

    command.upgrade(config, "004")

    with engine.begin() as connection:
        migrated_role = connection.execute(sa.text("SELECT role FROM workspace_members")).scalar_one()
        assert migrated_role == "editor"
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO workspace_members (workspace_id, user_id, role, created_at) "
                    "VALUES ('ws-b', 'user-1', 'admin', 'now')"
                )
            )


def test_conversation_thread_id_migration_rejects_existing_duplicates(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'duplicate-upgrade.db'}"
    config = _alembic_config(database_url)
    engine = sa.create_engine(database_url, future=True)

    command.upgrade(config, "004")
    _insert_conversation(
        engine,
        conversation_id="conv-a",
        thread_id="shared-thread",
        workspace_id="ws-a",
    )
    _insert_conversation(
        engine,
        conversation_id="conv-b",
        thread_id="shared-thread",
        workspace_id="ws-b",
    )

    with pytest.raises(sa.exc.IntegrityError):
        command.upgrade(config, "005")

    with engine.connect() as connection:
        revision = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
    index_names = {index["name"] for index in sa.inspect(engine).get_indexes("conversations")}

    assert revision == "004"
    assert "uq_conversations_thread_id" not in index_names


def test_conversation_thread_id_unique_constraint_is_reversible(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'reversible-constraint.db'}"
    config = _alembic_config(database_url)
    engine = sa.create_engine(database_url, future=True)

    command.upgrade(config, "005")
    _insert_conversation(
        engine,
        conversation_id="conv-a",
        thread_id="shared-thread",
        workspace_id="ws-a",
    )

    with pytest.raises(sa.exc.IntegrityError):
        _insert_conversation(
            engine,
            conversation_id="conv-b",
            thread_id="shared-thread",
            workspace_id="ws-b",
        )

    command.downgrade(config, "004")
    _insert_conversation(
        engine,
        conversation_id="conv-b",
        thread_id="shared-thread",
        workspace_id="ws-b",
    )

    with engine.connect() as connection:
        duplicate_count = connection.execute(
            sa.text("SELECT COUNT(*) FROM conversations WHERE thread_id = 'shared-thread'")
        ).scalar_one()

    assert duplicate_count == 2


def test_init_db_sqlite_schema_rejects_duplicate_conversation_thread_ids(tmp_path):
    database_path = tmp_path / "isolated-init.db"
    database_url = f"sqlite:///{database_path}"
    engine = sa.create_engine(database_url, future=True)
    database.set_db_path_override(database_path)

    try:
        database.init_db()
        _insert_conversation(
            engine,
            conversation_id="conv-a",
            thread_id="shared-thread",
            workspace_id="ws-a",
        )

        with pytest.raises(sa.exc.IntegrityError):
            _insert_conversation(
                engine,
                conversation_id="conv-b",
                thread_id="shared-thread",
                workspace_id="ws-b",
            )
    finally:
        engine.dispose()
        database.clear_db_path_override()
