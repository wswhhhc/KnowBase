"""Pinned source state repository functions backed by SQLite."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Callable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from src.persistence.schema import pinned_sources


ConnectionFactory = Callable[[], sqlite3.Connection]
SessionFactory = sessionmaker[Session]


def _normalize_pin_inputs(
    pinned_chunk_ids: list[str] | None = None,
    excluded_chunk_ids: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    pinned = list(dict.fromkeys(pinned_chunk_ids or []))
    excluded = [
        chunk_id for chunk_id in dict.fromkeys(excluded_chunk_ids or [])
        if chunk_id not in pinned
    ]
    return pinned, excluded


def clear_pin_state_with_session(session_factory: SessionFactory, thread_id: str) -> None:
    with session_factory.begin() as session:
        session.execute(delete(pinned_sources).where(pinned_sources.c.thread_id == thread_id))


def replace_pin_state_with_session(
    session_factory: SessionFactory,
    thread_id: str,
    pinned_chunk_ids: list[str] | None = None,
    excluded_chunk_ids: list[str] | None = None,
) -> None:
    pinned_chunk_ids, excluded_chunk_ids = _normalize_pin_inputs(pinned_chunk_ids, excluded_chunk_ids)

    now = datetime.now(UTC).isoformat()
    rows = [
        {"thread_id": thread_id, "chunk_id": chunk_id, "action": "pin", "created_at": now}
        for chunk_id in pinned_chunk_ids
    ]
    rows.extend(
        {"thread_id": thread_id, "chunk_id": chunk_id, "action": "exclude", "created_at": now}
        for chunk_id in excluded_chunk_ids
    )
    with session_factory.begin() as session:
        session.execute(delete(pinned_sources).where(pinned_sources.c.thread_id == thread_id))
        if rows:
            session.execute(pinned_sources.insert(), rows)


def load_pin_state_with_session(session_factory: SessionFactory, thread_id: str) -> list[dict]:
    with session_factory() as session:
        rows = session.execute(
            select(pinned_sources.c.chunk_id, pinned_sources.c.action)
            .where(pinned_sources.c.thread_id == thread_id)
            .order_by(pinned_sources.c.id)
        ).mappings().all()
    return [dict(row) for row in rows]


def load_pin_state_summary_with_session(session_factory: SessionFactory, thread_id: str) -> dict:
    entries = load_pin_state_with_session(session_factory, thread_id)
    return {
        "thread_id": thread_id,
        "pinned_chunk_ids": [entry["chunk_id"] for entry in entries if entry["action"] == "pin"],
        "excluded_chunk_ids": [entry["chunk_id"] for entry in entries if entry["action"] == "exclude"],
    }


def clear_pin_state(get_conn: ConnectionFactory, thread_id: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM pinned_sources WHERE thread_id = ?", (thread_id,))
    conn.commit()
    conn.close()


def replace_pin_state(
    get_conn: ConnectionFactory,
    thread_id: str,
    pinned_chunk_ids: list[str] | None = None,
    excluded_chunk_ids: list[str] | None = None,
) -> None:
    pinned_chunk_ids, excluded_chunk_ids = _normalize_pin_inputs(pinned_chunk_ids, excluded_chunk_ids)

    conn = get_conn()
    now = datetime.now(UTC).isoformat()
    conn.execute("DELETE FROM pinned_sources WHERE thread_id = ?", (thread_id,))
    rows = [(thread_id, chunk_id, "pin", now) for chunk_id in pinned_chunk_ids]
    rows.extend((thread_id, chunk_id, "exclude", now) for chunk_id in excluded_chunk_ids)
    if rows:
        conn.executemany(
            "INSERT INTO pinned_sources (thread_id, chunk_id, action, created_at) VALUES (?, ?, ?, ?)",
            rows,
        )
    conn.commit()
    conn.close()


def load_pin_state(get_conn: ConnectionFactory, thread_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT chunk_id, action FROM pinned_sources WHERE thread_id = ? ORDER BY id",
        (thread_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def load_pin_state_summary(get_conn: ConnectionFactory, thread_id: str) -> dict:
    entries = load_pin_state(get_conn, thread_id)
    return {
        "thread_id": thread_id,
        "pinned_chunk_ids": [entry["chunk_id"] for entry in entries if entry["action"] == "pin"],
        "excluded_chunk_ids": [entry["chunk_id"] for entry in entries if entry["action"] == "exclude"],
    }
