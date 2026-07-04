"""Shared SQLite query helpers for conversation repositories."""

from __future__ import annotations


def normalize_preview_text(content: str | None) -> str:
    """Return a single-line preview suitable for sidebar summaries."""
    if not content:
        return ""
    return " ".join(content.split())


def conversation_select_sql(where_clause: str = "") -> str:
    return (
        "SELECT c.id, c.thread_id, c.title, c.workspace_id, c.created_at, c.updated_at, "
        "COALESCE(("
        "SELECT content FROM messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1"
        "), '') AS last_message_preview "
        "FROM conversations c "
        f"{where_clause}"
    )
