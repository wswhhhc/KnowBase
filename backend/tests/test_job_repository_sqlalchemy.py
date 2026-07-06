from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from src.persistence.auth_repository import create_user_with_session
from src.persistence.job_repository import (
    cancel_job_with_session,
    create_job_with_session,
    get_job_with_session,
    list_jobs_with_session,
    mark_job_failed_with_session,
    mark_job_running_with_session,
    mark_job_succeeded_with_session,
    update_job_progress_with_session,
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


def test_sqlalchemy_job_lifecycle_updates_status_progress_and_error():
    session_factory = _session_factory()
    user = create_user_with_session(session_factory, username="editor", password_hash="hash", role="editor")
    job = create_job_with_session(session_factory, job_type="ingest_file", created_by_user_id=user["id"])

    running = mark_job_running_with_session(session_factory, job["id"])
    progressed = update_job_progress_with_session(
        session_factory,
        job["id"],
        progress={"phase": "parsing", "percent": 40},
    )
    succeeded = mark_job_succeeded_with_session(
        session_factory,
        job["id"],
        progress={"phase": "done", "percent": 100},
    )

    assert running is not None
    assert running["status"] == "running"
    assert running["attempts"] == 1
    assert progressed is not None
    assert progressed["progress"] == {"phase": "parsing", "percent": 40}
    assert succeeded is not None
    assert succeeded["status"] == "succeeded"
    assert succeeded["progress"] == {"phase": "done", "percent": 100}
    assert succeeded["finished_at"] is not None

    failed = mark_job_failed_with_session(session_factory, job["id"], error="boom")

    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["error"] == "boom"


def test_sqlalchemy_canceled_job_is_not_overwritten_by_success_or_failure():
    session_factory = _session_factory()
    user = create_user_with_session(session_factory, username="editor", password_hash="hash", role="editor")
    success_job = create_job_with_session(session_factory, job_type="ingest_url", created_by_user_id=user["id"])
    failure_job = create_job_with_session(session_factory, job_type="ingest_url", created_by_user_id=user["id"])

    mark_job_running_with_session(session_factory, success_job["id"])
    cancel_job_with_session(session_factory, success_job["id"])
    succeeded = mark_job_succeeded_with_session(
        session_factory,
        success_job["id"],
        progress={"phase": "done", "percent": 100},
    )

    mark_job_running_with_session(session_factory, failure_job["id"])
    cancel_job_with_session(session_factory, failure_job["id"])
    failed = mark_job_failed_with_session(session_factory, failure_job["id"], error="boom")

    assert succeeded is not None
    assert succeeded["status"] == "canceled"
    assert succeeded["progress"] == {}
    assert succeeded["error"] == ""
    assert failed is not None
    assert failed["status"] == "canceled"
    assert failed["error"] == ""


def test_sqlalchemy_progress_updates_preserve_retry_payload():
    session_factory = _session_factory()
    user = create_user_with_session(session_factory, username="editor", password_hash="hash", role="editor")
    job = create_job_with_session(
        session_factory,
        job_type="ingest_url",
        created_by_user_id=user["id"],
        progress={
            "phase": "queued",
            "percent": 0,
            "_retry": {
                "target_path": "src.jobs.document_tasks:ingest_url_document",
                "args": [],
                "kwargs": {"url": "https://example.com"},
                "inject_job_id": True,
            },
        },
    )

    progressed = update_job_progress_with_session(
        session_factory,
        job["id"],
        progress={"phase": "fetching", "percent": 25},
    )

    assert progressed is not None
    assert progressed["progress"]["phase"] == "fetching"
    assert progressed["progress"]["percent"] == 25
    assert progressed["progress"]["_retry"]["kwargs"] == {"url": "https://example.com"}
