"""SQLite connection/bootstrap helpers shared by persistence repositories."""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

from src.config.constants import DATA_DIR
from src.persistence import workspace_repository

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path(DATA_DIR) / "conversations.db"


def get_db_path() -> Path:
    """Return the active database path, respecting test-time overrides."""
    conversations_module = sys.modules.get("src.conversations")
    if conversations_module is not None:
        overridden = getattr(conversations_module, "_DB_PATH", None)
        if overridden is not None:
            return Path(overridden)
    return _DEFAULT_DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def run_migrations() -> None:
    """Run Alembic migrations to bring the database schema up to date."""
    ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    if not ini_path.exists():
        return

    configured_db = (Path(DATA_DIR) / "conversations.db").resolve()
    current_db = get_db_path().resolve()
    if current_db != configured_db:
        return

    try:
        from alembic import command
        from alembic.config import Config
    except ModuleNotFoundError:
        logger.warning("Alembic not installed; skipping migrations for %s", current_db)
        return

    try:
        alembic_cfg = Config(str(ini_path))
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{current_db}")
        command.upgrade(alembic_cfg, "head")
    except Exception as exc:
        logger.warning("Alembic migration failed: %s", exc)


def init_db() -> None:
    """Create tables if they don't exist, then ensure default workspace."""
    run_migrations()
    conn = get_connection()
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
    workspace_repository.ensure_default_workspace(get_connection)
