from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from src.persistence.auth_repository import create_user_with_session
from src.persistence.job_repository import (
    cancel_job_with_session,
    create_job_with_session,
    get_job_with_session,
    list_jobs_with_session,
)
from src.persistence.schema import metadata
from src.persistence.sqlalchemy_database import create_engine_for_url


def _session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def test_sqlalchemy_create_list_get_and_cancel_job():
    session_factory = _session_factory()
    user = create_user_with_session(session_factory, username="editor", password_hash="hash", role="editor")
    job = create_job_with_session(
        session_factory,
        job_type="ingest_url",
        created_by_user_id=user["id"],
        workspace_id="ws-a",
        progress={"phase": "queued", "percent": 0},
    )

    listed = list_jobs_with_session(session_factory, created_by_user_id=user["id"])
    stored = get_job_with_session(session_factory, job["id"])
    canceled = cancel_job_with_session(session_factory, job["id"])

    assert listed[0]["id"] == job["id"]
    assert stored is not None
    assert stored["progress"] == {"phase": "queued", "percent": 0}
    assert canceled is not None
    assert canceled["status"] == "canceled"
    assert canceled["finished_at"] is not None


def test_sqlalchemy_list_jobs_can_scope_by_creator():
    session_factory = _session_factory()
    editor = create_user_with_session(session_factory, username="editor", password_hash="hash", role="editor")
    viewer = create_user_with_session(session_factory, username="viewer", password_hash="hash", role="viewer")
    editor_job = create_job_with_session(
        session_factory,
        job_type="ingest_file",
        created_by_user_id=editor["id"],
    )
    create_job_with_session(
        session_factory,
        job_type="ingest_url",
        created_by_user_id=viewer["id"],
    )

    scoped = list_jobs_with_session(session_factory, created_by_user_id=editor["id"])
    all_jobs = list_jobs_with_session(session_factory)

    assert [job["id"] for job in scoped] == [editor_job["id"]]
    assert len(all_jobs) == 2
