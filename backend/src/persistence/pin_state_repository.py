"""Pinned source state repository functions backed by SQLite."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Callable


ConnectionFactory = Callable[[], sqlite3.Connection]


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
    pinned_chunk_ids = list(dict.fromkeys(pinned_chunk_ids or []))
    excluded_chunk_ids = [
        chunk_id for chunk_id in dict.fromkeys(excluded_chunk_ids or [])
        if chunk_id not in pinned_chunk_ids
    ]

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
