from __future__ import annotations

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config


def _alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


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

    command.upgrade(config, "head")

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
