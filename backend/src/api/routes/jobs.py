"""Background job status routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import authorize_workspace_role, get_current_user_or_legacy_api_key, get_knowledge_base
from src.api.models import JobOut
from src.jobs.enqueue import retry_tracked_job
from src.persistence import audit_store, job_store


router = APIRouter()
_KB_MUTATION_JOB_TYPES = {"ingest_file", "ingest_url", "clear_workspace", "rebuild_index"}


def _is_admin_or_legacy(current_user: dict | None) -> bool:
    return current_user is None or current_user.get("role") == "admin"


def _visible_job_or_404(job_id: str, current_user: dict | None) -> dict:
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if not _is_admin_or_legacy(current_user) and job.get("created_by_user_id") != current_user.get("id"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return job


def _invalidate_kb_cache_after_successful_mutation(job: dict) -> None:
    if job.get("status") == "succeeded" and job.get("job_type") in _KB_MUTATION_JOB_TYPES:
        get_knowledge_base.cache_clear()


@router.get("")
async def list_jobs(
    current_user: dict | None = Depends(get_current_user_or_legacy_api_key),
) -> list[JobOut]:
    owner_id = None if _is_admin_or_legacy(current_user) else str(current_user.get("id") or "")
    return [JobOut(**job) for job in job_store.list_jobs(created_by_user_id=owner_id)]


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    current_user: dict | None = Depends(get_current_user_or_legacy_api_key),
) -> JobOut:
    job = _visible_job_or_404(job_id, current_user)
    _invalidate_kb_cache_after_successful_mutation(job)
    return JobOut(**job)


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    current_user: dict | None = Depends(get_current_user_or_legacy_api_key),
) -> JobOut:
    job = _visible_job_or_404(job_id, current_user)
    if job["status"] not in {"queued", "running", "canceled"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务已结束，无法取消")
    canceled = job_store.cancel_job(job_id)
    if canceled is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if job["status"] != "canceled":
        audit_store.record_event(
            action="job.canceled",
            actor_user_id=current_user.get("id") if current_user else None,
            target_type="job",
            target_id=job_id,
            metadata={
                "job_type": canceled.get("job_type", ""),
                "workspace_id": canceled.get("workspace_id", ""),
            },
        )
    return JobOut(**canceled)


@router.post("/{job_id}/retry")
async def retry_job(
    job_id: str,
    current_user: dict | None = Depends(get_current_user_or_legacy_api_key),
) -> JobOut:
    job = _visible_job_or_404(job_id, current_user)
    workspace_id = str(job.get("workspace_id") or "")
    if workspace_id and not _is_admin_or_legacy(current_user):
        authorize_workspace_role(current_user, workspace_id, "editor")
    try:
        retried = retry_tracked_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="任务队列不可用") from exc
    return JobOut(**retried)
