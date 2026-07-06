"""Workspace persistence facade selecting SQLite or SQLAlchemy backends."""

from __future__ import annotations

from src.config.settings import settings
from src.persistence import workspace_repository
from src.persistence.database import get_connection
from src.persistence.sqlalchemy_database import get_session_factory, is_postgres_url


def _session_factory():
    return get_session_factory(settings.storage.database_url)


def _use_sqlalchemy() -> bool:
    return is_postgres_url(settings.storage.database_url)


def list_workspaces() -> list[dict]:
    if _use_sqlalchemy():
        return workspace_repository.list_workspaces_with_session(_session_factory())
    return workspace_repository.list_workspaces(get_connection)


def create_workspace(name: str = "新工作区", description: str = "") -> dict:
    if _use_sqlalchemy():
        return workspace_repository.create_workspace_with_session(_session_factory(), name, description)
    return workspace_repository.create_workspace(get_connection, name, description)


def get_workspace(ws_id: str) -> dict | None:
    if _use_sqlalchemy():
        return workspace_repository.get_workspace_with_session(_session_factory(), ws_id)
    return workspace_repository.get_workspace(get_connection, ws_id)


def update_workspace(ws_id: str, name: str | None = None, description: str | None = None) -> bool:
    if _use_sqlalchemy():
        return workspace_repository.update_workspace_with_session(_session_factory(), ws_id, name, description)
    return workspace_repository.update_workspace(get_connection, ws_id, name, description)


def delete_workspace(ws_id: str) -> bool:
    if _use_sqlalchemy():
        return workspace_repository.delete_workspace_with_session(_session_factory(), ws_id)
    return workspace_repository.delete_workspace(get_connection, ws_id)

