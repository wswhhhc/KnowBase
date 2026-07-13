"""Application service for document-maintenance background jobs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.services.document_audit import record_workspace_mutation_queued


EnqueueJob = Callable[..., dict[str, Any]]
AuditRecorder = Callable[..., Any]


def enqueue_clear_workspace(
    *,
    workspace_id: str,
    actor_user_id: str | None,
    enqueue_job: EnqueueJob,
    record_event: AuditRecorder,
) -> dict[str, Any]:
    job = enqueue_job(
        job_type="clear_workspace",
        target_path="src.jobs.document_tasks:clear_workspace_documents",
        created_by_user_id=actor_user_id,
        workspace_id=workspace_id,
        kwargs={"workspace_id": workspace_id},
        inject_job_id=True,
    )
    record_workspace_mutation_queued(
        record_event,
        action="document.clear_queued",
        actor_user_id=actor_user_id,
        workspace_id=workspace_id,
        job_id=job["id"],
        job_type="clear_workspace",
    )
    return job


def enqueue_rebuild_index(
    *,
    workspace_id: str,
    actor_user_id: str | None,
    enqueue_job: EnqueueJob,
    record_event: AuditRecorder,
) -> dict[str, Any]:
    job = enqueue_job(
        job_type="rebuild_index",
        target_path="src.jobs.document_tasks:rebuild_index_documents",
        created_by_user_id=actor_user_id,
        workspace_id=workspace_id,
        kwargs={"workspace_id": workspace_id},
        inject_job_id=True,
    )
    record_workspace_mutation_queued(
        record_event,
        action="document.rebuild_queued",
        actor_user_id=actor_user_id,
        workspace_id=workspace_id,
        job_id=job["id"],
        job_type="rebuild_index",
    )
    return job
