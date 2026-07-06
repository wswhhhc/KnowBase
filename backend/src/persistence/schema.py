"""SQLAlchemy Core schema for the team-edition persistence path."""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Index, Integer, MetaData, Table, Text


metadata = MetaData()

workspaces = Table(
    "workspaces",
    metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("description", Text, server_default=""),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
)

bookmarks = Table(
    "bookmarks",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("workspace_id", Text, server_default=""),
    Column("conversation_id", Text, server_default=""),
    Column("message_id", Integer, server_default="0"),
    Column("chunk_id", Text, server_default=""),
    Column("note", Text, server_default=""),
    Column("content", Text, server_default=""),
    Column("source", Text, server_default=""),
    Column("tags", Text, server_default=""),
    Column("created_at", Text, nullable=False),
)

conversations = Table(
    "conversations",
    metadata,
    Column("id", Text, primary_key=True),
    Column("thread_id", Text, nullable=False),
    Column("title", Text, nullable=False, server_default="新对话"),
    Column("workspace_id", Text, server_default=""),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
)

messages = Table(
    "messages",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", Text, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
    Column("role", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("sources", Text, server_default="[]"),
    Column("quality_reason", Text, server_default=""),
    Column("debug_info", Text, server_default="{}"),
    Column("feedback", Text, nullable=True),
    Column("feedback_category", Text, nullable=True),
    Column("feedback_detail", Text, nullable=True),
    Column("created_at", Text, nullable=False),
    Index("idx_messages_conv", "conversation_id", "id"),
)

pinned_sources = Table(
    "pinned_sources",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("thread_id", Text, nullable=False),
    Column("chunk_id", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    CheckConstraint("action IN ('pin', 'exclude')", name="ck_pinned_sources_action"),
    Index("idx_pinned_sources_thread", "thread_id", "chunk_id"),
)

users = Table(
    "users",
    metadata,
    Column("id", Text, primary_key=True),
    Column("username", Text, nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("role", Text, nullable=False),
    Column("is_active", Boolean, nullable=False, server_default="1"),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    CheckConstraint("role IN ('admin', 'editor', 'viewer')", name="ck_users_role"),
)

workspace_members = Table(
    "workspace_members",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("workspace_id", Text, nullable=False),
    Column("user_id", Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("role", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    CheckConstraint("role IN ('admin', 'editor', 'viewer')", name="ck_workspace_members_role"),
    Index("idx_workspace_members_workspace_user", "workspace_id", "user_id", unique=True),
)

refresh_tokens = Table(
    "refresh_tokens",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("token_hash", Text, nullable=False, unique=True),
    Column("expires_at", Text, nullable=False),
    Column("revoked_at", Text, nullable=True),
    Column("created_at", Text, nullable=False),
    Index("idx_refresh_tokens_user", "user_id"),
)

audit_logs = Table(
    "audit_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("actor_user_id", Text, nullable=True),
    Column("action", Text, nullable=False),
    Column("target_type", Text, server_default=""),
    Column("target_id", Text, server_default=""),
    Column("metadata_json", Text, server_default="{}"),
    Column("created_at", Text, nullable=False),
    Index("idx_audit_logs_actor_created", "actor_user_id", "created_at"),
)

