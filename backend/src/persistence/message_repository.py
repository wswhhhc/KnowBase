"""Message repository functions backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Callable


ConnectionFactory = Callable[[], sqlite3.Connection]
ConversationGetter = Callable[[str], dict | None]
MessageGetter = Callable[[str], list[dict]]


def add_message(
    get_conn: ConnectionFactory,
    conv_id: str,
    role: str,
    content: str,
    sources: list | None = None,
    quality_reason: str = "",
    debug_info: str = "{}",
) -> int:
    conn = get_conn()
    now = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        "INSERT INTO messages (conversation_id, role, content, sources, quality_reason, debug_info, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (conv_id, role, content, json.dumps(sources or [], ensure_ascii=False), quality_reason, debug_info, now),
    )
    msg_id = cursor.lastrowid
    conn.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        (now, conv_id),
    )
    conn.commit()
    conn.close()
    return msg_id


def get_messages(get_conn: ConnectionFactory, conv_id: str) -> list[dict]:
    conn = get_conn()
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
            for source in raw:
                for key in ("chunk_index", "page", "score"):
                    if key in source and source[key] == "":
                        source[key] = None
            msg["sources"] = raw
        except (json.JSONDecodeError, TypeError):
            msg["sources"] = []
        try:
            msg["debug_info"] = json.loads(msg.get("debug_info", "{}"))
        except (json.JSONDecodeError, TypeError):
            msg["debug_info"] = {}
        result.append(msg)
    return result


def list_assistant_debug_pairs(get_conn: ConnectionFactory) -> list[dict]:
    conn = get_conn()
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


def update_feedback(
    get_conn: ConnectionFactory,
    msg_row_id: int,
    feedback: str,
    conv_id: str | None = None,
    category: str | None = None,
    detail: str | None = None,
) -> bool:
    conn = get_conn()
    if conv_id:
        row = conn.execute(
            "SELECT id FROM messages WHERE id = ? AND conversation_id = ?", (msg_row_id, conv_id)
        ).fetchone()
        if not row:
            conn.close()
            return False
    cursor = conn.execute(
        "UPDATE messages SET feedback = ?, feedback_category = ?, feedback_detail = ? WHERE id = ?",
        (feedback, category, detail, msg_row_id),
    )
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def export_conversation(
    conv_id: str,
    *,
    fmt: str,
    include_sources: bool,
    include_debug: bool,
    get_conversation: ConversationGetter,
    get_messages_for_conversation: MessageGetter,
):
    conv = get_conversation(conv_id)
    if not conv:
        return "" if fmt == "markdown" else {}

    messages = get_messages_for_conversation(conv_id)

    if fmt == "json":
        export_msgs = []
        for msg in messages:
            entry = {
                "role": "用户" if msg["role"] == "user" else "助手",
                "content": msg["content"],
            }
            if include_sources and msg.get("sources"):
                entry["sources"] = msg["sources"]
            if include_debug and msg.get("debug_info"):
                entry["debug_info"] = msg["debug_info"]
            export_msgs.append(entry)
        return {
            "title": conv["title"],
            "created_at": conv["created_at"],
            "messages": export_msgs,
        }

    parts = [f"# {conv['title']}\n\n"]
    for msg in messages:
        role_label = "[用户]" if msg["role"] == "user" else "[助手]"
        parts.append(f"### {role_label}\n{msg['content']}\n")
        if include_sources and msg["sources"]:
            parts.append(f"**来源：** {', '.join(source.get('source', '?') for source in msg['sources'])}\n")
        if include_debug:
            debug_info = msg.get("debug_info", {})
            if isinstance(debug_info, str):
                try:
                    debug_info = json.loads(debug_info)
                except (json.JSONDecodeError, TypeError):
                    debug_info = {}
            if debug_info:
                debug_lines = []
                if debug_info.get("evidence_level"):
                    debug_lines.append(f"证据等级：{debug_info['evidence_level']}")
                if debug_info.get("evidence_summary"):
                    debug_lines.append(f"证据摘要：{debug_info['evidence_summary']}")
                if debug_info.get("outcome_category"):
                    debug_lines.append(f"结果分类：{debug_info['outcome_category']}")
                if debug_info.get("rewritten_question"):
                    debug_lines.append(f"改写后查询：{debug_info['rewritten_question']}")
                if debug_info.get("retry_count", 0) > 0:
                    debug_lines.append(f"重试次数：{debug_info['retry_count']}")
                if debug_info.get("used_rerank"):
                    debug_lines.append("使用重排：是")
                if debug_info.get("used_web_search"):
                    debug_lines.append(f"联网搜索：是（{debug_info.get('web_results_count', 0)} 条）")
                if debug_info.get("nodes"):
                    debug_lines.append(f"节点数：{len(debug_info['nodes'])}")
                if debug_lines:
                    parts.append("*调试信息：*  " + "  \n".join(debug_lines) + "\n")
            elif msg.get("quality_reason"):
                parts.append(f"*质量检查：{msg['quality_reason']}*\n")
        parts.append("\n---\n\n")
    return "".join(parts)
