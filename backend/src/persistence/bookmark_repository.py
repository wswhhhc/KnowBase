"""Bookmark repository functions backed by SQLite."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Callable


ConnectionFactory = Callable[[], sqlite3.Connection]


def create_bookmark(
    get_conn: ConnectionFactory,
    workspace_id: str = "",
    conversation_id: str = "",
    message_id: int = 0,
    chunk_id: str = "",
    note: str = "",
    content: str = "",
    source: str = "",
    tags: str = "",
) -> dict:
    conn = get_conn()
    if chunk_id:
        existing = conn.execute(
            "SELECT id, workspace_id, conversation_id, message_id, chunk_id, note, content, source, tags, created_at "
            "FROM bookmarks WHERE workspace_id = ? AND chunk_id = ? ORDER BY id LIMIT 1",
            (workspace_id, chunk_id),
        ).fetchone()
        if existing:
            conn.close()
            return dict(existing)

    now = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        "INSERT INTO bookmarks (workspace_id, conversation_id, message_id, chunk_id, note, content, source, tags, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (workspace_id, conversation_id, message_id, chunk_id, note, content, source, tags, now),
    )
    conn.commit()
    bookmark_id = cursor.lastrowid
    conn.close()
    return {"id": bookmark_id, "workspace_id": workspace_id, "conversation_id": conversation_id,
            "message_id": message_id, "chunk_id": chunk_id, "note": note, "content": content,
            "source": source, "tags": tags, "created_at": now}


def list_bookmarks(get_conn: ConnectionFactory, workspace_id: str | None = None, search: str | None = None) -> list[dict]:
    conn = get_conn()
    clauses: list[str] = []
    params: list[str] = []
    if workspace_id is not None:
        clauses.append("workspace_id = ?")
        params.append(workspace_id)
    if search:
        like = f"%{search}%"
        clauses.append("(content LIKE ? OR note LIKE ? OR tags LIKE ?)")
        params.extend([like, like, like])

    query = "SELECT id, workspace_id, conversation_id, message_id, chunk_id, note, content, source, tags, created_at FROM bookmarks"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_bookmark(get_conn: ConnectionFactory, bm_id: int, **kwargs) -> dict | None:
    allowed = {"note", "tags"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return None
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [bm_id]
    conn = get_conn()
    conn.execute(f"UPDATE bookmarks SET {set_clause} WHERE id = ?", values)
    conn.commit()
    row = conn.execute(
        "SELECT id, workspace_id, conversation_id, message_id, chunk_id, note, content, source, tags, created_at FROM bookmarks WHERE id = ?",
        (bm_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_bookmark(get_conn: ConnectionFactory, bm_id: int) -> bool:
    conn = get_conn()
    cursor = conn.execute("DELETE FROM bookmarks WHERE id = ?", (bm_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0
