"""Conversation repository functions backed by SQLite."""

from __future__ import annotations

from datetime import UTC, datetime
import sqlite3
from typing import Callable
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.persistence.schema import conversations, messages, pinned_sources
from src.persistence.sqlite_helpers import conversation_select_sql, normalize_preview_text


ConnectionFactory = Callable[[], sqlite3.Connection]
SessionFactory = sessionmaker[Session]


def _conversation_from_mapping(row) -> dict:
    conversation = {
        "id": row["id"],
        "thread_id": row["thread_id"],
        "title": row["title"],
        "workspace_id": row["workspace_id"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_message_preview": normalize_preview_text(row.get("last_message_preview")),
    }
    return conversation


def _conversation_select():
    last_message_preview = (
        select(messages.c.content)
        .where(messages.c.conversation_id == conversations.c.id)
        .order_by(messages.c.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    return select(
        conversations.c.id,
        conversations.c.thread_id,
        conversations.c.title,
        conversations.c.workspace_id,
        conversations.c.created_at,
        conversations.c.updated_at,
        func.coalesce(last_message_preview, "").label("last_message_preview"),
    )


def create_conversation_with_session(
    session_factory: SessionFactory,
    title: str = "新对话",
    thread_id: str | None = None,
    workspace_id: str = "",
) -> dict:
    conv_id = str(uuid4())
    actual_thread_id = thread_id or conv_id
    now = datetime.now(UTC).isoformat()
    row = {
        "id": conv_id,
        "thread_id": actual_thread_id,
        "title": title,
        "workspace_id": workspace_id,
        "created_at": now,
        "updated_at": now,
    }
    with session_factory.begin() as session:
        session.execute(conversations.insert().values(**row))
    return row


def get_conversation_by_thread_with_session(session_factory: SessionFactory, thread_id: str) -> dict | None:
    with session_factory() as session:
        row = session.execute(
            _conversation_select().where(conversations.c.thread_id == thread_id)
        ).mappings().first()
    return _conversation_from_mapping(row) if row else None


def list_conversations_with_session(session_factory: SessionFactory, workspace_id: str | None = None) -> list[dict]:
    statement = _conversation_select().order_by(conversations.c.updated_at.desc())
    if workspace_id is not None:
        statement = statement.where(conversations.c.workspace_id == workspace_id)
    with session_factory() as session:
        rows = session.execute(statement).mappings().all()
    return [_conversation_from_mapping(row) for row in rows]


def get_conversation_with_session(session_factory: SessionFactory, conv_id: str) -> dict | None:
    with session_factory() as session:
        row = session.execute(
            _conversation_select().where(conversations.c.id == conv_id)
        ).mappings().first()
    return _conversation_from_mapping(row) if row else None


def update_title_with_session(session_factory: SessionFactory, conv_id: str, title: str) -> bool:
    with session_factory.begin() as session:
        result = session.execute(
            update(conversations)
            .where(conversations.c.id == conv_id)
            .values(title=title, updated_at=datetime.now(UTC).isoformat())
        )
    return result.rowcount > 0


def delete_conversations_with_session(session_factory: SessionFactory, conv_ids: list[str]) -> None:
    if not conv_ids:
        return
    with session_factory.begin() as session:
        thread_rows = session.execute(
            select(conversations.c.thread_id).where(conversations.c.id.in_(conv_ids))
        ).all()
        thread_ids = [row.thread_id for row in thread_rows]
        session.execute(delete(messages).where(messages.c.conversation_id.in_(conv_ids)))
        session.execute(delete(conversations).where(conversations.c.id.in_(conv_ids)))
        if thread_ids:
            session.execute(delete(pinned_sources).where(pinned_sources.c.thread_id.in_(thread_ids)))


def delete_conversation_with_session(session_factory: SessionFactory, conv_id: str) -> bool:
    with session_factory.begin() as session:
        conv = session.execute(
            select(conversations.c.thread_id).where(conversations.c.id == conv_id)
        ).first()
        session.execute(delete(messages).where(messages.c.conversation_id == conv_id))
        result = session.execute(delete(conversations).where(conversations.c.id == conv_id))
        if conv:
            session.execute(delete(pinned_sources).where(pinned_sources.c.thread_id == conv.thread_id))
    return result.rowcount > 0


def create_conversation(get_conn: ConnectionFactory, title: str = "新对话", thread_id: str | None = None, workspace_id: str = "") -> dict:
    conn = get_conn()
    conv_id = str(uuid4())
    actual_thread_id = thread_id or conv_id
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO conversations (id, thread_id, title, workspace_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (conv_id, actual_thread_id, title, workspace_id, now, now),
    )
    conn.commit()
    conn.close()
    return {"id": conv_id, "thread_id": actual_thread_id, "title": title, "workspace_id": workspace_id, "created_at": now, "updated_at": now}


def get_conversation_by_thread(get_conn: ConnectionFactory, thread_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        conversation_select_sql("WHERE c.thread_id = ?"),
        (thread_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    conversation = dict(row)
    conversation["last_message_preview"] = normalize_preview_text(conversation.get("last_message_preview"))
    return conversation


def list_conversations(get_conn: ConnectionFactory, workspace_id: str | None = None) -> list[dict]:
    conn = get_conn()
    if workspace_id is not None:
        rows = conn.execute(
            conversation_select_sql("WHERE c.workspace_id = ? ORDER BY c.updated_at DESC"),
            (workspace_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            conversation_select_sql("ORDER BY c.updated_at DESC")
        ).fetchall()
    conn.close()
    conversations = [dict(r) for r in rows]
    for conversation in conversations:
        conversation["last_message_preview"] = normalize_preview_text(conversation.get("last_message_preview"))
    return conversations


def get_conversation(get_conn: ConnectionFactory, conv_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        conversation_select_sql("WHERE c.id = ?"), (conv_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    conversation = dict(row)
    conversation["last_message_preview"] = normalize_preview_text(conversation.get("last_message_preview"))
    return conversation


def update_title(get_conn: ConnectionFactory, conv_id: str, title: str) -> bool:
    conn = get_conn()
    cursor = conn.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
        (title, datetime.now(UTC).isoformat(), conv_id),
    )
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def delete_conversations(get_conn: ConnectionFactory, conv_ids: list[str]) -> None:
    if not conv_ids:
        return
    conn = get_conn()
    placeholders = ",".join("?" for _ in conv_ids)
    thread_rows = conn.execute(
        f"SELECT thread_id FROM conversations WHERE id IN ({placeholders})",
        conv_ids,
    ).fetchall()
    thread_ids = [row["thread_id"] for row in thread_rows]
    conn.execute(f"DELETE FROM messages WHERE conversation_id IN ({placeholders})", conv_ids)
    conn.execute(f"DELETE FROM conversations WHERE id IN ({placeholders})", conv_ids)
    if thread_ids:
        thread_placeholders = ",".join("?" for _ in thread_ids)
        conn.execute(
            f"DELETE FROM pinned_sources WHERE thread_id IN ({thread_placeholders})",
            thread_ids,
        )
    conn.commit()
    conn.close()


def delete_conversation(get_conn: ConnectionFactory, conv_id: str) -> bool:
    conn = get_conn()
    conv = conn.execute("SELECT thread_id FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
    cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    if conv:
        conn.execute("DELETE FROM pinned_sources WHERE thread_id = ?", (conv["thread_id"],))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0
