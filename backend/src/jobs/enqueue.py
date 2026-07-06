"""Helpers for enqueueing tracked background jobs."""

from __future__ import annotations

from typing import Any

from rq import Queue

from src.jobs.queue import create_queue
from src.jobs.tasks import run_tracked_job
from src.persistence import audit_store, job_store


def enqueue_tracked_job(
    *,
    job_type: str,
    target_path: str,
    created_by_user_id: str | None,
    workspace_id: str = "",
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    queue: Queue | None = None,
    inject_job_id: bool = False,
) -> dict:
    job = job_store.create_job(
        job_type=job_type,
        created_by_user_id=created_by_user_id,
        workspace_id=workspace_id,
        progress={"phase": "queued", "percent": 0},
    )
    audit_store.record_event(
        action="job.queued",
        actor_user_id=created_by_user_id,
        target_type="job",
        target_id=job["id"],
        metadata={"job_type": job_type, "workspace_id": workspace_id},
    )
    task_kwargs = dict(kwargs or {})
    if inject_job_id:
        task_kwargs["job_id"] = job["id"]
    try:
        (queue or create_queue()).enqueue(
            run_tracked_job,
            job["id"],
            target_path,
            args or [],
            task_kwargs,
            job_id=job["id"],
        )
    except Exception as exc:
        job_store.mark_job_failed(job["id"], error=str(exc))
        audit_store.record_event(
            action="job.enqueue_failed",
            actor_user_id=created_by_user_id,
            target_type="job",
            target_id=job["id"],
            metadata={"job_type": job_type, "workspace_id": workspace_id, "error": str(exc)},
        )
        raise
    return job_store.get_job(job["id"]) or job
