"""Job repository functions backed by SQLAlchemy."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from src.persistence.schema import jobs


SessionFactory = sessionmaker[Session]
VALID_JOB_STATUSES = {"queued", "running", "succeeded", "failed", "canceled"}
CANCELABLE_JOB_STATUSES = {"queued", "running"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _progress_to_json(progress: dict | None) -> str:
    return json.dumps(progress or {}, ensure_ascii=False)


def _job_from_mapping(row) -> dict:
    try:
        progress = json.loads(row["progress_json"] or "{}")
    except json.JSONDecodeError:
        progress = {}
    return {
        "id": row["id"],
        "job_type": row["job_type"],
        "status": row["status"],
        "created_by_user_id": row["created_by_user_id"],
        "workspace_id": row["workspace_id"] or "",
        "progress": progress if isinstance(progress, dict) else {},
        "error": row["error"] or "",
        "attempts": int(row["attempts"] or 0),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


def create_job_with_session(
    session_factory: SessionFactory,
    *,
    job_type: str,
    created_by_user_id: str | None,
    workspace_id: str = "",
    status: str = "queued",
    progress: dict | None = None,
) -> dict:
    if status not in VALID_JOB_STATUSES:
        raise ValueError("invalid job status")
    now = _now()
    row = {
        "id": str(uuid4()),
        "job_type": job_type,
        "status": status,
        "created_by_user_id": created_by_user_id,
        "workspace_id": workspace_id,
        "progress_json": _progress_to_json(progress),
        "error": "",
        "attempts": 0,
        "created_at": now,
        "updated_at": now,
        "started_at": now if status == "running" else None,
        "finished_at": now if status in {"succeeded", "failed", "canceled"} else None,
    }
    with session_factory.begin() as session:
        session.execute(jobs.insert().values(**row))
    return _job_from_mapping(row)


def list_jobs_with_session(
    session_factory: SessionFactory,
    *,
    created_by_user_id: str | None = None,
) -> list[dict]:
    statement = select(jobs).order_by(jobs.c.created_at.desc())
    if created_by_user_id is not None:
        statement = statement.where(jobs.c.created_by_user_id == created_by_user_id)
    with session_factory() as session:
        rows = session.execute(statement).mappings().all()
    return [_job_from_mapping(row) for row in rows]


def get_job_with_session(session_factory: SessionFactory, job_id: str) -> dict | None:
    with session_factory() as session:
        row = session.execute(select(jobs).where(jobs.c.id == job_id)).mappings().first()
    return _job_from_mapping(row) if row else None


def cancel_job_with_session(session_factory: SessionFactory, job_id: str) -> dict | None:
    now = _now()
    with session_factory.begin() as session:
        row = session.execute(select(jobs).where(jobs.c.id == job_id)).mappings().first()
        if row is None:
            return None
        if row["status"] in CANCELABLE_JOB_STATUSES:
            session.execute(
                update(jobs)
                .where(jobs.c.id == job_id)
                .values(status="canceled", updated_at=now, finished_at=now)
            )
            row = session.execute(select(jobs).where(jobs.c.id == job_id)).mappings().first()
    return _job_from_mapping(row) if row else None
