"""Workspace repository functions backed by SQLite."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Callable
from uuid import uuid4

from sqlalchemy import desc, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.persistence.schema import bookmarks, conversations, workspaces


ConnectionFactory = Callable[[], sqlite3.Connection]
SessionFactory = sessionmaker[Session]


def _workspace_from_mapping(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def ensure_default_workspace_with_session(session_factory: SessionFactory) -> None:
    with session_factory.begin() as session:
        row = session.execute(
            select(workspaces.c.id).where(workspaces.c.id == "")
        ).first()
        if row:
            return
        now = datetime.now(UTC).isoformat()
        session.execute(
            workspaces.insert().values(
                id="",
                name="默认工作区",
                description="所有未归类的对话",
                created_at=now,
                updated_at=now,
            )
        )


def create_workspace_with_session(
    session_factory: SessionFactory,
    name: str = "新工作区",
    description: str = "",
) -> dict:
    workspace_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    row = {
        "id": workspace_id,
        "name": name,
        "description": description,
        "created_at": now,
        "updated_at": now,
    }
    with session_factory.begin() as session:
        session.execute(workspaces.insert().values(**row))
    return row


def list_workspaces_with_session(session_factory: SessionFactory) -> list[dict]:
    with session_factory() as session:
        rows = session.execute(
            select(
                workspaces.c.id,
                workspaces.c.name,
                workspaces.c.description,
                workspaces.c.created_at,
                workspaces.c.updated_at,
            ).order_by(desc(workspaces.c.id == ""), workspaces.c.created_at)
        ).mappings().all()
    return [_workspace_from_mapping(row) for row in rows]


def get_workspace_with_session(session_factory: SessionFactory, ws_id: str) -> dict | None:
    with session_factory() as session:
        row = session.execute(
            select(
                workspaces.c.id,
                workspaces.c.name,
                workspaces.c.description,
                workspaces.c.created_at,
                workspaces.c.updated_at,
            ).where(workspaces.c.id == ws_id)
        ).mappings().first()
    return _workspace_from_mapping(row) if row else None


def update_workspace_with_session(
    session_factory: SessionFactory,
    ws_id: str,
    name: str | None = None,
    description: str | None = None,
) -> bool:
    values: dict[str, str] = {}
    if name is not None:
        values["name"] = name
    if description is not None:
        values["description"] = description
    if not values:
        return False
    values["updated_at"] = datetime.now(UTC).isoformat()
    with session_factory.begin() as session:
        result = session.execute(
            update(workspaces).where(workspaces.c.id == ws_id).values(**values)
        )
    return result.rowcount > 0


def delete_workspace_with_session(session_factory: SessionFactory, ws_id: str) -> bool:
    with session_factory.begin() as session:
        session.execute(
            update(conversations).where(conversations.c.workspace_id == ws_id).values(workspace_id="")
        )
        session.execute(
            update(bookmarks).where(bookmarks.c.workspace_id == ws_id).values(workspace_id="")
        )
        result = session.execute(workspaces.delete().where(workspaces.c.id == ws_id))
    return result.rowcount > 0


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


def get_workspace(get_conn: ConnectionFactory, ws_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT id, name, description, created_at, updated_at FROM workspaces WHERE id = ?",
        (ws_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


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
