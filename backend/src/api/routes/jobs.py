"""Background job status routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_current_user_or_legacy_api_key
from src.api.models import JobOut
from src.persistence import job_store


router = APIRouter()


def _is_admin_or_legacy(current_user: dict | None) -> bool:
    return current_user is None or current_user.get("role") == "admin"


def _visible_job_or_404(job_id: str, current_user: dict | None) -> dict:
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if not _is_admin_or_legacy(current_user) and job.get("created_by_user_id") != current_user.get("id"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return job


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
    return JobOut(**_visible_job_or_404(job_id, current_user))


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
    return JobOut(**canceled)
