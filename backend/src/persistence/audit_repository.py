"""Audit log repository functions backed by SQLAlchemy."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.persistence.schema import audit_logs


SessionFactory = sessionmaker[Session]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _metadata_to_json(metadata: dict | None) -> str:
    return json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)


def _audit_log_from_mapping(row) -> dict:
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return {
        "id": row["id"],
        "actor_user_id": row["actor_user_id"],
        "action": row["action"],
        "target_type": row["target_type"] or "",
        "target_id": row["target_id"] or "",
        "metadata": metadata if isinstance(metadata, dict) else {},
        "created_at": row["created_at"],
    }


def record_audit_log_with_session(
    session_factory: SessionFactory,
    *,
    action: str,
    actor_user_id: str | None = None,
    target_type: str = "",
    target_id: str = "",
    metadata: dict | None = None,
) -> dict:
    row = {
        "actor_user_id": actor_user_id,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "metadata_json": _metadata_to_json(metadata),
        "created_at": _now(),
    }
    with session_factory.begin() as session:
        result = session.execute(audit_logs.insert().values(**row))
        row["id"] = result.inserted_primary_key[0]
    return _audit_log_from_mapping(row)


def list_audit_logs_with_session(
    session_factory: SessionFactory,
    *,
    actor_user_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    statement = select(audit_logs).order_by(audit_logs.c.created_at.desc(), audit_logs.c.id.desc()).limit(limit)
    if actor_user_id is not None:
        statement = statement.where(audit_logs.c.actor_user_id == actor_user_id)
    with session_factory() as session:
        rows = session.execute(statement).mappings().all()
    return [_audit_log_from_mapping(row) for row in rows]
