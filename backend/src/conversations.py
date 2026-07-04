"""Conversation facade with SQLite-backed persistence repositories."""

import logging
import sqlite3
from pathlib import Path

from src.config.settings import DATA_DIR
from src.persistence import (
    bookmark_repository,
    conversation_repository,
    message_repository,
    pin_state_repository,
    workspace_repository,
)

_DB_PATH = Path(DATA_DIR) / "conversations.db"
logger = logging.getLogger(__name__)


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _run_migrations():
    """Run Alembic migrations to bring the database schema up to date.

    Skip if alembic.ini is missing (e.g. running from a temp test env).
    """
    ini_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    if not ini_path.exists():
        return
    # Only migrate the configured primary database, not patched temp test paths.
    configured_db = (Path(DATA_DIR) / "conversations.db").resolve()
    current_db = _DB_PATH.resolve()
    if current_db != configured_db:
        return
    try:
        from alembic import command
        from alembic.config import Config
    except ModuleNotFoundError:
        logger.warning("Alembic not installed; skipping migrations for %s", _DB_PATH)
        return
    try:
        alembic_cfg = Config(str(ini_path))
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{_DB_PATH}")
        command.upgrade(alembic_cfg, "head")
    except Exception as exc:
        logger.warning("Alembic migration failed: %s", exc)


def init_db():
    """Create tables if they don't exist, then ensure default workspace."""
    _run_migrations()
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id TEXT DEFAULT '',
            conversation_id TEXT DEFAULT '',
            message_id INTEGER DEFAULT 0,
            chunk_id TEXT DEFAULT '',
            note TEXT DEFAULT '',
            content TEXT DEFAULT '',
            source TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '新对话',
            workspace_id TEXT DEFAULT '',
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
            feedback_category TEXT DEFAULT NULL,
            feedback_detail TEXT DEFAULT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
        CREATE TABLE IF NOT EXISTS pinned_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('pin', 'exclude')),
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_pinned_sources_thread ON pinned_sources(thread_id, chunk_id);
    """)
    conn.commit()
    conn.close()
    workspace_repository.ensure_default_workspace(_get_conn)


def create_conversation(title: str = "新对话", thread_id: str | None = None, workspace_id: str = "") -> dict:
    return conversation_repository.create_conversation(_get_conn, title, thread_id, workspace_id)


def get_conversation_by_thread(thread_id: str) -> dict | None:
    return conversation_repository.get_conversation_by_thread(_get_conn, thread_id)


def list_conversations(workspace_id: str | None = None) -> list[dict]:
    return conversation_repository.list_conversations(_get_conn, workspace_id)


def get_conversation(conv_id: str) -> dict | None:
    return conversation_repository.get_conversation(_get_conn, conv_id)


def update_title(conv_id: str, title: str) -> bool:
    return conversation_repository.update_title(_get_conn, conv_id, title)


def delete_conversations(conv_ids: list[str]):
    conversation_repository.delete_conversations(_get_conn, conv_ids)


def delete_conversation(conv_id: str) -> bool:
    return conversation_repository.delete_conversation(_get_conn, conv_id)


def add_message(conv_id: str, role: str, content: str, sources: list | None = None, quality_reason: str = "", debug_info: str = "{}") -> int:
    return message_repository.add_message(_get_conn, conv_id, role, content, sources, quality_reason, debug_info)


def get_messages(conv_id: str) -> list[dict]:
    return message_repository.get_messages(_get_conn, conv_id)


def list_assistant_debug_pairs() -> list[dict]:
    return message_repository.list_assistant_debug_pairs(_get_conn)


def update_feedback(msg_row_id: int, feedback: str, conv_id: str | None = None, category: str | None = None, detail: str | None = None) -> bool:
    return message_repository.update_feedback(_get_conn, msg_row_id, feedback, conv_id, category, detail)


def export_conversation(conv_id: str, fmt: str = "markdown", include_sources: bool = True, include_debug: bool = False):
    return message_repository.export_conversation(
        conv_id,
        fmt=fmt,
        include_sources=include_sources,
        include_debug=include_debug,
        get_conversation=get_conversation,
        get_messages_for_conversation=get_messages,
    )


# ── Bookmarks ──


def create_bookmark(workspace_id: str = "", conversation_id: str = "", message_id: int = 0,
                    chunk_id: str = "", note: str = "", content: str = "", source: str = "",
                    tags: str = "") -> dict:
    return bookmark_repository.create_bookmark(_get_conn, workspace_id, conversation_id, message_id, chunk_id, note, content, source, tags)


def list_bookmarks(workspace_id: str | None = None, search: str | None = None) -> list[dict]:
    return bookmark_repository.list_bookmarks(_get_conn, workspace_id, search)


def update_bookmark(bm_id: int, **kwargs) -> dict | None:
    return bookmark_repository.update_bookmark(_get_conn, bm_id, **kwargs)


def delete_bookmark(bm_id: int) -> bool:
    return bookmark_repository.delete_bookmark(_get_conn, bm_id)


# ── Pinned Sources ──


def clear_pin_state(thread_id: str) -> None:
    pin_state_repository.clear_pin_state(_get_conn, thread_id)


def replace_pin_state(
    thread_id: str,
    pinned_chunk_ids: list[str] | None = None,
    excluded_chunk_ids: list[str] | None = None,
) -> None:
    pin_state_repository.replace_pin_state(_get_conn, thread_id, pinned_chunk_ids, excluded_chunk_ids)


def load_pin_state(thread_id: str) -> list[dict]:
    return pin_state_repository.load_pin_state(_get_conn, thread_id)


def load_pin_state_summary(thread_id: str) -> dict:
    return pin_state_repository.load_pin_state_summary(_get_conn, thread_id)


# ── Workspaces ──


def create_workspace(name: str = "新工作区", description: str = "") -> dict:
    return workspace_repository.create_workspace(_get_conn, name, description)


def list_workspaces() -> list[dict]:
    return workspace_repository.list_workspaces(_get_conn)


def update_workspace(ws_id: str, name: str | None = None, description: str | None = None) -> bool:
    return workspace_repository.update_workspace(_get_conn, ws_id, name, description)


def delete_workspace(ws_id: str) -> bool:
    return workspace_repository.delete_workspace(_get_conn, ws_id)
