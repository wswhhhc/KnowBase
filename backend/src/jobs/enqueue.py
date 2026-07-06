"""Helpers for enqueueing tracked background jobs."""

from __future__ import annotations

from typing import Any

from rq import Queue

from src.jobs.queue import create_queue
from src.jobs.tasks import run_tracked_job
from src.persistence import audit_store, job_store


def _retry_payload(
    *,
    target_path: str,
    args: list[Any] | None,
    kwargs: dict[str, Any] | None,
    inject_job_id: bool,
) -> dict[str, Any]:
    return {
        "target_path": target_path,
        "args": list(args or []),
        "kwargs": dict(kwargs or {}),
        "inject_job_id": inject_job_id,
    }


def _enqueue_payload(job_id: str, payload: dict[str, Any], *, queue: Queue | None = None) -> None:
    task_kwargs = dict(payload.get("kwargs") or {})
    if payload.get("inject_job_id"):
        task_kwargs["job_id"] = job_id
    (queue or create_queue()).enqueue(
        run_tracked_job,
        job_id,
        str(payload["target_path"]),
        list(payload.get("args") or []),
        task_kwargs,
        job_id=job_id,
    )


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
    retry_payload = _retry_payload(
        target_path=target_path,
        args=args,
        kwargs=kwargs,
        inject_job_id=inject_job_id,
    )
    job = job_store.create_job(
        job_type=job_type,
        created_by_user_id=created_by_user_id,
        workspace_id=workspace_id,
        progress={"phase": "queued", "percent": 0, "_retry": retry_payload},
    )
    audit_store.record_event(
        action="job.queued",
        actor_user_id=created_by_user_id,
        target_type="job",
        target_id=job["id"],
        metadata={"job_type": job_type, "workspace_id": workspace_id},
    )
    try:
        _enqueue_payload(job["id"], retry_payload, queue=queue)
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


def retry_tracked_job(job_id: str, *, queue: Queue | None = None) -> dict:
    job = job_store.get_job(job_id)
    if job is None:
        raise ValueError("任务不存在")
    if job["status"] != "failed":
        raise ValueError("只有失败任务可以重试")
    if job["job_type"] == "ingest_file":
        raise ValueError("文件导入任务无法直接重试，请重新上传文件")

    payload = job.get("progress", {}).get("_retry")
    if not isinstance(payload, dict) or not payload.get("target_path"):
        raise ValueError("任务缺少可重试信息")

    retried = job_store.mark_job_queued_for_retry(job_id)
    if retried is None:
        raise ValueError("任务不存在")

    audit_store.record_event(
        action="job.retried",
        actor_user_id=retried.get("created_by_user_id"),
        target_type="job",
        target_id=job_id,
        metadata={"job_type": retried["job_type"], "workspace_id": retried.get("workspace_id", "")},
    )
    try:
        _enqueue_payload(job_id, payload, queue=queue)
    except Exception as exc:
        job_store.mark_job_failed(job_id, error=str(exc))
        audit_store.record_event(
            action="job.retry_failed",
            actor_user_id=retried.get("created_by_user_id"),
            target_type="job",
            target_id=job_id,
            metadata={
                "job_type": retried["job_type"],
                "workspace_id": retried.get("workspace_id", ""),
                "error": str(exc),
            },
        )
        raise
    return job_store.get_job(job_id) or retried
