"""Conversation facade with SQLite-backed persistence repositories."""

from pathlib import Path

from src.config.constants import DATA_DIR
from src.persistence import (
    bookmark_repository,
    conversation_repository,
    database,
    message_repository,
    pin_state_repository,
    workspace_repository,
)

_DB_PATH = Path(DATA_DIR) / "conversations.db"
_get_conn = database.get_connection


def _sync_db_path_override() -> None:
    configured_db_path = Path(DATA_DIR) / "conversations.db"
    if Path(_DB_PATH).resolve() == configured_db_path.resolve():
        database.clear_db_path_override()
    else:
        database.set_db_path_override(_DB_PATH)


def _run_migrations() -> None:
    _sync_db_path_override()
    database.run_migrations()


def init_db():
    """Compatibility wrapper for the extracted database bootstrap."""
    _sync_db_path_override()
    database.init_db()


def create_conversation(title: str = "新对话", thread_id: str | None = None, workspace_id: str = "") -> dict:
    return conversation_repository.create_conversation(database.get_connection, title, thread_id, workspace_id)


def get_conversation_by_thread(thread_id: str) -> dict | None:
    return conversation_repository.get_conversation_by_thread(database.get_connection, thread_id)


def list_conversations(workspace_id: str | None = None) -> list[dict]:
    return conversation_repository.list_conversations(database.get_connection, workspace_id)


def get_conversation(conv_id: str) -> dict | None:
    return conversation_repository.get_conversation(database.get_connection, conv_id)


def update_title(conv_id: str, title: str) -> bool:
    return conversation_repository.update_title(database.get_connection, conv_id, title)


def delete_conversations(conv_ids: list[str]):
    conversation_repository.delete_conversations(database.get_connection, conv_ids)


def delete_conversation(conv_id: str) -> bool:
    return conversation_repository.delete_conversation(database.get_connection, conv_id)


def add_message(conv_id: str, role: str, content: str, sources: list | None = None, quality_reason: str = "", debug_info: str = "{}") -> int:
    return message_repository.add_message(database.get_connection, conv_id, role, content, sources, quality_reason, debug_info)


def get_messages(conv_id: str) -> list[dict]:
    return message_repository.get_messages(database.get_connection, conv_id)


def list_assistant_debug_pairs() -> list[dict]:
    return message_repository.list_assistant_debug_pairs(database.get_connection)


def update_feedback(msg_row_id: int, feedback: str, conv_id: str | None = None, category: str | None = None, detail: str | None = None) -> bool:
    return message_repository.update_feedback(database.get_connection, msg_row_id, feedback, conv_id, category, detail)


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
    return bookmark_repository.create_bookmark(database.get_connection, workspace_id, conversation_id, message_id, chunk_id, note, content, source, tags)


def list_bookmarks(workspace_id: str | None = None, search: str | None = None) -> list[dict]:
    return bookmark_repository.list_bookmarks(database.get_connection, workspace_id, search)


def update_bookmark(bm_id: int, **kwargs) -> dict | None:
    return bookmark_repository.update_bookmark(database.get_connection, bm_id, **kwargs)


def delete_bookmark(bm_id: int) -> bool:
    return bookmark_repository.delete_bookmark(database.get_connection, bm_id)


# ── Pinned Sources ──


def clear_pin_state(thread_id: str) -> None:
    pin_state_repository.clear_pin_state(database.get_connection, thread_id)


def replace_pin_state(
    thread_id: str,
    pinned_chunk_ids: list[str] | None = None,
    excluded_chunk_ids: list[str] | None = None,
) -> None:
    pin_state_repository.replace_pin_state(database.get_connection, thread_id, pinned_chunk_ids, excluded_chunk_ids)


def load_pin_state(thread_id: str) -> list[dict]:
    return pin_state_repository.load_pin_state(database.get_connection, thread_id)


def load_pin_state_summary(thread_id: str) -> dict:
    return pin_state_repository.load_pin_state_summary(database.get_connection, thread_id)


# ── Workspaces ──


def create_workspace(name: str = "新工作区", description: str = "") -> dict:
    return workspace_repository.create_workspace(database.get_connection, name, description)


def list_workspaces() -> list[dict]:
    return workspace_repository.list_workspaces(database.get_connection)


def update_workspace(ws_id: str, name: str | None = None, description: str | None = None) -> bool:
    return workspace_repository.update_workspace(database.get_connection, ws_id, name, description)


def delete_workspace(ws_id: str) -> bool:
    return workspace_repository.delete_workspace(database.get_connection, ws_id)
