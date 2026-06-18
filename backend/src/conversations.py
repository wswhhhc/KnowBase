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
            debug_info TEXT DEFAULT '{}',
            feedback TEXT DEFAULT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
    """)
    # 兼容旧库：为已有 messages 表添加 debug_info 列
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN debug_info TEXT DEFAULT '{}'")
    except sqlite3.OperationalError:
        pass  # 列已存在
    conn.commit()
    conn.close()


def create_conversation(title: str = "新对话", thread_id: str | None = None) -> dict:
    """Create a new conversation, return its dict."""
    conn = _get_conn()
    conv_id = str(uuid4())
    actual_thread_id = thread_id or conv_id
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO conversations (id, thread_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (conv_id, actual_thread_id, title, now, now),
    )
    conn.commit()
    conn.close()
    return {"id": conv_id, "thread_id": actual_thread_id, "title": title, "created_at": now, "updated_at": now}


def get_conversation_by_thread(thread_id: str) -> dict | None:
    """Return the conversation that owns this thread_id, or None."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, thread_id, title, created_at, updated_at FROM conversations WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


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


def delete_conversations(conv_ids: list[str]):
    """批量删除多个对话及其消息。"""
    conn = _get_conn()
    placeholders = ",".join("?" for _ in conv_ids)
    conn.execute(f"DELETE FROM messages WHERE conversation_id IN ({placeholders})", conv_ids)
    conn.execute(f"DELETE FROM conversations WHERE id IN ({placeholders})", conv_ids)
    conn.commit()
    conn.close()


def delete_conversation(conv_id: str):
    """Delete a conversation and its messages."""
    conn = _get_conn()
    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
    conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()


def add_message(conv_id: str, role: str, content: str, sources: list | None = None, quality_reason: str = "", debug_info: str = "{}"):
    """Add a message to a conversation."""
    conn = _get_conn()
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, sources, quality_reason, debug_info, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (conv_id, role, content, json.dumps(sources or [], ensure_ascii=False), quality_reason, debug_info, now),
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
        "SELECT id, role, content, sources, quality_reason, debug_info, feedback, created_at "
        "FROM messages WHERE conversation_id = ? ORDER BY id",
        (conv_id,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        msg = dict(r)
        try:
            raw = json.loads(msg["sources"]) if msg["sources"] else []
            # Pydantic 要求 int 字段不能是空字符串，清洗一下
            for s in raw:
                for key in ("chunk_index", "page", "score"):
                    if key in s and s[key] == "":
                        s[key] = None
            msg["sources"] = raw
        except (json.JSONDecodeError, TypeError):
            msg["sources"] = []
        # 确保 debug_info 是 dict
        try:
            msg["debug_info"] = json.loads(msg.get("debug_info", "{}"))
        except (json.JSONDecodeError, TypeError):
            msg["debug_info"] = {}
        result.append(msg)
    return result


def list_assistant_debug_pairs() -> list[dict]:
    """Return assistant debug info paired with the preceding user question."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT c.thread_id, m.role, m.content, m.debug_info, m.created_at "
        "FROM messages m "
        "JOIN conversations c ON c.id = m.conversation_id "
        "ORDER BY c.thread_id, m.id"
    ).fetchall()
    conn.close()

    pairs: list[dict] = []
    pending_user_by_thread: dict[str, str | None] = {}
    for row in rows:
        thread_id = row["thread_id"]
        role = row["role"]
        if role == "user":
            pending_user_by_thread[thread_id] = row["content"]
            continue
        if role != "assistant":
            continue

        question = pending_user_by_thread.get(thread_id)
        if question is None:
            continue

        try:
            debug_info = json.loads(row["debug_info"] or "{}")
        except (json.JSONDecodeError, TypeError):
            debug_info = {}

        pairs.append({
            "thread_id": thread_id,
            "question": question[:100],
            "debug_info": debug_info,
            "created_at": row["created_at"],
        })
        pending_user_by_thread[thread_id] = None

    return pairs


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
