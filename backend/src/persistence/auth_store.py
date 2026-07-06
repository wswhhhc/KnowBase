"""Auth persistence facade for the configured business database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.config.settings import settings
from src.persistence import auth_repository
from src.persistence.sqlalchemy_database import get_session_factory


def _session_factory():
    return get_session_factory(settings.storage.database_url)


def create_user(*, username: str, password_hash: str, role: str = "viewer", is_active: bool = True) -> dict:
    return auth_repository.create_user_with_session(
        _session_factory(),
        username=username,
        password_hash=password_hash,
        role=role,
        is_active=is_active,
    )


def get_user_by_username(username: str) -> dict | None:
    return auth_repository.get_user_by_username_with_session(_session_factory(), username)


def get_user_by_id(user_id: str) -> dict | None:
    return auth_repository.get_user_by_id_with_session(_session_factory(), user_id)


def list_users() -> list[dict]:
    return auth_repository.list_users_with_session(_session_factory())


def update_user(
    user_id: str,
    *,
    username: str | None = None,
    password_hash: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> dict | None:
    return auth_repository.update_user_with_session(
        _session_factory(),
        user_id,
        username=username,
        password_hash=password_hash,
        role=role,
        is_active=is_active,
    )


def delete_user(user_id: str) -> bool:
    return auth_repository.delete_user_with_session(_session_factory(), user_id)


def create_refresh_token(*, user_id: str, token_hash: str) -> dict:
    expires_at = (datetime.now(UTC) + timedelta(days=settings.auth.refresh_token_days)).isoformat()
    return auth_repository.create_refresh_token_with_session(
        _session_factory(),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )


def get_refresh_token(token_hash: str) -> dict | None:
    return auth_repository.get_refresh_token_with_session(_session_factory(), token_hash)


def revoke_refresh_token(token_hash: str) -> bool:
    return auth_repository.revoke_refresh_token_with_session(_session_factory(), token_hash)
