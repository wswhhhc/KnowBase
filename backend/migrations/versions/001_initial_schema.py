"""Create initial schema from conversations.db

Revision ID: 001
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=OFF;")

    op.create_table("workspaces",
        sa.Column("id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''")),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_table("bookmarks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Text(), server_default=sa.text("''")),
        sa.Column("conversation_id", sa.Text(), server_default=sa.text("''")),
        sa.Column("message_id", sa.Integer(), server_default=sa.text("0")),
        sa.Column("chunk_id", sa.Text(), server_default=sa.text("''")),
        sa.Column("note", sa.Text(), server_default=sa.text("''")),
        sa.Column("content", sa.Text(), server_default=sa.text("''")),
        sa.Column("source", sa.Text(), server_default=sa.text("''")),
        sa.Column("tags", sa.Text(), server_default=sa.text("''")),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_table("conversations",
        sa.Column("id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), server_default=sa.text("'新对话'")),
        sa.Column("workspace_id", sa.Text(), server_default=sa.text("''")),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_table("messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.Text(), server_default=sa.text("'[]'")),
        sa.Column("quality_reason", sa.Text(), server_default=sa.text("''")),
        sa.Column("debug_info", sa.Text(), server_default=sa.text("'{}'")),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("feedback_category", sa.Text(), nullable=True),
        sa.Column("feedback_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_messages_conv", "messages", ["conversation_id", "id"])
    op.create_table("pinned_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("chunk_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_pinned_sources_thread", "pinned_sources", ["thread_id", "chunk_id"])

    if bind.dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=ON;")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=OFF;")
    op.drop_table("pinned_sources")
    op.drop_index("idx_messages_conv", table_name="messages")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("bookmarks")
    op.drop_table("workspaces")
    if bind.dialect.name == "sqlite":
        op.execute("PRAGMA foreign_keys=ON;")
