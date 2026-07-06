from __future__ import annotations

import pytest

from src.api.auth_tokens import hash_password
from src.jobs.enqueue import enqueue_tracked_job
from src.jobs.tasks import run_tracked_job
from src.persistence import auth_store, job_store
from tests.test_auth_routes import _configure_auth_database


class FakeQueue:
    def __init__(self):
        self.calls = []

    def enqueue(self, func, *args, **kwargs):
        self.calls.append({"func": func, "args": args, "kwargs": kwargs})
        return None


class FailingQueue:
    def enqueue(self, *_args, **_kwargs):
        raise RuntimeError("redis unavailable")


def sample_task(left: int, right: int) -> int:
    return left + right


def failing_task() -> None:
    raise RuntimeError("task exploded")


@pytest.fixture()
def isolated_jobs_database(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    yield


def test_run_tracked_job_marks_success(isolated_jobs_database):
    user = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    job = job_store.create_job(job_type="sample", created_by_user_id=user["id"])

    result = run_tracked_job(job["id"], "tests.test_job_tasks:sample_task", [2, 3])
    stored = job_store.get_job(job["id"])

    assert result == 5
    assert stored is not None
    assert stored["status"] == "succeeded"
    assert stored["attempts"] == 1
    assert stored["progress"] == {"phase": "done", "percent": 100}
    assert stored["started_at"] is not None
    assert stored["finished_at"] is not None


def test_run_tracked_job_marks_failure(isolated_jobs_database):
    user = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    job = job_store.create_job(job_type="sample", created_by_user_id=user["id"])

    with pytest.raises(RuntimeError, match="task exploded"):
        run_tracked_job(job["id"], "tests.test_job_tasks:failing_task")
    stored = job_store.get_job(job["id"])

    assert stored is not None
    assert stored["status"] == "failed"
    assert stored["attempts"] == 1
    assert stored["error"] == "task exploded"
    assert stored["finished_at"] is not None


def test_run_tracked_job_skips_canceled_job(isolated_jobs_database):
    user = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    job = job_store.create_job(job_type="sample", created_by_user_id=user["id"])
    job_store.cancel_job(job["id"])

    result = run_tracked_job(job["id"], "tests.test_job_tasks:missing_task")
    stored = job_store.get_job(job["id"])

    assert result is None
    assert stored is not None
    assert stored["status"] == "canceled"
    assert stored["attempts"] == 0


def test_enqueue_tracked_job_creates_db_job_and_uses_same_rq_job_id(isolated_jobs_database):
    user = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    queue = FakeQueue()

    job = enqueue_tracked_job(
        job_type="sample",
        target_path="tests.test_job_tasks:sample_task",
        created_by_user_id=user["id"],
        workspace_id="ws-a",
        args=[2, 3],
        queue=queue,
    )

    assert job["status"] == "queued"
    assert job["workspace_id"] == "ws-a"
    assert queue.calls[0]["func"] is run_tracked_job
    assert queue.calls[0]["args"] == (job["id"], "tests.test_job_tasks:sample_task", [2, 3], {})
    assert queue.calls[0]["kwargs"]["job_id"] == job["id"]


def test_enqueue_tracked_job_marks_failed_when_enqueue_fails(isolated_jobs_database):
    user = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")

    with pytest.raises(RuntimeError, match="redis unavailable"):
        enqueue_tracked_job(
            job_type="sample",
            target_path="tests.test_job_tasks:sample_task",
            created_by_user_id=user["id"],
            queue=FailingQueue(),
        )
    stored_jobs = job_store.list_jobs(created_by_user_id=user["id"])

    assert stored_jobs[0]["status"] == "failed"
    assert stored_jobs[0]["error"] == "redis unavailable"
