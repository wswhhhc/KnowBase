"""Workspace repository functions backed by SQLite."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Callable
from uuid import uuid4


ConnectionFactory = Callable[[], sqlite3.Connection]


def ensure_default_workspace(get_conn: ConnectionFactory) -> None:
    conn = get_conn()
    row = conn.execute("SELECT id FROM workspaces WHERE id = ''").fetchone()
    if not row:
        now = datetime.now(UTC).isoformat()
        conn.execute(
            "INSERT INTO workspaces (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("", "默认工作区", "所有未归类的对话", now, now),
        )
        conn.commit()
    conn.close()


def create_workspace(get_conn: ConnectionFactory, name: str = "新工作区", description: str = "") -> dict:
    conn = get_conn()
    workspace_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO workspaces (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (workspace_id, name, description, now, now),
    )
    conn.commit()
    conn.close()
    return {"id": workspace_id, "name": name, "description": description, "created_at": now, "updated_at": now}


def list_workspaces(get_conn: ConnectionFactory) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT id, name, description, created_at, updated_at FROM workspaces ORDER BY id = '' DESC, created_at").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_workspace(get_conn: ConnectionFactory, ws_id: str, name: str | None = None, description: str | None = None) -> bool:
    conn = get_conn()
    now = datetime.now(UTC).isoformat()
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if not updates:
        conn.close()
        return False
    updates.append("updated_at = ?")
    params.append(now)
    params.append(ws_id)
    cursor = conn.execute(f"UPDATE workspaces SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def delete_workspace(get_conn: ConnectionFactory, ws_id: str) -> bool:
    conn = get_conn()
    conn.execute("UPDATE conversations SET workspace_id = '' WHERE workspace_id = ?", (ws_id,))
    conn.execute("UPDATE bookmarks SET workspace_id = '' WHERE workspace_id = ?", (ws_id,))
    cursor = conn.execute("DELETE FROM workspaces WHERE id = ?", (ws_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0
