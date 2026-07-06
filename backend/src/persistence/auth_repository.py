"""Authentication repository functions backed by SQLAlchemy."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from src.persistence.schema import refresh_tokens, users


SessionFactory = sessionmaker[Session]


def _user_from_mapping(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "password_hash": row["password_hash"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _public_user(user: dict) -> dict:
    return {key: value for key, value in user.items() if key != "password_hash"}


def create_user_with_session(
    session_factory: SessionFactory,
    *,
    username: str,
    password_hash: str,
    role: str = "viewer",
    is_active: bool = True,
) -> dict:
    now = datetime.now(UTC).isoformat()
    row = {
        "id": str(uuid4()),
        "username": username,
        "password_hash": password_hash,
        "role": role,
        "is_active": is_active,
        "created_at": now,
        "updated_at": now,
    }
    with session_factory.begin() as session:
        session.execute(users.insert().values(**row))
    return _public_user(row)


def get_user_by_username_with_session(session_factory: SessionFactory, username: str) -> dict | None:
    with session_factory() as session:
        row = session.execute(select(users).where(users.c.username == username)).mappings().first()
    return _user_from_mapping(row) if row else None


def get_user_by_id_with_session(session_factory: SessionFactory, user_id: str) -> dict | None:
    with session_factory() as session:
        row = session.execute(select(users).where(users.c.id == user_id)).mappings().first()
    return _user_from_mapping(row) if row else None


def create_refresh_token_with_session(
    session_factory: SessionFactory,
    *,
    user_id: str,
    token_hash: str,
    expires_at: str,
) -> dict:
    row = {
        "id": str(uuid4()),
        "user_id": user_id,
        "token_hash": token_hash,
        "expires_at": expires_at,
        "revoked_at": None,
        "created_at": datetime.now(UTC).isoformat(),
    }
    with session_factory.begin() as session:
        session.execute(refresh_tokens.insert().values(**row))
    return row


def get_refresh_token_with_session(session_factory: SessionFactory, token_hash: str) -> dict | None:
    with session_factory() as session:
        row = session.execute(
            select(refresh_tokens).where(refresh_tokens.c.token_hash == token_hash)
        ).mappings().first()
    return dict(row) if row else None


def revoke_refresh_token_with_session(session_factory: SessionFactory, token_hash: str) -> bool:
    with session_factory.begin() as session:
        result = session.execute(
            update(refresh_tokens)
            .where(refresh_tokens.c.token_hash == token_hash, refresh_tokens.c.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC).isoformat())
        )
    return result.rowcount > 0
