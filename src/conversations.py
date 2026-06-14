"""对话历史管理 — SQLite 持久化存储。"""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from config.settings import ROOT_DIR

_DB_PATH = ROOT_DIR / "data" / "conversations.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '新对话',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            sources TEXT DEFAULT '[]',
            quality_reason TEXT DEFAULT '',
            feedback TEXT DEFAULT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
    """)
    conn.commit()
    conn.close()


def create_conversation(title: str = "新对话") -> dict:
    """Create a new conversation, return its dict."""
    conn = _get_conn()
    conv_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO conversations (id, thread_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (conv_id, conv_id, title, now, now),
    )
    conn.commit()
    conn.close()
    return {"id": conv_id, "thread_id": conv_id, "title": title, "created_at": now, "updated_at": now}


def list_conversations() -> list[dict]:
    """Return all conversations ordered by update time desc."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, thread_id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_conversation(conv_id: str) -> dict | None:
    """Get a single conversation by id."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, thread_id, title, created_at, updated_at FROM conversations WHERE id = ?", (conv_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_title(conv_id: str, title: str):
    """Update conversation title."""
    conn = _get_conn()
    conn.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
        (title, datetime.now(UTC).isoformat(), conv_id),
    )
    conn.commit()
    conn.close()


def delete_conversation(conv_id: str):
    """Delete a conversation and its messages."""
    conn = _get_conn()
    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
    conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()


def add_message(conv_id: str, role: str, content: str, sources: list | None = None, quality_reason: str = ""):
    """Add a message to a conversation."""
    conn = _get_conn()
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, sources, quality_reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (conv_id, role, content, json.dumps(sources or [], ensure_ascii=False), quality_reason, now),
    )
    conn.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        (now, conv_id),
    )
    conn.commit()
    conn.close()


def get_messages(conv_id: str) -> list[dict]:
    """Return all messages for a conversation, ordered by id."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, role, content, sources, quality_reason, feedback, created_at "
        "FROM messages WHERE conversation_id = ? ORDER BY id",
        (conv_id,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        msg = dict(r)
        try:
            msg["sources"] = json.loads(msg["sources"]) if msg["sources"] else []
        except (json.JSONDecodeError, TypeError):
            msg["sources"] = []
        result.append(msg)
    return result


def update_feedback(msg_row_id: int, feedback: str):
    """Update feedback for a message."""
    conn = _get_conn()
    conn.execute("UPDATE messages SET feedback = ? WHERE id = ?", (feedback, msg_row_id))
    conn.commit()
    conn.close()


def export_conversation(conv_id: str) -> str:
    """Export conversation as Markdown."""
    conv = get_conversation(conv_id)
    if not conv:
        return ""
    messages = get_messages(conv_id)
    parts = [f"# {conv['title']}\n\n"]
    for msg in messages:
        role_label = "👤 用户" if msg["role"] == "user" else "🤖 助手"
        parts.append(f"### {role_label}\n{msg['content']}\n")
        if msg["sources"]:
            parts.append(f"**来源：** {', '.join(s.get('source', '?') for s in msg['sources'])}\n")
        if msg["quality_reason"]:
            parts.append(f"*质量检查：{msg['quality_reason']}*\n")
        parts.append("\n---\n\n")
    return "".join(parts)
