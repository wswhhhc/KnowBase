"""Job persistence facade for API routes and future workers."""

from __future__ import annotations

from src.config.settings import settings
from src.persistence import job_repository
from src.persistence.sqlalchemy_database import get_session_factory


def _session_factory():
    return get_session_factory(settings.storage.database_url)


def create_job(
    *,
    job_type: str,
    created_by_user_id: str | None,
    workspace_id: str = "",
    status: str = "queued",
    progress: dict | None = None,
) -> dict:
    return job_repository.create_job_with_session(
        _session_factory(),
        job_type=job_type,
        created_by_user_id=created_by_user_id,
        workspace_id=workspace_id,
        status=status,
        progress=progress,
    )


def list_jobs(*, created_by_user_id: str | None = None) -> list[dict]:
    return job_repository.list_jobs_with_session(
        _session_factory(),
        created_by_user_id=created_by_user_id,
    )


def get_job(job_id: str) -> dict | None:
    return job_repository.get_job_with_session(_session_factory(), job_id)


def cancel_job(job_id: str) -> dict | None:
    return job_repository.cancel_job_with_session(_session_factory(), job_id)
