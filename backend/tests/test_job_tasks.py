from __future__ import annotations

import pytest

from src.api.auth_tokens import hash_password
from src.jobs.document_tasks import clear_workspace_documents, rebuild_index_documents
from src.jobs.enqueue import enqueue_tracked_job
from src.jobs.tasks import run_tracked_job
from src.persistence import audit_store, auth_store, job_store
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


def canceling_task(job_id: str) -> str:
    job_store.cancel_job(job_id)
    return "canceled during execution"


def canceling_failing_task(job_id: str) -> None:
    job_store.cancel_job(job_id)
    raise RuntimeError("task exploded after cancel")


class FakeClearKnowledgeBase:
    def __init__(self):
        self.cleared_workspaces: list[str] = []

    def clear_workspace(self, workspace_id: str = "") -> int:
        self.cleared_workspaces.append(workspace_id)
        return 4

    def document_count_for_workspace(self, workspace_id: str = "") -> int:
        return 0


class FakeRebuildKnowledgeBase:
    def __init__(self):
        self.rebuild_calls = 0

    def rebuild_index(self) -> int:
        self.rebuild_calls += 1
        return 7


@pytest.fixture()
def isolated_jobs_database(monkeypatch, tmp_path):
    _configure_auth_database(monkeypatch, tmp_path)
    yield


def test_run_tracked_job_marks_success(isolated_jobs_database):
    user = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    job = job_store.create_job(job_type="sample", created_by_user_id=user["id"], workspace_id="ws-a")

    result = run_tracked_job(job["id"], "tests.test_job_tasks:sample_task", [2, 3])
    stored = job_store.get_job(job["id"])
    audit_events = audit_store.list_events(actor_user_id=user["id"])

    assert result == 5
    assert stored is not None
    assert stored["status"] == "succeeded"
    assert stored["attempts"] == 1
    assert stored["progress"] == {"phase": "done", "percent": 100}
    assert stored["started_at"] is not None
    assert stored["finished_at"] is not None
    assert audit_events[0]["action"] == "job.succeeded"
    assert audit_events[0]["target_id"] == job["id"]
    assert audit_events[0]["metadata"] == {"job_type": "sample", "workspace_id": "ws-a", "attempts": 1}


def test_run_tracked_job_marks_failure(isolated_jobs_database):
    user = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    job = job_store.create_job(job_type="sample", created_by_user_id=user["id"], workspace_id="ws-a")

    with pytest.raises(RuntimeError, match="task exploded"):
        run_tracked_job(job["id"], "tests.test_job_tasks:failing_task")
    stored = job_store.get_job(job["id"])
    audit_events = audit_store.list_events(actor_user_id=user["id"])

    assert stored is not None
    assert stored["status"] == "failed"
    assert stored["attempts"] == 1
    assert stored["error"] == "task exploded"
    assert stored["finished_at"] is not None
    assert audit_events[0]["action"] == "job.failed"
    assert audit_events[0]["target_id"] == job["id"]
    assert audit_events[0]["metadata"] == {"job_type": "sample", "workspace_id": "ws-a", "attempts": 1}


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


def test_run_tracked_job_preserves_canceled_status_after_task_returns(isolated_jobs_database):
    user = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    job = job_store.create_job(job_type="sample", created_by_user_id=user["id"], workspace_id="ws-a")

    result = run_tracked_job(job["id"], "tests.test_job_tasks:canceling_task", kwargs={"job_id": job["id"]})
    stored = job_store.get_job(job["id"])
    audit_events = audit_store.list_events(actor_user_id=user["id"])

    assert result == "canceled during execution"
    assert stored is not None
    assert stored["status"] == "canceled"
    assert stored["attempts"] == 1
    assert stored["progress"] == {}
    assert not [event for event in audit_events if event["action"] == "job.succeeded"]


def test_run_tracked_job_preserves_canceled_status_after_task_raises(isolated_jobs_database):
    user = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    job = job_store.create_job(job_type="sample", created_by_user_id=user["id"], workspace_id="ws-a")

    with pytest.raises(RuntimeError, match="task exploded after cancel"):
        run_tracked_job(job["id"], "tests.test_job_tasks:canceling_failing_task", kwargs={"job_id": job["id"]})
    stored = job_store.get_job(job["id"])
    audit_events = audit_store.list_events(actor_user_id=user["id"])

    assert stored is not None
    assert stored["status"] == "canceled"
    assert stored["attempts"] == 1
    assert stored["error"] == ""
    assert not [event for event in audit_events if event["action"] == "job.failed"]


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
    audit_events = audit_store.list_events(actor_user_id=user["id"])
    assert audit_events[0]["action"] == "job.queued"
    assert audit_events[0]["target_id"] == job["id"]
    assert audit_events[0]["metadata"] == {"job_type": "sample", "workspace_id": "ws-a"}


def test_enqueue_tracked_job_can_inject_db_job_id_into_task_kwargs(isolated_jobs_database):
    user = auth_store.create_user(username="editor", password_hash=hash_password("editor-pass"), role="editor")
    queue = FakeQueue()

    job = enqueue_tracked_job(
        job_type="sample",
        target_path="tests.test_job_tasks:sample_task",
        created_by_user_id=user["id"],
        kwargs={"left": 2, "right": 3},
        queue=queue,
        inject_job_id=True,
    )

    assert queue.calls[0]["args"] == (
        job["id"],
        "tests.test_job_tasks:sample_task",
        [],
        {"left": 2, "right": 3, "job_id": job["id"]},
    )


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
    audit_events = audit_store.list_events(actor_user_id=user["id"])

    assert stored_jobs[0]["status"] == "failed"
    assert stored_jobs[0]["error"] == "redis unavailable"
    assert [event["action"] for event in audit_events[:2]] == ["job.enqueue_failed", "job.queued"]


def test_clear_workspace_documents_clears_workspace_and_returns_result():
    kb = FakeClearKnowledgeBase()

    result = clear_workspace_documents(workspace_id="ws-a", kb=kb)

    assert kb.cleared_workspaces == ["ws-a"]
    assert result == {
        "removed": 4,
        "total_docs": 0,
        "message": "知识库已清空",
    }


def test_clear_workspace_documents_builds_catalog_only_kb_when_none_is_provided(monkeypatch):
    fake_kb = FakeClearKnowledgeBase()
    init_calls: list[bool] = []

    def _fake_kb_factory(*, require_embeddings: bool = True):
        init_calls.append(require_embeddings)
        return fake_kb

    monkeypatch.setattr("src.jobs.document_tasks.KnowledgeBase", _fake_kb_factory)

    result = clear_workspace_documents(workspace_id="ws-a")

    assert init_calls == [False]
    assert result["message"] == "知识库已清空"


def test_rebuild_index_documents_rebuilds_index_and_returns_result():
    kb = FakeRebuildKnowledgeBase()

    result = rebuild_index_documents(kb=kb)

    assert kb.rebuild_calls == 1
    assert result == {
        "total_docs": 7,
        "message": "索引已重建",
    }
