"""Authentication repository functions backed by SQLAlchemy."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.persistence.schema import jobs, refresh_tokens, users, workspace_members


SessionFactory = sessionmaker[Session]
VALID_WORKSPACE_MEMBER_ROLES = {"editor", "viewer"}


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


def list_users_with_session(session_factory: SessionFactory) -> list[dict]:
    with session_factory() as session:
        rows = session.execute(select(users).order_by(users.c.created_at.desc())).mappings().all()
    return [_public_user(_user_from_mapping(row)) for row in rows]


def count_active_admins_with_session(session_factory: SessionFactory) -> int:
    with session_factory() as session:
        count = session.execute(
            select(func.count()).select_from(users).where(users.c.role == "admin", users.c.is_active.is_(True))
        ).scalar_one()
    return int(count)


def update_user_with_session(
    session_factory: SessionFactory,
    user_id: str,
    *,
    username: str | None = None,
    password_hash: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> dict | None:
    values: dict[str, object] = {}
    if username is not None:
        values["username"] = username
    if password_hash is not None:
        values["password_hash"] = password_hash
    if role is not None:
        values["role"] = role
    if is_active is not None:
        values["is_active"] = is_active
    if not values:
        return None
    values["updated_at"] = datetime.now(UTC).isoformat()
    with session_factory.begin() as session:
        session.execute(update(users).where(users.c.id == user_id).values(**values))
        row = session.execute(select(users).where(users.c.id == user_id)).mappings().first()
    return _public_user(_user_from_mapping(row)) if row else None


def delete_user_with_session(session_factory: SessionFactory, user_id: str) -> bool:
    with session_factory.begin() as session:
        session.execute(delete(refresh_tokens).where(refresh_tokens.c.user_id == user_id))
        session.execute(delete(workspace_members).where(workspace_members.c.user_id == user_id))
        session.execute(update(jobs).where(jobs.c.created_by_user_id == user_id).values(created_by_user_id=None))
        result = session.execute(delete(users).where(users.c.id == user_id))
    return result.rowcount > 0


def _workspace_member_from_mapping(row) -> dict:
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "user_id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
        "created_at": row["created_at"],
    }


def list_workspace_members_with_session(session_factory: SessionFactory, workspace_id: str) -> list[dict]:
    statement = (
        select(
            workspace_members.c.id,
            workspace_members.c.workspace_id,
            workspace_members.c.user_id,
            users.c.username,
            workspace_members.c.role,
            workspace_members.c.created_at,
        )
        .select_from(workspace_members.join(users, users.c.id == workspace_members.c.user_id))
        .where(workspace_members.c.workspace_id == workspace_id)
        .order_by(users.c.username)
    )
    with session_factory() as session:
        rows = session.execute(statement).mappings().all()
    return [_workspace_member_from_mapping(row) for row in rows]


def list_workspace_memberships_for_user_with_session(session_factory: SessionFactory, user_id: str) -> list[dict]:
    statement = (
        select(
            workspace_members.c.id,
            workspace_members.c.workspace_id,
            workspace_members.c.user_id,
            workspace_members.c.role,
            workspace_members.c.created_at,
        )
        .where(workspace_members.c.user_id == user_id)
        .order_by(workspace_members.c.created_at)
    )
    with session_factory() as session:
        rows = session.execute(statement).mappings().all()
    return [dict(row) for row in rows]


def get_workspace_member_role_with_session(
    session_factory: SessionFactory,
    *,
    workspace_id: str,
    user_id: str,
) -> str | None:
    with session_factory() as session:
        role = session.execute(
            select(workspace_members.c.role).where(
                workspace_members.c.workspace_id == workspace_id,
                workspace_members.c.user_id == user_id,
            )
        ).scalar_one_or_none()
    return role


def add_workspace_member_with_session(
    session_factory: SessionFactory,
    *,
    workspace_id: str,
    user_id: str,
    role: str,
) -> dict:
    if role not in VALID_WORKSPACE_MEMBER_ROLES:
        raise ValueError("invalid workspace member role")
    now = datetime.now(UTC).isoformat()
    row = {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "role": role,
        "created_at": now,
    }
    with session_factory.begin() as session:
        result = session.execute(workspace_members.insert().values(**row))
        row["id"] = result.inserted_primary_key[0]
    user = get_user_by_id_with_session(session_factory, user_id) or {}
    row["username"] = user.get("username", "")
    return row


def replace_workspace_members_with_session(
    session_factory: SessionFactory,
    *,
    workspace_id: str,
    members: list[dict],
) -> list[dict]:
    now = datetime.now(UTC).isoformat()
    invalid_roles = sorted({str(member.get("role") or "") for member in members} - VALID_WORKSPACE_MEMBER_ROLES)
    if invalid_roles:
        raise ValueError("invalid workspace member role")
    rows = [
        {
            "workspace_id": workspace_id,
            "user_id": member["user_id"],
            "role": member["role"],
            "created_at": now,
        }
        for member in members
    ]
    with session_factory.begin() as session:
        session.execute(delete(workspace_members).where(workspace_members.c.workspace_id == workspace_id))
        if rows:
            session.execute(workspace_members.insert(), rows)
    return list_workspace_members_with_session(session_factory, workspace_id)


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


def revoke_refresh_tokens_for_user_with_session(session_factory: SessionFactory, user_id: str) -> int:
    with session_factory.begin() as session:
        result = session.execute(
            update(refresh_tokens)
            .where(refresh_tokens.c.user_id == user_id, refresh_tokens.c.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC).isoformat())
        )
    return int(result.rowcount or 0)
